"""
inboxpilot/agents/classify_agent.py
Classify Agent: uses Groq (Llama 3) to categorise emails with structured JSON output.
"""
from __future__ import annotations
import json
from inboxpilot.models import EmailObject, ClassificationResult
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

SYSTEM_PROMPT = """You are an expert email classifier. Analyse the email and respond ONLY with a
valid JSON object matching this exact schema — no markdown, no extra text:

{
  "category": "<one of: urgent-action | meeting-request | newsletter | notification | spam | personal>",
  "confidence": <float 0.0-1.0>,
  "priority": <integer 1-10>,
  "reasoning": "<one sentence explanation>",
  "suggested_action": "<what the assistant should do>",
  "required_tools": ["calendar_check" and/or "draft_generator" as relevant, or empty list],
  "estimated_handle_time": "<e.g. 5 minutes>"
}

Category definitions:
- urgent-action  : Requires response within 24h, mentions deadline/urgent/ASAP
- meeting-request: Scheduling intent, mentions meeting/schedule/availability
- newsletter     : Bulk content, has unsubscribe link, digest format
- notification   : Automated alert, no-reply sender, build/CI notifications
- spam           : Unsolicited commercial or phishing content
- personal       : Non-work, from personal contacts"""


def run_classify_agent(email: EmailObject, config: dict) -> ClassificationResult:
    """Classify a single email using Groq (Llama 3 — free tier)."""
    import os
    agent_cfg = config.get("agents", {}).get("classify", {})
    model_name = agent_cfg.get("model", "llama-3.3-70b-versatile")
    temperature = agent_cfg.get("temperature", 0.1)

    llm = ChatGroq(
        model=model_name,
        temperature=temperature,
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
    )

    user_content = (
        f"Subject: {email.subject}\n"
        f"From: {email.sender.name} <{email.sender.email}>\n"
        f"Date: {email.date}\n"
        f"Attachments: {', '.join(a.filename for a in email.attachments) if email.attachments else 'none'}\n"
        f"\n--- Body ---\n{email.body_text[:800]}"
    )

    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])

    raw = response.content.strip()
    # Strip any accidental markdown code fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw)

    return ClassificationResult(
        email_id=email.id,
        category=data.get("category", "personal"),
        confidence=float(data.get("confidence", 0.5)),
        priority=int(data.get("priority", 5)),
        reasoning=data.get("reasoning", ""),
        suggested_action=data.get("suggested_action", ""),
        required_tools=data.get("required_tools", []),
        estimated_handle_time=data.get("estimated_handle_time", "5 minutes"),
    )
