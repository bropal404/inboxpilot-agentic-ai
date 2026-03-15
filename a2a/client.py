"""
a2a/client.py
Async HTTP client for calling A2A-compliant agent services.
Uses httpx with automatic retry and exponential backoff.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

from .models import A2ARequest, A2AResponse, AgentCard, Task, TaskInput, TaskResult

logger = logging.getLogger(__name__)


class A2AClient:
    """
    Client for communicating with A2A agent services via JSON-RPC 2.0 over HTTP.

    Usage:
        async with A2AClient("http://fetch-service:8001") as client:
            result = await client.send_task("email_fetch", {"mode": "production"})
    """

    def __init__(self, base_url: str, timeout: float = 60.0, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "A2AClient":
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("A2AClient must be used as async context manager")
        return self._client

    async def get_agent_card(self) -> AgentCard:
        """Fetch the agent's capability card from /.well-known/agent.json."""
        resp = await self.client.get(f"{self.base_url}/.well-known/agent.json")
        resp.raise_for_status()
        return AgentCard.model_validate(resp.json())

    async def send_task(
        self,
        method: str,
        params: Dict[str, Any] | None = None,
    ) -> TaskResult:
        """
        Send a task to the remote agent and wait for a completed result.
        Retries up to max_retries times on transient errors.
        """
        params = params or {}
        request = A2ARequest(
            method="tasks/send",
            params={
                "input": {
                    "method": method,
                    "params": params,
                }
            },
        )

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "[A2A → %s] %s (attempt %d/%d)",
                    self.base_url,
                    method,
                    attempt,
                    self.max_retries,
                )
                resp = await self.client.post(
                    f"{self.base_url}/a2a",
                    json=request.model_dump(),
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                a2a_resp = A2AResponse.model_validate(resp.json())

                if a2a_resp.error:
                    raise RuntimeError(
                        f"A2A agent error [{a2a_resp.error.code}]: {a2a_resp.error.message}"
                    )

                task = Task.model_validate(a2a_resp.result)
                if task.status == "failed":
                    raise RuntimeError(f"Remote task failed: {task.error}")
                if task.result is None:
                    raise RuntimeError("Remote task returned no result")
                return task.result

            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                wait = 2 ** (attempt - 1)
                logger.warning(
                    "[A2A] Transient error talking to %s: %s — retrying in %ds",
                    self.base_url,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)

        raise RuntimeError(
            f"A2A call to {self.base_url} failed after {self.max_retries} attempts: {last_exc}"
        )
