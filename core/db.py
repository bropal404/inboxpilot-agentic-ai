"""
inboxpilot/db.py
Simulated in-memory database with optional JSON persistence.
"""
from __future__ import annotations
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class SessionRecord:
    id: str
    started_at: str
    ended_at: Optional[str] = None
    emails_processed: int = 0
    drafts_created: int = 0
    status: str = "running"


@dataclass
class EmailRecord:
    id: str
    session_id: str
    subject: str
    sender_email: str
    received_at: str
    classification: Optional[str] = None
    confidence: Optional[float] = None
    action_taken: Optional[str] = None
    draft_id: Optional[str] = None


@dataclass
class DraftRecord:
    id: str
    email_id: str
    subject: str
    body: str
    created_at: str
    approved: bool = False
    sent_at: Optional[str] = None
    proposed_meetings: List[Dict] = field(default_factory=list)


@dataclass
class StyleSample:
    text: str
    context: str  # "formal" | "casual" | "urgent"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class SimulatedDatabase:
    def __init__(self, persist_path: Optional[str] = None):
        self.sessions: Dict[str, SessionRecord] = {}
        self.emails: Dict[str, EmailRecord] = {}
        self.drafts: Dict[str, DraftRecord] = {}
        self.style_samples: List[StyleSample] = []
        self.persist_path = persist_path

        if persist_path and os.path.exists(persist_path):
            self._load()

    # ── Sessions ──────────────────────────────────────────────────────────────

    def create_session(self, session_id: str, started_at: str) -> SessionRecord:
        record = SessionRecord(id=session_id, started_at=started_at)
        self.sessions[session_id] = record
        return record

    def update_session(self, session_id: str, **kwargs) -> None:
        if session_id in self.sessions:
            for k, v in kwargs.items():
                setattr(self.sessions[session_id], k, v)

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        return self.sessions.get(session_id)

    def list_sessions(self, limit: int = 10) -> List[SessionRecord]:
        all_sessions = list(self.sessions.values())
        return sorted(all_sessions, key=lambda s: s.started_at, reverse=True)[:limit]

    # ── Emails ────────────────────────────────────────────────────────────────

    def save_email(self, record: EmailRecord) -> str:
        self.emails[record.id] = record
        return record.id

    def get_email(self, email_id: str) -> Optional[EmailRecord]:
        return self.emails.get(email_id)

    def get_emails_by_session(self, session_id: str) -> List[EmailRecord]:
        return [e for e in self.emails.values() if e.session_id == session_id]

    # ── Drafts ────────────────────────────────────────────────────────────────

    def save_draft(self, record: DraftRecord) -> str:
        self.drafts[record.id] = record
        return record.id

    def get_pending_drafts(self) -> List[DraftRecord]:
        return [d for d in self.drafts.values() if not d.approved]

    def approve_draft(self, draft_id: str) -> bool:
        if draft_id in self.drafts:
            self.drafts[draft_id].approved = True
            self.drafts[draft_id].sent_at = datetime.utcnow().isoformat()
            return True
        return False

    def discard_draft(self, draft_id: str) -> bool:
        if draft_id in self.drafts:
            del self.drafts[draft_id]
            return True
        return False

    def get_draft(self, draft_id: str) -> Optional[DraftRecord]:
        return self.drafts.get(draft_id)

    # ── Style Samples ─────────────────────────────────────────────────────────

    def add_style_sample(self, text: str, context: str) -> None:
        self.style_samples.append(StyleSample(text=text, context=context))

    def get_style_samples(self, context: str, limit: int = 3) -> List[str]:
        matched = [s.text for s in self.style_samples if s.context == context]
        return matched[:limit]

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        total_sessions = len(self.sessions)
        total_emails = len(self.emails)
        total_drafts = len(self.drafts)
        approved_drafts = sum(1 for d in self.drafts.values() if d.approved)
        category_counts: Dict[str, int] = {}
        for e in self.emails.values():
            if e.classification:
                category_counts[e.classification] = category_counts.get(e.classification, 0) + 1
        confidences = [e.confidence for e in self.emails.values() if e.confidence is not None]
        avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

        return {
            "sessions": total_sessions,
            "emails_processed": total_emails,
            "drafts_created": total_drafts,
            "drafts_approved": approved_drafts,
            "avg_confidence": avg_confidence,
            "category_counts": category_counts,
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self) -> None:
        if not self.persist_path:
            return
        data = {
            "sessions": {k: asdict(v) for k, v in self.sessions.items()},
            "emails": {k: asdict(v) for k, v in self.emails.items()},
            "drafts": {k: asdict(v) for k, v in self.drafts.items()},
            "style_samples": [asdict(s) for s in self.style_samples],
        }
        with open(self.persist_path, "w") as f:
            json.dump(data, f, default=str, indent=2)

    def _load(self) -> None:
        try:
            with open(self.persist_path, "r") as f:
                data = json.load(f)
            for k, v in data.get("sessions", {}).items():
                self.sessions[k] = SessionRecord(**v)
            for k, v in data.get("emails", {}).items():
                self.emails[k] = EmailRecord(**v)
            for k, v in data.get("drafts", {}).items():
                v.setdefault("proposed_meetings", [])
                self.drafts[k] = DraftRecord(**v)
            for s in data.get("style_samples", []):
                self.style_samples.append(StyleSample(**s))
        except Exception:
            pass  # Start fresh if corrupt
