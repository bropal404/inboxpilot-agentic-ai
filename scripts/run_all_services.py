"""
scripts/run_all_services.py
Start all four InboxPilot A2A services locally for development/testing.
Runs each service in a separate subprocess.
"""
import os, sys, subprocess, time, signal, atexit

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON = os.path.join(ROOT, ".venv", "bin", "python") if os.path.exists(
    os.path.join(ROOT, ".venv", "bin", "python")
) else sys.executable

# Detect the pipx venv python
PIPX_PYTHON = "/home/arman-03/.local/share/pipx/venvs/inboxpilot/bin/python"
if os.path.exists(PIPX_PYTHON):
    PYTHON = PIPX_PYTHON

ENV = {**os.environ, "PYTHONPATH": ROOT}

# Override service URLs for local dev
ENV["FETCH_SERVICE_URL"] = "http://localhost:8001"
ENV["CLASSIFY_SERVICE_URL"] = "http://localhost:8002"
ENV["RESPOND_SERVICE_URL"] = "http://localhost:8003"
ENV["SUPERVISOR_URL"] = "http://localhost:8080"

SERVICES = [
    {
        "name": "fetch-service",
        "script": os.path.join(ROOT, "services", "fetch-service", "main.py"),
        "port": 8001,
    },
    {
        "name": "classify-service",
        "script": os.path.join(ROOT, "services", "classify-service", "main.py"),
        "port": 8002,
    },
    {
        "name": "respond-service",
        "script": os.path.join(ROOT, "services", "respond-service", "main.py"),
        "port": 8003,
    },
    {
        "name": "supervisor",
        "script": os.path.join(ROOT, "services", "supervisor", "main.py"),
        "port": 8080,
    },
]

procs = []


def kill_all():
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass


atexit.register(kill_all)


def main():
    print("Starting InboxPilot distributed services...\n")
    for svc in SERVICES:
        log_file = open(f"/tmp/{svc['name']}.log", "w")
        p = subprocess.Popen(
            [PYTHON, svc["script"]],
            env=ENV,
            stdout=log_file,
            stderr=log_file,
        )
        procs.append(p)
        print(f"  ✓ {svc['name']} started (PID {p.pid}) → http://localhost:{svc['port']}")
        time.sleep(1.5)  # stagger startup

    print("\nAll services started. Logs at /tmp/<service>.log")
    print("Press Ctrl+C to stop all.\n")

    try:
        while True:
            # Check if any service died
            for i, (p, svc) in enumerate(zip(procs, SERVICES)):
                if p.poll() is not None:
                    print(f"\n⚠️  {svc['name']} exited (code {p.returncode}). Check /tmp/{svc['name']}.log")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nShutting down services...")
        kill_all()


if __name__ == "__main__":
    main()
