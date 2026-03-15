"""
a2a/server.py
Base FastAPI router for A2A-compliant agent microservices.

Each service subclasses A2AServer, sets `agent_card`, and implements `handle_task`.
"""
from __future__ import annotations
import logging
from abc import abstractmethod
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from .models import (
    AgentCard,
    A2ARequest,
    A2AResponse,
    A2AError,
    Task,
    TaskInput,
    TaskResult,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class A2AServer:
    """
    Base class for A2A agent HTTP endpoints.

    Subclasses must:
      1. Set `self.agent_card` with an AgentCard instance.
      2. Implement `async handle_task(task_input) -> list[dict]`
         returning a list of artifact dicts.
    """

    def __init__(self):
        self.router = APIRouter()
        self.agent_card: AgentCard = AgentCard(
            name="Unknown Agent",
            description="Override agent_card in your subclass.",
            url="http://localhost",
        )
        self._register_routes()

    def _register_routes(self):
        # Agent Card discovery
        @self.router.get("/.well-known/agent.json", tags=["A2A"])
        async def agent_card_endpoint():
            return JSONResponse(self.agent_card.model_dump())

        # Health check
        @self.router.get("/health", tags=["A2A"])
        async def health():
            return {"status": "ok", "agent": self.agent_card.name}

        # Main A2A JSON-RPC endpoint
        @self.router.post("/a2a", tags=["A2A"])
        async def a2a_endpoint(request: A2ARequest) -> A2AResponse:
            return await self._dispatch(request)

    async def _dispatch(self, request: A2ARequest) -> A2AResponse:
        """Route JSON-RPC method to the appropriate handler."""
        if request.method != "tasks/send":
            return A2AResponse(
                id=request.id,
                error=A2AError(
                    code=-32601,
                    message=f"Method not found: {request.method}",
                ),
            )

        raw_input = request.params.get("input", {})
        task_input = TaskInput(
            method=raw_input.get("method", ""),
            params=raw_input.get("params", {}),
        )
        task = Task(input=task_input, status="running")

        try:
            logger.info("[%s] Handling task: %s", self.agent_card.name, task_input.method)
            artifacts = await self.handle_task(task_input)
            task.status = "completed"
            task.result = TaskResult(artifacts=artifacts)

            return A2AResponse(
                id=request.id,
                result=task.model_dump(),
            )

        except Exception as exc:
            logger.error("[%s] Task failed: %s", self.agent_card.name, exc, exc_info=True)
            task.status = "failed"
            task.error = str(exc)
            return A2AResponse(
                id=request.id,
                result=task.model_dump(),  # return as result so client sees status=failed
            )

    @abstractmethod
    async def handle_task(self, task_input: TaskInput) -> list[Dict[str, Any]]:
        """
        Process an incoming task and return a list of artifact dicts.
        Raise an exception to signal failure.
        """
        raise NotImplementedError
