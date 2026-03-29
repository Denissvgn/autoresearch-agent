"""Experiment results query endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from server.core.log_writer import AgentLogWriter

router = APIRouter(prefix="/api", tags=["results"])

_store = None


def init(store):
    global _store
    _store = store


@router.get("/research/{research_id}/results")
async def get_results(research_id: str):
    """Full experiment history for a research session."""
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    iterations = await _store.get_iterations(research_id)
    return {
        "research_id": research_id,
        "session": session,
        "iterations": iterations,
    }


@router.get("/research/{research_id}/iterations")
async def get_iterations(research_id: str):
    """All iterations with metrics and config snapshots."""
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return await _store.get_iterations(research_id)


@router.get("/research/{research_id}/iterations/{iteration_num}")
async def get_iteration(research_id: str, iteration_num: int):
    """Single iteration detail."""
    iteration = await _store.get_iteration(research_id, iteration_num)
    if not iteration:
        raise HTTPException(status_code=404, detail="Iteration not found")
    return iteration


@router.get("/research/{research_id}/best")
async def get_best_iteration(research_id: str):
    """Best iteration (highest primary metric with gates passed)."""
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    best = await _store.get_best_iteration(research_id)
    if not best:
        raise HTTPException(
            status_code=404,
            detail="No winning iteration found (no iteration with all gates passed)",
        )
    return best


@router.get("/research/{research_id}/agent-log")
async def get_agent_log(
    research_id: str,
    after: Optional[int] = Query(default=None, description="Return only entries after this line number (0-based)"),
    format: Optional[str] = Query(default=None, description="Set to 'json' for raw structured entries"),
):
    """Agent conversation log — full Claude transcript captured during execution."""
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    workspace = session.get("workspace_path", "")
    log_path = Path(workspace) / "agent_log.jsonl"

    if not log_path.exists():
        if format == "json":
            return {"research_id": research_id, "entries": [], "total_lines": 0}
        return {"research_id": research_id, "log": "No log available yet."}

    if format == "json":
        entries = AgentLogWriter.read_lines(log_path, after_line=after or 0)
        return {
            "research_id": research_id,
            "entries": entries,
            "total_lines": sum(1 for _ in open(log_path, encoding="utf-8")),
        }

    # Default: human-readable text
    if after is not None and after > 0:
        entries = AgentLogWriter.read_lines(log_path, after_line=after)
        from server.core.log_writer import _format_entry
        text = "\n".join(_format_entry(e) for e in entries)
    else:
        text = AgentLogWriter.read_all(log_path)

    return {"research_id": research_id, "log": text or "No log entries yet."}
