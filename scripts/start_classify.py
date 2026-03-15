"""scripts/start_classify.py"""
import sys, os, importlib.util
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
spec = importlib.util.spec_from_file_location(
    "classify_service_main",
    os.path.join(os.path.dirname(__file__), "..", "services", "classify-service", "main.py"),
)
mod = importlib.util.load_from_spec(spec)
spec.loader.exec_module(mod)
import uvicorn
uvicorn.run(mod.app, host="0.0.0.0", port=8002, log_level="info")
