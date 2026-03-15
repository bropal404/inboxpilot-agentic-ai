"""
services/supervisor/graph.py
LangGraph StateGraph for the distributed InboxPilot pipeline.

Nodes call each agent service via A2A JSON-RPC over HTTP.
State is stored in-memory per session run (no persistence needed).
"""
from __future__ import annotations
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from langgraph.graph import StateGraph, END

from a2a.client import A2AClient

logger = logging.getLogger("supervisor.graph")


def _svc_urls() -> tuple[str, str, str]:
    """Lazily read service URLs from the environment at call time (not module import time)."""
    return (
        os.environ.get("FETCH_SERVICE_URL", "http://fetch-service:8001"),
        os.environ.get("CLASSIFY_SERVICE_URL", "http://classify-service:8002"),
        os.environ.get("RESPOND_SERVICE_URL", "http://respond-service:8003"),
    )


# Categories that never need a reply
NO_RESPONSE_CATEGORIES = {"newsletter", "spam", "notification"}


# ── LangGraph State ─────────────────────────────────────────────────────────────
from typing import TypedDict, Optional


class PipelineState(TypedDict):
    session_id: str
    mode: str                                   # "demo" | "production"
    emails: List[Dict[str, Any]]
    current_email_idx: int
    total_emails: int
    classifications: Dict[str, Dict[str, Any]]  # email_id → ClassificationResult
    actions_taken: List[Dict[str, Any]]
    drafts_created: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    next_step: str                               # "classify" | "respond" | "next_email" | "done"
    log: List[str]                              # human-readable log lines


# ── Node helpers ────────────────────────────────────────────────────────────────

def _log(state: PipelineState, msg: str) -> None:
    state["log"].append(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}")
    logger.info(msg)


# ── Nodes ───────────────────────────────────────────────────────────────────────

async def fetch_node(state: PipelineState) -> PipelineState:
    FETCH_URL, _, _ = _svc_urls()
    _log(state, f"[FETCH] Calling fetch-service via A2A ({FETCH_URL})")
    try:
        async with A2AClient(FETCH_URL) as client:
            result = await client.send_task(
                "email_fetch", {"mode": state["mode"]}
            )
        emails = result.artifacts
        state["emails"] = emails
        state["total_emails"] = len(emails)
        state["current_email_idx"] = 0
        state["next_step"] = "classify" if emails else "done"
        _log(state, f"[FETCH] Retrieved {len(emails)} emails")
    except Exception as exc:
        _log(state, f"[FETCH] Error: {exc}")
        state["errors"].append({"agent": "fetch", "error": str(exc), "timestamp": datetime.utcnow().isoformat()})
        state["next_step"] = "done"
    return state


async def classify_node(state: PipelineState) -> PipelineState:
    _, CLASSIFY_URL, _ = _svc_urls()
    idx = state["current_email_idx"]
    email = state["emails"][idx]
    subject = email.get("subject", "")[:60]
    _log(state, f"[CLASSIFY] Email {idx + 1}/{state['total_emails']}: \"{subject}\"")
    try:
        async with A2AClient(CLASSIFY_URL) as client:
            result = await client.send_task("email_classify", {"email": email})
        classification = result.artifacts[0]
        email_id = email["id"]
        state["classifications"][email_id] = classification

        category = classification.get("category", "personal")
        confidence = classification.get("confidence", 0.0)
        priority = classification.get("priority", 5)
        _log(state, f"  → Category: {category} (confidence: {confidence:.2f})")
        _log(state, f"  → Priority: {priority}/10 — {classification.get('reasoning', '')}")

        if category in NO_RESPONSE_CATEGORIES:
            action = f"Archived / marked as {category}"
            state["actions_taken"].append({
                "email_id": email_id,
                "action": action,
                "timestamp": datetime.utcnow().isoformat(),
                "details": classification.get("suggested_action", ""),
            })
            _log(state, f"  → Action: {action}")
            state["next_step"] = "next_email"
        elif category == "personal":
            action = "Flagged for manual review"
            state["actions_taken"].append({
                "email_id": email_id,
                "action": action,
                "timestamp": datetime.utcnow().isoformat(),
                "details": "Personal email, requires user decision.",
            })
            _log(state, f"  → Action: {action}")
            state["next_step"] = "next_email"
        else:
            state["next_step"] = "respond"

    except Exception as exc:
        _log(state, f"  [CLASSIFY] Error: {exc}")
        state["errors"].append({
            "agent": "classify",
            "error": str(exc),
            "email_id": email.get("id"),
            "timestamp": datetime.utcnow().isoformat(),
        })
        state["next_step"] = "next_email"
    return state


