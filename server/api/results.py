"""Experiment results query endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Optional

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
async def get_agent_log(research_id: str):
    """Placeholder — agent conversation log.

    In a full implementation, this would read from a stored log file
    written by the orchestrator during the agent session.
    """
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # TODO: Read from agent log file when implemented
    return {
        "research_id": research_id,
        "log": "(Agent log capture not yet implemented)",
        "note": "Agent conversation is streamed via WebSocket during execution",
    }
