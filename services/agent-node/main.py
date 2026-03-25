import os
from fastapi import FastAPI, Request
from a2a.kafka_bus import bus
import asyncio
import httpx

app = FastAPI(title="Node Runtime", version="1.0.0")
node_role = os.getenv("NODE_ROLE", "generic")

@app.on_event("startup")
async def startup_event():
    import sys
    print("Agent starting up...", file=sys.stderr)
    asyncio.create_task(background_boot())

async def background_boot():
    import sys
    print(f"Executing background boot for {node_role}...", file=sys.stderr)
    try:
        await asyncio.to_thread(bus.connect_producer)
        print(f"🚀 Runtime {node_role} Booted. Waiting for instructions over Kafka...", file=sys.stderr)
        
        # Simple asynchronous loop to simulate checking for messages without blocking UVicorn.
        # In a real setup, this would be a persistent consumer loop.
        asyncio.create_task(mock_consumer())
    except Exception as e:
        print(f"Error booting agent: {e}", file=sys.stderr)

async def mock_consumer():
    import json
    from kafka import KafkaConsumer
    import socket
    import sys
    
    # Allow the synchronous connection loop to run in background
    def connect_consume():
        try:
            print(f"🔄 Node {node_role} attaching to topic 'master-events'...", file=sys.stderr)
            consumer = KafkaConsumer(
                "master-events",
                bootstrap_servers=os.getenv("KAFKA_BROKERS", "kafka:9092"),
                value_deserializer=lambda x: json.loads(x.decode("utf-8")),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id=f"group-{node_role}"
            )
            for message in consumer:
                print(f"📥 [NODE:{node_role}] RECEIVED MSG: {message.value}", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ Node consumer failed to attach: {e}", file=sys.stderr)
            
    await asyncio.to_thread(connect_consume)

@app.get("/health")
def health():
    return {"status": "ok", "role": node_role}

@app.post("/execute")
async def execute_task(request: Request):
    data = await request.json()
    await bus.send("orchestrator-events", {"event": "task_completed", "data": data})
    return {"message": "task sent to bus"}
