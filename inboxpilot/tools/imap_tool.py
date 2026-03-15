"""
inboxpilot/tools/imap_tool.py
Demo IMAP tool that returns hard-coded sample emails.
In production mode, uses imaplib with SSL.
"""
from __future__ import annotations
import time
import imaplib
import email
import uuid
from typing import List, Dict, Any, Optional
from inboxpilot.models import EmailObject, SenderInfo, AttachmentMeta


# ── Demo emails ───────────────────────────────────────────────────────────────

DEMO_EMAILS: List[Dict[str, Any]] = [
    {
        "subject": "Q4 Budget Review - Need your input by Friday",
        "sender": {"name": "Sarah Chen", "email": "sarah@company.com"},
        "recipients": ["user@example.com"],
        "date": "2024-01-15T09:30:00Z",
        "body_text": (
            "Hi,\n\nI've attached the Q4 budget draft. I need your feedback on the "
            "marketing allocation by Friday EOD so we can finalize. There's an urgent "
            "gap we need to address ASAP. Can we discuss this week?\n\nBest,\nSarah"
        ),
        "flags": ["unread", "important"],
        "attachments": [{"filename": "Q4_budget_draft.xlsx", "size": 45000, "content_type": "application/vnd.ms-excel"}],
    },
    {
        "subject": "Sync on API integration timeline",
        "sender": {"name": "Mike Johnson", "email": "mike@partner.com"},
        "recipients": ["user@example.com"],
        "date": "2024-01-15T10:15:00Z",
        "body_text": (
            "Hey,\n\nWanted to find time to review the API integration schedule. "
            "Are you free Thursday or Friday this week to meet? "
            "Shouldn't take more than 30 minutes.\n\nThanks,\nMike"
        ),
        "flags": ["unread"],
        "attachments": [],
    },
    {
        "subject": "Python Weekly - Issue 512",
        "sender": {"name": "Python Weekly", "email": "newsletter@pythonweekly.com"},
        "recipients": ["user@example.com"],
        "date": "2024-01-15T08:00:00Z",
        "body_text": (
            "Python Weekly Issue #512\n\n"
            "Top stories this week:\n"
            "- Python 3.12 performance improvements\n"
            "- New features in Pydantic v2\n"
            "- LangChain vs LlamaIndex comparison\n\n"
            "To unsubscribe, click here: https://pythonweekly.com/unsubscribe"
        ),
        "flags": ["unread"],
        "attachments": [],
    },
    {
        "subject": "Build #4521 passed ✓",
        "sender": {"name": "GitHub Actions", "email": "noreply@github.com"},
        "recipients": ["user@example.com"],
        "date": "2024-01-15T11:00:00Z",
        "body_text": (
            "Your workflow run 'CI Pipeline' completed successfully.\n"
            "Branch: main\nCommit: 3f2a9b1\nDuration: 2m 34s\n\n"
            "This is an automated notification. Please do not reply."
        ),
        "flags": ["unread"],
        "attachments": [],
    },
    {
        "subject": "Lunch tomorrow?",
        "sender": {"name": "Alex (Friend)", "email": "alex@gmail.com"},
        "recipients": ["user@example.com"],
        "date": "2024-01-15T12:45:00Z",
        "body_text": (
            "Hey! Any chance you're free tomorrow for lunch? "
            "Maybe that Italian place we went to last month? "
            "Let me know. :)\n\n- Alex"
        ),
        "flags": ["unread"],
        "attachments": [],
    },
]


# ── Tool ──────────────────────────────────────────────────────────────────────

def fetch_emails_demo(latency_ms: int = 300, count: int = 5) -> List[EmailObject]:
    """Return demo emails simulating IMAP fetch."""
    time.sleep(latency_ms / 1000)
    result = []
    for raw in DEMO_EMAILS[:count]:
        obj = EmailObject(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            subject=raw["subject"],
            sender=SenderInfo(**raw["sender"]),
            recipients=raw["recipients"],
            date=raw["date"],
            body_text=raw["body_text"],
            attachments=[AttachmentMeta(**a) for a in raw["attachments"]],
            flags=raw["flags"],
        )
        result.append(obj)
    return result


def fetch_emails_real(
    host: str,
    port: int,
    username: str,
    password: str,
    folder: str = "INBOX",
    max_fetch: int = 10,
) -> List[EmailObject]:
    """Fetch emails from a real IMAP server."""
    conn = imaplib.IMAP4_SSL(host, port)
    conn.login(username, password)
    conn.select(folder)
    _, data = conn.search(None, "UNSEEN")
    ids = data[0].split()[-max_fetch:]
    result = []
    for uid in ids:
        _, msg_data = conn.fetch(uid, "(RFC822)")
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(errors="replace")
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors="replace")
        sender_raw = msg.get("From", "")
        sender_name = sender_raw.split("<")[0].strip().strip('"')
        sender_email = sender_raw.split("<")[-1].rstrip(">") if "<" in sender_raw else sender_raw
        result.append(EmailObject(
            subject=msg.get("Subject", "(No Subject)"),
            sender=SenderInfo(name=sender_name, email=sender_email),
            recipients=[msg.get("To", "")],
            date=msg.get("Date", ""),
            body_text=body,
        ))
    conn.logout()
    return result
