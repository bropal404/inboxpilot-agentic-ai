"""
services/fetch-service/main.py
Fetch Agent microservice — A2A-compliant HTTP server.

Exposes:
  GET  /.well-known/agent.json    → AgentCard
  GET  /health                    → {"status": "ok"}
  POST /a2a                        → JSON-RPC dispatcher

Supported task method:
  "email_fetch"   params: {"mode": "demo"|"production", ...config...}
  Returns:  list of EmailObject dicts as artifacts
"""
from __future__ import annotations
import os
import sys
import logging
from typing import Any, Dict

from fastapi import FastAPI
from dotenv import load_dotenv, find_dotenv

# ── Path setup ─────────────────────────────────────────────────────────────────
# Allow imports from the repo root (inboxpilot package + a2a package)
sys.path.insert(0, "/app")
load_dotenv(find_dotenv(usecwd=True), override=True)

from a2a.server import A2AServer
from a2a.models import AgentCard, AgentCapability, TaskInput
from inboxpilot.agents.fetch_agent import run_fetch_agent
from inboxpilot.config_loader import load_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("fetch-service")


class FetchAgentService(A2AServer):
    def __init__(self):
        super().__init__()
        self.agent_card = AgentCard(
            name="InboxPilot-Fetch",
            description=(
                "Fetches emails from an IMAP server (or generates demo data). "
                "Returns a list of EmailObject dicts ready for classification."
            ),
            version="1.0.0",
            url=os.environ.get("FETCH_SERVICE_URL", "http://fetch-service:8001"),
            capabilities=[
                AgentCapability(
                    name="email_fetch",
                    description="Retrieve emails from IMAP or demo source",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "mode": {"type": "string", "enum": ["demo", "production"]},
                        },
                    },
                    output_schema={
                        "type": "array",
                        "items": {"type": "object", "description": "EmailObject"},
                    },
                )
            ],
        )

    async def handle_task(self, task_input: TaskInput) -> list[Dict[str, Any]]:
        if task_input.method != "email_fetch":
            raise ValueError(f"Unknown method: {task_input.method}")

        config = load_config()
        # Allow caller to override mode
        if "mode" in task_input.params:
            config.setdefault("app", {})["mode"] = task_input.params["mode"]

        logger.info("Fetching emails in mode: %s", config.get("app", {}).get("mode", "demo"))
        emails = run_fetch_agent(config)
        logger.info("Fetched %d emails", len(emails))

        return [email.model_dump() for email in emails]


# ── FastAPI app ────────────────────────────────────────────────────────────────

_service = FetchAgentService()

app = FastAPI(title="InboxPilot Fetch Service", version="1.0.0")
app.include_router(_service.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
