"""
inboxpilot/orchestrator.py
LangGraph state machine orchestrating the InboxPilot pipeline.

Nodes: fetch → classify → respond/skip → (loop) → done
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any

from langgraph.graph import StateGraph, END

from inboxpilot.state import InboxState
from inboxpilot.models import EmailObject, ClassificationResult, DraftObject
from inboxpilot.agents.fetch_agent import run_fetch_agent
from inboxpilot.agents.classify_agent import run_classify_agent
from inboxpilot.agents.respond_agent import run_respond_agent
from inboxpilot.db import SimulatedDatabase, SessionRecord, EmailRecord, DraftRecord


# ── Node implementations ───────────────────────────────────────────────────────

def fetch_node(state: InboxState, config: dict, db: SimulatedDatabase, logger) -> InboxState:
    """Fetch emails and seed the queue."""
    logger("[FETCH] Connecting to email server...")
    try:
        emails = run_fetch_agent(config)
        logger(f"[FETCH] Retrieved {len(emails)} emails")
        state["emails"] = [e.model_dump() for e in emails]
        state["total_emails"] = len(emails)
        state["current_email_idx"] = 0
        state["next_step"] = "classify" if emails else "done"
    except Exception as exc:
        logger(f"[FETCH] Error: {exc}")
        state["errors"].append({"agent": "fetch", "error": str(exc), "email_id": None, "timestamp": datetime.utcnow().isoformat()})
        state["next_step"] = "done"
        state["status"] = "error"
    return state


def classify_node(state: InboxState, config: dict, db: SimulatedDatabase, logger) -> InboxState:
    """Classify the current email."""
    idx = state["current_email_idx"]
    email_data = state["emails"][idx]
    email = EmailObject(**email_data)

    logger(f"[CLASSIFY] Processing email {idx + 1}/{state['total_emails']}: \"{email.subject}\"")

    try:
        result: ClassificationResult = run_classify_agent(email, config)
        state["classifications"][email.id] = result.model_dump()

        logger(f"  → Category: {result.category} (confidence: {result.confidence:.2f})")
        logger(f"  → Priority: {result.priority}/10")
        logger(f"  → {result.reasoning}")

        # Persist to DB
        db.save_email(EmailRecord(
            id=email.id,
            session_id=state["session_id"],
            subject=email.subject,
            sender_email=email.sender.email,
            received_at=email.date,
            classification=result.category,
            confidence=result.confidence,
        ))

        # Decide next action
        no_response_categories = {"newsletter", "spam", "notification"}
        if result.category in no_response_categories:
            action = f"Archived / marked as {result.category}"
            state["actions_taken"].append({
                "email_id": email.id,
                "action": action,
                "timestamp": datetime.utcnow().isoformat(),
                "details": result.suggested_action,
            })
            logger(f"  → Action: {action}")
            state["next_step"] = "next_email"
        elif result.category == "personal":
            action = "Flagged for manual review"
            state["actions_taken"].append({
                "email_id": email.id,
                "action": action,
                "timestamp": datetime.utcnow().isoformat(),
                "details": "Personal email, requires user decision.",
            })
            logger(f"  → Action: {action}")
            state["next_step"] = "next_email"
        else:
            # urgent-action or meeting-request → generate draft
            state["next_step"] = "respond"

    except Exception as exc:
        logger(f"  [CLASSIFY] Error: {exc}")
        state["errors"].append({"agent": "classify", "error": str(exc), "email_id": email.id, "timestamp": datetime.utcnow().isoformat()})
        state["next_step"] = "next_email"

    return state


def respond_node(state: InboxState, config: dict, db: SimulatedDatabase, logger) -> InboxState:
    """Generate a draft response for the current email."""
    idx = state["current_email_idx"]
    email = EmailObject(**state["emails"][idx])
    classification_data = state["classifications"][email.id]
    classification = ClassificationResult(**classification_data)

    logger(f"[RESPOND] Generating draft for email {idx + 1}/{state['total_emails']}...")
    if classification.category == "meeting-request":
        logger("  → Checking calendar availability...")

    try:
        draft: DraftObject = run_respond_agent(email, classification, config)
        state["drafts_created"].append(draft.model_dump())
        logger(f"  → Draft created ({draft.word_count} words, confidence: {draft.confidence:.2f})")

        # Persist draft in DB
        db.save_draft(DraftRecord(
            id=draft.draft_id,
            email_id=email.id,
            subject=draft.subject,
            body=draft.body,
            created_at=draft.created_at,
            proposed_meetings=[slot.model_dump() for slot in draft.proposed_meetings],
        ))
        db.save_email(EmailRecord(
            id=email.id,
            session_id=state["session_id"],
            subject=email.subject,
            sender_email=email.sender.email,
            received_at=email.date,
            classification=classification.category,
            confidence=classification.confidence,
            action_taken="draft_created",
            draft_id=draft.draft_id,
        ))

        state["actions_taken"].append({
            "email_id": email.id,
            "action": "draft_created",
            "timestamp": datetime.utcnow().isoformat(),
            "details": f"Draft ID: {draft.draft_id}",
        })

    except Exception as exc:
        logger(f"  [RESPOND] Error: {exc}")
        state["errors"].append({"agent": "respond", "error": str(exc), "email_id": email.id, "timestamp": datetime.utcnow().isoformat()})

    state["next_step"] = "next_email"
    return state


def advance_email(state: InboxState) -> InboxState:
    """Move to the next email or done."""
    state["current_email_idx"] += 1
    if state["current_email_idx"] >= state["total_emails"]:
        state["next_step"] = "done"
    else:
        state["next_step"] = "classify"
    return state


# ── Router helpers ─────────────────────────────────────────────────────────────

def route_after_classify(state: InboxState) -> str:
    ns = state.get("next_step", "done")
    if ns == "respond":
        return "respond"
    elif ns == "next_email":
        return "advance"
    return "done"


def route_after_advance(state: InboxState) -> str:
    ns = state.get("next_step", "done")
    if ns == "classify":
        return "classify"
    return "done"


def route_after_fetch(state: InboxState) -> str:
    ns = state.get("next_step", "done")
    if ns == "classify":
        return "classify"
    return "done"


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_graph(config: dict, db: SimulatedDatabase, logger):
    """Build and compile the LangGraph state machine."""

    def _fetch(state: InboxState) -> InboxState:
        return fetch_node(state, config, db, logger)

    def _classify(state: InboxState) -> InboxState:
        return classify_node(state, config, db, logger)

    def _respond(state: InboxState) -> InboxState:
        return respond_node(state, config, db, logger)

    def _advance(state: InboxState) -> InboxState:
        return advance_email(state)

    graph = StateGraph(InboxState)
    graph.add_node("fetch", _fetch)
    graph.add_node("classify", _classify)
    graph.add_node("respond", _respond)
    graph.add_node("advance", _advance)

    graph.set_entry_point("fetch")
    graph.add_conditional_edges("fetch", route_after_fetch, {
        "classify": "classify",
        "done": END,
    })
    graph.add_conditional_edges("classify", route_after_classify, {
        "respond": "respond",
        "advance": "advance",
        "done": END,
    })
    graph.add_edge("respond", "advance")
    graph.add_conditional_edges("advance", route_after_advance, {
        "classify": "classify",
        "done": END,
    })

    return graph.compile()


# ── Public runner ──────────────────────────────────────────────────────────────

def run_pipeline(config: dict, db: SimulatedDatabase, logger=print) -> InboxState:
    """Run the full InboxPilot pipeline and return final state."""
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    started_at = datetime.utcnow().isoformat()
    db.create_session(session_id, started_at)

    initial_state: InboxState = {
        "session_id": session_id,
        "started_at": started_at,
        "emails": [],
        "current_email_idx": 0,
        "total_emails": 0,
        "classifications": {},
        "actions_taken": [],
        "drafts_created": [],
        "errors": [],
        "retry_count": {},
        "next_step": "fetch",
        "status": "running",
    }

    graph = build_graph(config, db, logger)
    final_state = graph.invoke(initial_state)
    final_state["status"] = "completed"

    db.update_session(
        session_id,
        ended_at=datetime.utcnow().isoformat(),
        emails_processed=final_state["total_emails"],
        drafts_created=len(final_state["drafts_created"]),
        status="completed",
    )
    if config.get("memory", {}).get("auto_save", True):
        db.save()

    return final_state
