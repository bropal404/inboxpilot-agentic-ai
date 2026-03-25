"""
inboxpilot/agents/respond_agent.py
Response Agent: generates a draft reply using GPT-4o-mini,
optionally embedding calendar slots for meeting requests.
"""
from __future__ import annotations
import json
from inboxpilot.models import EmailObject, ClassificationResult, DraftObject, TimeSlot
from inboxpilot.tools.calendar_tool import get_free_slots_demo, format_slots
from inboxpilot.tools.style_tool import get_style_samples
from inboxpilot.tools.draft_tool import save_draft_demo
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

SYSTEM_PROMPT = """You are an executive assistant drafting professional email responses.

Guidelines:
1. Address every question or point in the original email
2. Keep tone professional but warm
3. Target length: 50-150 words
4. For meeting requests: include the provided available time slots naturally in the reply
5. If calendar slots are provided, phrase them like: "I'm free on <slots>."
6. Never start with "I" — vary your opening
7. Close with one of: Best, Thanks, Kind regards, Cheers

Respond ONLY with a JSON object — no markdown fences, no extra text — in this exact schema:
{
  "subject": "<Reply subject starting with Re: >",
  "body": "<Full email body>",
  "tone": "<professional-friendly | formal | casual>",
  "confidence": <float 0.0-1.0>
}"""


def run_respond_agent(
    email: EmailObject,
    classification: ClassificationResult,
    config: dict,
) -> DraftObject:
    """Generate a draft email response and save it to demo_drafts/."""
    import os
    agent_cfg = config.get("agents", {}).get("respond", {})
    model_name = agent_cfg.get("model", "llama-3.1-8b-instant")
    temperature = agent_cfg.get("temperature", 0.7)
    demo_cfg = config.get("app", {}).get("demo", {})
    latency_ms = demo_cfg.get("latency_ms", 300)

    # Determine response context
    context = "formal"
    if classification.category == "personal":
        context = "casual"
    elif classification.category == "urgent-action":
        context = "urgent"

    style_samples = get_style_samples(context=context, limit=2)
    style_hint = "\n".join(f'- "{s}"' for s in style_samples)

    # Get calendar slots if meeting-related
    meeting_slots: list[TimeSlot] = []
    calendar_info = ""
    if classification.category in ("meeting-request", "urgent-action"):
        meeting_slots = get_free_slots_demo(latency_ms=latency_ms)
        calendar_info = f"\nAvailable time slots to include if relevant: {format_slots(meeting_slots)}"

    user_content = (
        f"Original email to respond to:\n"
        f"From: {email.sender.name} <{email.sender.email}>\n"
        f"Subject: {email.subject}\n"
        f"Body:\n{email.body_text}\n\n"
        f"Classification: {classification.category} (priority {classification.priority}/10)\n"
        f"Suggested action: {classification.suggested_action}\n"
        f"{calendar_info}\n\n"
        f"Style examples from user's sent mail:\n{style_hint}"
    )

    llm = ChatGroq(
        model=model_name,
        temperature=temperature,
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
    )
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])

    raw = response.content.strip()
    # Strip markdown code fences if present
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else parts[0]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    import re

    # Sanitise control characters that break json.loads (literal \n inside strings)
    def _sanitise(s: str) -> str:
        # Only replace bare newlines/tabs that appear inside JSON string values
        return re.sub(
            r'("(?:[^"\\]|\\.)*")',
            lambda m: m.group(0).replace('\n', '\\n').replace('\r', '').replace('\t', ' '),
            s,
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            data = json.loads(_sanitise(raw))
        except json.JSONDecodeError:
            # Last resort: field-by-field extraction with tight boundaries
            def _get(key: str) -> str:
                m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL)
                return m.group(1).replace('\\n', '\n') if m else ""
            def _getf(key: str) -> float:
                m = re.search(rf'"{key}"\s*:\s*([0-9.]+)', raw)
                return float(m.group(1)) if m else 0.85
            data = {
                "subject": _get("subject") or f"Re: {email.subject}",
                "body": _get("body"),
                "tone": _get("tone") or "professional-friendly",
                "confidence": _getf("confidence"),
            }


    draft = DraftObject(
        email_id=email.id,
        subject=data.get("subject", f"Re: {email.subject}"),
        body=data.get("body", ""),
        tone=data.get("tone", "professional-friendly"),
        confidence=float(data.get("confidence", 0.85)),
        proposed_meetings=meeting_slots if meeting_slots else [],
        requires_approval=True,
    )

    # Save to demo_drafts/
    save_draft_demo(draft)
    return draft
