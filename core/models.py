"""
inboxpilot/models.py
Data models for InboxPilot using Pydantic.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class AttachmentMeta(BaseModel):
    filename: str
    size: int  # bytes
    content_type: str = "application/octet-stream"


class SenderInfo(BaseModel):
    name: str
    email: str


class EmailObject(BaseModel):
    id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}")
    subject: str
    sender: SenderInfo
    recipients: List[str] = []
    date: str  # ISO timestamp string
    body_text: str
    body_html: Optional[str] = None
    attachments: List[AttachmentMeta] = []
    thread_id: Optional[str] = None
    flags: List[str] = ["unread"]


class ClassificationResult(BaseModel):
    email_id: str
    category: str  # urgent-action | meeting-request | newsletter | notification | spam | personal
    confidence: float  # 0–1
    priority: int  # 1–10
    reasoning: str
    suggested_action: str
    required_tools: List[str] = []
    estimated_handle_time: str = "5 minutes"


class TimeSlot(BaseModel):
    day: str
    time: str
    duration_minutes: int = 30


class DraftObject(BaseModel):
    draft_id: str = Field(default_factory=lambda: f"draft_{uuid.uuid4().hex[:8]}")
    email_id: str
    subject: str
    body: str
    tone: str = "professional-friendly"
    word_count: int = 0
    proposed_meetings: List[TimeSlot] = []
    confidence: float = 0.85
    requires_approval: bool = True
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    def model_post_init(self, __context: Any) -> None:
        if self.word_count == 0:
            self.word_count = len(self.body.split())


class ActionLog(BaseModel):
    email_id: str
    action: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    details: str = ""


class ErrorLog(BaseModel):
    email_id: Optional[str]
    error: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    agent: str = ""
