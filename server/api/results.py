"""Experiment results query endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

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


# ------------------------------------------------------------------
# Download / export endpoints
# ------------------------------------------------------------------


def _resolve_workspace_file(workspace: str, filename: str) -> Path:
    """Resolve a file within the workspace, guarding against path traversal."""
    base = Path(workspace).resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    return target


@router.get("/research/{research_id}/download/config")
async def download_config(research_id: str):
    """Download the best_train.yaml config as a YAML file."""
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    workspace = session.get("workspace_path", "")
    config_path = _resolve_workspace_file(workspace, "best_train.yaml")

    if not config_path.exists():
        # Fall back to train.yaml if best doesn't exist yet
        config_path = _resolve_workspace_file(workspace, "train.yaml")
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="No config file found in workspace")

    instrument = session.get("instrument", "unknown")
    model_type = session.get("model_type", "model")
    filename = f"{instrument}_{model_type}_best_config.yaml"

    return FileResponse(
        path=str(config_path),
        media_type="application/x-yaml",
        filename=filename,
    )


@router.get("/research/{research_id}/download/agent-log")
async def download_agent_log(research_id: str):
    """Download the agent_log.jsonl transcript as a file."""
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    workspace = session.get("workspace_path", "")
    log_path = _resolve_workspace_file(workspace, "agent_log.jsonl")

    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Agent log not found")

    instrument = session.get("instrument", "unknown")
    model_type = session.get("model_type", "model")
    filename = f"{instrument}_{model_type}_agent_log.jsonl"

    return FileResponse(
        path=str(log_path),
        media_type="application/x-ndjson",
        filename=filename,
    )


@router.get("/research/{research_id}/download/results")
async def download_results(research_id: str):
    """Download the full session + iterations as a JSON file."""
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    iterations = await _store.get_iterations(research_id)

    payload = {
        "research_id": research_id,
        "session": session,
        "iterations": iterations,
    }

    instrument = session.get("instrument", "unknown")
    model_type = session.get("model_type", "model")
    filename = f"{instrument}_{model_type}_results.json"

    return Response(
        content=json.dumps(payload, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
