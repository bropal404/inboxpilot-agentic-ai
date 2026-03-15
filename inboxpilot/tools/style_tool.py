"""
inboxpilot/tools/style_tool.py
Returns example writing samples used to guide the Response Agent.
"""
from __future__ import annotations
from typing import List

STYLE_SAMPLES: List[dict] = [
    {
        "context": "formal",
        "text": (
            "Hi [Name],\n\nThank you for reaching out. I've reviewed your message "
            "and will get back to you with a comprehensive response by end of day tomorrow.\n\n"
            "Best regards"
        ),
    },
    {
        "context": "formal",
        "text": (
            "Dear [Name],\n\nI appreciate you bringing this to my attention. "
            "I'll have my team look into it and provide an update within 24 hours.\n\n"
            "Kind regards"
        ),
    },
    {
        "context": "casual",
        "text": (
            "Hey [Name]!\n\nThanks for the heads up! "
            "Sounds good — let me check my schedule and get back to you shortly.\n\nCheers"
        ),
    },
    {
        "context": "casual",
        "text": (
            "Hi [Name],\n\nGot it, totally makes sense. "
            "I'll sort this out and ping you when it's done!\n\nThanks"
        ),
    },
    {
        "context": "urgent",
        "text": (
            "Hi [Name],\n\nI saw this is time-sensitive — I'm on it now. "
            "I'll have something back to you within the hour.\n\nBest"
        ),
    },
]


def get_style_samples(context: str = "formal", limit: int = 2) -> List[str]:
    """Return style samples for the given context."""
    matched = [s["text"] for s in STYLE_SAMPLES if s["context"] == context]
    return matched[:limit] if matched else [STYLE_SAMPLES[0]["text"]]


def get_style_summary() -> dict:
    """Return a summary of user writing style for prompts."""
    return {
        "avg_length_words": 65,
        "common_signoffs": ["Best", "Thanks", "Cheers"],
        "formality": "professional-friendly",
        "typical_response_time": "Morning (9–11am)",
    }
