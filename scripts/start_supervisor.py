"""scripts/start_supervisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# A2A service URLs for local dev (override env from .env)
os.environ.setdefault("FETCH_SERVICE_URL", "http://localhost:8001")
os.environ.setdefault("CLASSIFY_SERVICE_URL", "http://localhost:8002")
os.environ.setdefault("RESPOND_SERVICE_URL", "http://localhost:8003")
from services.supervisor.main import app
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
