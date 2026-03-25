import asyncio
import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .adapter import start_adapter_loop

APP_NAME = os.getenv("APP_NAME", "unknown-app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the Kafka adapter loop in background
    task = asyncio.create_task(start_adapter_loop())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, log_level="info")