async def respond_node(state: PipelineState) -> PipelineState:
    _, _, RESPOND_URL = _svc_urls()
    idx = state["current_email_idx"]
    email = state["emails"][idx]
    email_id = email["id"]
    classification = state["classifications"].get(email_id, {})
    _log(state, f"[RESPOND] Generating draft for email {idx + 1}/{state['total_emails']}...")
    try:
        async with A2AClient(RESPOND_URL) as client:
            result = await client.send_task(
                "email_respond",
                {"email": email, "classification": classification},
            )
        draft = result.artifacts[0]
        state["drafts_created"].append(draft)
        word_count = draft.get("word_count", 0)
        confidence = draft.get("confidence", 0.0)
        _log(state, f"  → Draft created ({word_count} words, confidence: {confidence:.2f})")

        state["actions_taken"].append({
            "email_id": email_id,
            "action": "draft_created",
            "timestamp": datetime.utcnow().isoformat(),
            "details": f"Draft ID: {draft.get('draft_id', '')}",
        })
    except Exception as exc:
        _log(state, f"  [RESPOND] Error: {exc}")
        state["errors"].append({
            "agent": "respond",
            "error": str(exc),
            "email_id": email_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
    state["next_step"] = "next_email"
    return state


def advance_node(state: PipelineState) -> PipelineState:
    """Increment the email index and decide whether to continue classifying."""
    state["current_email_idx"] += 1
    if state["current_email_idx"] >= state["total_emails"]:
        state["next_step"] = "done"
    else:
        state["next_step"] = "classify"
    return state


# ── Routing ──────────────────────────────────────────────────────────────────────

def route_after_fetch(state: PipelineState) -> str:
    return state.get("next_step", "done") if state.get("next_step") == "classify" else "done"


def route_after_classify(state: PipelineState) -> str:
    ns = state.get("next_step", "done")
    if ns == "respond":
        return "respond"
    if ns == "next_email":
        return "advance"
    return "done"


def route_after_advance(state: PipelineState) -> str:
    return "classify" if state.get("next_step") == "classify" else "done"


# ── Graph builder ────────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("fetch", fetch_node)
    g.add_node("classify", classify_node)
    g.add_node("respond", respond_node)
    g.add_node("advance", advance_node)

    g.set_entry_point("fetch")
    g.add_conditional_edges("fetch", route_after_fetch, {"classify": "classify", "done": END})
    g.add_conditional_edges("classify", route_after_classify, {
        "respond": "respond",
        "advance": "advance",
        "done": END,
    })
    g.add_edge("respond", "advance")
    g.add_conditional_edges("advance", route_after_advance, {"classify": "classify", "done": END})

    return g.compile()


# ── Public runner ────────────────────────────────────────────────────────────────

async def run_distributed_pipeline(session_id: str, mode: str = "production") -> PipelineState:
    """Run the full distributed pipeline and return the final state."""
    import uuid

    initial_state: PipelineState = {
        "session_id": session_id,
        "mode": mode,
        "emails": [],
        "current_email_idx": 0,
        "total_emails": 0,
        "classifications": {},
        "actions_taken": [],
        "drafts_created": [],
        "errors": [],
        "next_step": "fetch",
        "log": [],
    }

    graph = build_graph()
    final_state = await graph.ainvoke(initial_state)
    return final_state
