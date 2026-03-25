from fastapi import FastAPI, HTTPException
import json
import os

app = FastAPI(title="PaaS Repository Server")

# Simulated database of configurations per app deployed on the platform
APPS_CONF = {
    "inboxpilot": {
        "agents": 6,
        "models": 4,
        "tools": 10,
        "topology": ["classify", "fetch", "respond"]
    }
}

@app.get("/config/{app_name}")
def get_config(app_name: str):
    """Serve the topology and config for a specific app requested by the Supervisor/Master"""
    if app_name in APPS_CONF:
        return APPS_CONF[app_name]
    raise HTTPException(status_code=404, detail="App not found")

@app.get("/health")
def health():
    return {"status": "ok"}
