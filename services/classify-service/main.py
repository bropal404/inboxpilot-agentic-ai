"""
services/classify-service/main.py
Classify Agent microservice — A2A-compliant HTTP server.

Supported task method:
  "email_classify"  params: {"email": <EmailObject dict>}
  Returns:          [ClassificationResult dict]  as artifacts
"""
from __future__ import annotations
import os
import sys
import logging
from typing import Any, Dict

from fastapi import FastAPI
from dotenv import load_dotenv, find_dotenv

sys.path.insert(0, "/app")
load_dotenv(find_dotenv(usecwd=True), override=True)

from a2a.server import A2AServer
from a2a.models import AgentCard, AgentCapability, TaskInput
from inboxpilot.agents.classify_agent import run_classify_agent
from inboxpilot.config_loader import load_config
from inboxpilot.models import EmailObject

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("classify-service")


class ClassifyAgentService(A2AServer):
    def __init__(self):
        super().__init__()
        self.agent_card = AgentCard(
            name="InboxPilot-Classify",
            description=(
                "Classifies a single email into categories using Groq (Llama 3). "
                "Returns confidence, priority, category, and suggested action."
            ),
            version="1.0.0",
            url=os.environ.get("CLASSIFY_SERVICE_URL", "http://classify-service:8002"),
            capabilities=[
                AgentCapability(
                    name="email_classify",
                    description="Classify email text using the Groq Llama 3 LLM",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "email": {"type": "object", "description": "EmailObject dict"},
                        },
                        "required": ["email"],
                    },
                    output_schema={
                        "type": "object",
                        "description": "ClassificationResult",
                    },
                )
            ],
        )

    async def handle_task(self, task_input: TaskInput) -> list[Dict[str, Any]]:
        if task_input.method != "email_classify":
            raise ValueError(f"Unknown method: {task_input.method}")

        email_data = task_input.params.get("email")
        if not email_data:
            raise ValueError("Missing 'email' in params")

        email = EmailObject(**email_data)
        config = load_config()

        logger.info("Classifying email: %s", email.subject[:60])
        result = run_classify_agent(email, config)
        logger.info("Category: %s (confidence %.2f)", result.category, result.confidence)

        return [result.model_dump()]


_service = ClassifyAgentService()

app = FastAPI(title="InboxPilot Classify Service", version="1.0.0")
app.include_router(_service.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
