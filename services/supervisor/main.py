import asyncio
from fastapi import FastAPI
from a2a.kafka_bus import bus
import os
import httpx
import json

app = FastAPI(title="PaaS Supervisor Master Node")
REPO_URL = os.getenv("REPO_URL", "http://repo:8000")

@app.on_event("startup")
async def startup():
    # Move blocking kafka connection attempt into a background task 
    # to avoid freezing the Uvicorn application startup lifecycle hook.
    asyncio.create_task(background_boot())

async def background_boot():
    print("🚀 Supervisor Booting...")
    
    try:
        # Connect to sync kafka bus in a separate thread so it doesn't freeze the event loop
        await asyncio.to_thread(bus.connect_producer)
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{REPO_URL}/config/inboxpilot")
            resp.raise_for_status()
            topology = resp.json()
            print(f"📥 Topology Pulled from Repository: {json.dumps(topology)}")
            
            await bus.send("master-events", {"event": "topology_ready", "config": topology})
            print("🚀 Master Topology Broadcast complete.")
    except Exception as e:
        print(f"⚠️ Failed to boot Master properly: {e}")

@app.get("/health")
def health():
    return {"status": "ok", "role": "supervisor"}

@app.post("/execute")
async def execute_task(payload: dict):
    print(f"📤 Translating HTTP POST into Kafka Event -> Topic: 'master-events', Payload: {payload}")
    # Sends a request downward over the broker for the runtime managers to catch
    await bus.send("master-events", {"event": "task_request", "data": payload})
    print("✅ Message successfully published to Kafka bus.")
    return {"status": "broadcasted", "platform": "accepted", "payload": payload}
