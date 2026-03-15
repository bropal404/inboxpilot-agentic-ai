"""
inboxpilot/tools/draft_tool.py
Saves generated draft emails to the demo_drafts/ folder.
"""
from __future__ import annotations
import os
from datetime import datetime
from inboxpilot.models import DraftObject

DEMO_DRAFTS_DIR = "demo_drafts"


def save_draft_demo(draft: DraftObject) -> bool:
    """Save draft to demo_drafts/ directory as a text file."""
    os.makedirs(DEMO_DRAFTS_DIR, exist_ok=True)
    filename = os.path.join(DEMO_DRAFTS_DIR, f"{draft.draft_id}.txt")
    lines = [
        f"Draft ID  : {draft.draft_id}",
        f"Email ID  : {draft.email_id}",
        f"Subject   : {draft.subject}",
        f"Created   : {draft.created_at}",
        f"Confidence: {draft.confidence}",
        "",
        "--- BODY ---",
        draft.body,
    ]
    if draft.proposed_meetings:
        lines.append("")
        lines.append("--- PROPOSED MEETING SLOTS ---")
        for slot in draft.proposed_meetings:
            lines.append(f"  • {slot.day} at {slot.time} ({slot.duration_minutes} min)")

    with open(filename, "w") as f:
        f.write("\n".join(lines))
    return True
