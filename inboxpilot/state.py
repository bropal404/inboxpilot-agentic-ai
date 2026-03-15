"""
inboxpilot/state.py
LangGraph state schema for the InboxPilot pipeline.
"""
from __future__ import annotations
from typing import TypedDict, List, Dict, Any, Optional
from inboxpilot.models import EmailObject, ClassificationResult, DraftObject, ActionLog, ErrorLog


class InboxState(TypedDict):
    # Session
    session_id: str
    started_at: str

    # Email queue
    emails: List[Dict[str, Any]]        # serialised EmailObject dicts
    current_email_idx: int
    total_emails: int

    # Results
    classifications: Dict[str, Dict[str, Any]]   # email_id → ClassificationResult dict
    actions_taken: List[Dict[str, Any]]
    drafts_created: List[Dict[str, Any]]

    # Error tracking
    errors: List[Dict[str, Any]]
    retry_count: Dict[str, int]

    # Routing
    next_step: str   # "fetch" | "classify" | "respond" | "done"
    status: str      # "running" | "completed" | "error"
