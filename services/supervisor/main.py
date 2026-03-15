"""
services/supervisor/main.py
Supervisor HTTP API — FastAPI app that runs the distributed LangGraph pipeline.

Endpoints:
  GET  /health                      → {"status": "ok"}
  POST /pipeline/run                → Trigger pipeline, returns session summary
  GET  /pipeline/status/{id}        → Get session final state (after run)
"""
from __future__ import annotations
import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv

sys.path.insert(0, "/app")
load_dotenv(find_dotenv(usecwd=True), override=True)

from services.supervisor.graph import run_distributed_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("supervisor")

app = FastAPI(title="InboxPilot Supervisor", version="1.0.0")

# In-memory session store (sufficient for single-host use)
_sessions: Dict[str, Dict[str, Any]] = {}


class PipelineRequest(BaseModel):
    mode: str = "production"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "InboxPilot Supervisor"}


@app.post("/pipeline/run")
async def run_pipeline(request: PipelineRequest):
    """
    Trigger a full distributed pipeline run.
    Blocks until the pipeline completes and returns the session summary.
    """
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    started_at = datetime.utcnow().isoformat()
    logger.info("[SUPERVISOR] Starting session %s (mode=%s)", session_id, request.mode)

    try:
        final_state = await run_distributed_pipeline(
            session_id=session_id,
            mode=request.mode,
        )
        _sessions[session_id] = final_state

        drafts = final_state.get("drafts_created", [])
        actions = final_state.get("actions_taken", [])
        errors = final_state.get("errors", [])
        archived = sum(1 for a in actions if "archived" in a.get("action", "").lower())
        flagged = sum(1 for a in actions if "manual" in a.get("action", "").lower())

        return {
            "session_id": session_id,
            "started_at": started_at,
            "completed_at": datetime.utcnow().isoformat(),
            "emails_processed": final_state.get("total_emails", 0),
            "drafts_created": len(drafts),
            "archived": archived,
            "flagged_for_review": flagged,
            "errors": len(errors),
            "log": final_state.get("log", []),
        }
    except Exception as exc:
        logger.error("[SUPERVISOR] Pipeline failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/pipeline/status/{session_id}")
async def pipeline_status(session_id: str):
    """Return the stored final state for a completed session."""
    state = _sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return state


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
