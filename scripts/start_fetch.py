"""
scripts/start_fetch.py  — local dev launcher for fetch-service (bypasses hyphen module name)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# import the main module from the hyphenated directory using importlib
import importlib.util
spec = importlib.util.spec_from_file_location(
    "fetch_service_main",
    os.path.join(os.path.dirname(__file__), "..", "services", "fetch-service", "main.py"),
)
mod = importlib.util.load_from_spec(spec)
spec.loader.exec_module(mod)

import uvicorn
uvicorn.run(mod.app, host="0.0.0.0", port=8001, log_level="info")
