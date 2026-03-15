"""
a2a/models.py
Pydantic models for the A2A (Agent2Agent) protocol wire format.
Based on Google's A2A specification: JSON-RPC 2.0 over HTTP.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
import uuid


# ── Agent Card ─────────────────────────────────────────────────────────────────

class AgentCapability(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)


class AgentCard(BaseModel):
    """/.well-known/agent.json — describes an agent's identity and capabilities."""
    name: str
    description: str
    version: str = "1.0.0"
    url: str
    capabilities: List[AgentCapability] = Field(default_factory=list)
    authentication: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── A2A Task ────────────────────────────────────────────────────────────────────

TaskStatus = Literal["submitted", "running", "completed", "failed"]


class TaskInput(BaseModel):
    method: str                          # e.g. "email_fetch", "email_classify"
    params: Dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    status: TaskStatus = "submitted"
    input: TaskInput
    result: Optional[TaskResult] = None
    error: Optional[str] = None


# ── JSON-RPC 2.0 Envelope ──────────────────────────────────────────────────────

class A2ARequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str                          # e.g. "tasks/send"
    params: Dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)


class A2AError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class A2AResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[A2AError] = None
