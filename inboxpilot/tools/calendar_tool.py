"""
inboxpilot/tools/calendar_tool.py
Returns free time slots. Demo mode uses hardcoded slots.
"""
from __future__ import annotations
import time
from typing import List
from inboxpilot.models import TimeSlot


DEMO_SLOTS: List[TimeSlot] = [
    TimeSlot(day="Thursday", time="2:00pm", duration_minutes=30),
    TimeSlot(day="Friday", time="10:00am", duration_minutes=30),
    TimeSlot(day="Monday", time="3:00pm", duration_minutes=30),
]


def get_free_slots_demo(latency_ms: int = 300) -> List[TimeSlot]:
    """Return hard-coded demo availability slots."""
    time.sleep(latency_ms / 1000)
    return DEMO_SLOTS


def format_slots(slots: List[TimeSlot]) -> str:
    """Format slots into a human-readable string for email drafts."""
    parts = [f"{s.day} at {s.time} ({s.duration_minutes} min)" for s in slots[:3]]
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + f", or {parts[-1]}"
