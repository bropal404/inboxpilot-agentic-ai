"""
services/respond-service/main.py
Respond Agent microservice — A2A-compliant HTTP server.

Supported task method:
  "email_respond"  params: {"email": <EmailObject dict>, "classification": <ClassificationResult dict>}
  Returns:         [DraftObject dict]  as artifacts
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
from inboxpilot.agents.respond_agent import run_respond_agent
from inboxpilot.config_loader import load_config
from inboxpilot.models import EmailObject, ClassificationResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("respond-service")


class RespondAgentService(A2AServer):
    def __init__(self):
        super().__init__()
        self.agent_card = AgentCard(
            name="InboxPilot-Respond",
            description=(
                "Generates a professional draft reply to an email using Groq (Llama 3). "
                "Includes calendar slots for meeting requests."
            ),
            version="1.0.0",
            url=os.environ.get("RESPOND_SERVICE_URL", "http://respond-service:8003"),
            capabilities=[
                AgentCapability(
                    name="email_respond",
                    description="Draft an email reply using Groq Llama 3",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "email": {"type": "object", "description": "EmailObject dict"},
                            "classification": {
                                "type": "object",
                                "description": "ClassificationResult dict",
                            },
                        },
                        "required": ["email", "classification"],
                    },
                    output_schema={
                        "type": "object",
                        "description": "DraftObject",
                    },
                )
            ],
        )

    async def handle_task(self, task_input: TaskInput) -> list[Dict[str, Any]]:
        if task_input.method != "email_respond":
            raise ValueError(f"Unknown method: {task_input.method}")

        email_data = task_input.params.get("email")
        classification_data = task_input.params.get("classification")
        if not email_data or not classification_data:
            raise ValueError("Missing 'email' or 'classification' in params")

        email = EmailObject(**email_data)
        classification = ClassificationResult(**classification_data)
        config = load_config()

        logger.info("Generating draft for: %s", email.subject[:60])
        draft = run_respond_agent(email, classification, config)
        logger.info("Draft created (%d words, confidence %.2f)", draft.word_count, draft.confidence)

        return [draft.model_dump()]


_service = RespondAgentService()

app = FastAPI(title="InboxPilot Respond Service", version="1.0.0")
app.include_router(_service.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")
