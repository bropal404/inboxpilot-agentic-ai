import asyncio
import json
import os
import shutil
import tarfile
import tempfile
import socket
from pathlib import Path
import docker
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from confluent_kafka import Producer, Consumer
from confluent_kafka.admin import AdminClient, NewTopic

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = docker.from_env()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

# We will maintain a mapping of app_name to a dict of user_id -> WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, app_name: str, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if app_name not in self.active_connections:
            self.active_connections[app_name] = {}
        self.active_connections[app_name][user_id] = websocket

    def disconnect(self, app_name: str, user_id: str):
        if app_name in self.active_connections and user_id in self.active_connections[app_name]:
            del self.active_connections[app_name][user_id]

    async def send_personal_message(self, message: str, app_name: str, user_id: str):
        if app_name in self.active_connections and user_id in self.active_connections[app_name]:
            await self.active_connections[app_name][user_id].send_text(message)

manager = ConnectionManager()

# Kafka Producer
producer_conf = {'bootstrap.servers': KAFKA_BOOTSTRAP}
producer = Producer(producer_conf)
admin_client = AdminClient({'bootstrap.servers': KAFKA_BOOTSTRAP})

# Background Task for Kafka Consumer
# A single loop might not suffice if we have dynamic topics. 
# Or we can subscribe to all topics matching a pattern. confluent-kafka supports regex.
async def consume_all_responses():
    consumer_conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP,
        'group.id': 'orchestrator-group',
        'auto.offset.reset': 'latest'
    }
    consumer = Consumer(consumer_conf)
    # ^.*-responses$ matches any topic ending in -responses
    consumer.subscribe(['^.*-responses$'])
    
    try:
        while True:
            msg = consumer.poll(0.1)
            if msg is None:
                await asyncio.sleep(0.1)
                continue
            if msg.error():
                continue
            
            val = msg.value().decode('utf-8')
            topic = msg.topic()
            app_name = topic.replace('-responses', '')
            try:
                data = json.loads(val)
                user_id = data.get("user_id")
                response_text = data.get("response")
                if user_id and response_text:
                    await manager.send_personal_message(
                        json.dumps({"type": "agent", "text": response_text}), 
                        app_name, 
                        user_id
                    )
            except Exception as e:
                print(f"Error processing message: {e}")
    finally:
        consumer.close()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(consume_all_responses())

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/apps")
def list_apps():
    apps = []
    try:
        containers = client.containers.list()
        for c in containers:
            if "agent" in c.name.lower() or c.labels.get('com.platform.app') == 'true':
                port = "Unknown"
                if c.ports:
                    for k, v in c.ports.items():
                        if v:
                            port = v[0]['HostPort']
                            break
                apps.append({
                    "id": c.short_id,
                    "name": c.name,
                    "status": c.status,
                    "port": port
                })
    except Exception as e:
        print("Error fetching containers", e)
    return {"apps": apps}

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('0.0.0.0', 0))
    port = s.getsockname()[1]
    s.close()
    return port

@app.post("/api/deploy")
async def deploy_app(file: UploadFile = File(...)):
    app_name = file.filename.replace('.tar.gz', '').replace('.tar', '').lower()
    
    # 1. Save uploaded file
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        # 2. Extract tar
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir)
        with tarfile.open(file_path, "r:*") as tar:
            tar.extractall(path=extract_dir)
            
        # Check if extracted dir has a single inner dir
        contents = os.listdir(extract_dir)
        build_dir = extract_dir
        if len(contents) == 1 and os.path.isdir(os.path.join(extract_dir, contents[0])):
            build_dir = os.path.join(extract_dir, contents[0])
            
        # Check platform.yaml
        if not os.path.exists(os.path.join(build_dir, "platform.yaml")):
            raise HTTPException(status_code=400, detail="Missing platform.yaml")
            
        # Read platform.yaml (simple yaml parsing via string replacement since pyyaml not guaranteed)
        with open(os.path.join(build_dir, "platform.yaml"), "r") as pf:
            content = pf.read()
            # extremely naive extraction
            for line in content.split('\n'):
                if line.startswith('name:'):
                    app_name = line.split(':')[1].strip()

        app_name = app_name.lower().replace('_', '-')

        os.system(f'docker run --rm --network platform-net minio/mc:latest sh -c "mc alias set myminio http://minio:9000 admin adminpassword && mc mb myminio/app-{app_name} --ignore-existing" || true')

        in_topic = f"{app_name}-requests"
        out_topic = f"{app_name}-responses"
        fs = admin_client.create_topics([
            NewTopic(in_topic, num_partitions=1, replication_factor=1),
            NewTopic(out_topic, num_partitions=1, replication_factor=1)
        ])
        for t, f in fs.items():
            try:
                f.result() # The result itself is None
            except Exception as e:
                pass # Already exists
        
        # 4. Build and Run Image
        assigned_port = get_free_port()
        try:
            image, _ = client.images.build(path=build_dir, tag=f"{app_name}:latest")
            
            try:
                old_container = client.containers.get(app_name)
                old_container.stop()
                old_container.remove()
            except docker.errors.NotFound:
                pass

            container = client.containers.run(
                image.id,
                name=app_name,
                network="platform-net",
                labels={"com.platform.app": "true"},
                detach=True,
                ports={f"{assigned_port}/tcp": assigned_port},
                environment={
                    "APP_NAME": app_name,
                    "PORT": str(assigned_port),
                    "KAFKA_BOOTSTRAP_SERVERS": KAFKA_BOOTSTRAP,
                    "KAFKA_INPUT_TOPIC": in_topic,
                    "KAFKA_OUTPUT_TOPIC": out_topic,
                    "MINIO_ENDPOINT": "minio:9000",
                    "STORAGE_BUCKET": f"app-{app_name}",
                    "REDIS_URL": "redis://redis:6379/0"
                }
            )
            return {"status": "deployed", "container": container.name, "port": assigned_port}
        except Exception as e:
            print("Deploy Error:", e)
            raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/apps/{app_name}")
def delete_app(app_name: str):
    try:
        container = client.containers.get(app_name)
        container.stop()
        container.remove()
        return {"status": "deleted"}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Not Found")

@app.websocket("/ws/chat/{app_name}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, app_name: str, user_id: str):
    await manager.connect(app_name, user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Send message to specific topic
            payload = json.dumps({"user_id": user_id, "text": data})
            producer.produce(f'{app_name}-requests', value=payload)
            producer.poll(0)
    except WebSocketDisconnect:
        manager.disconnect(app_name, user_id)
