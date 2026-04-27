"""Experiment results query endpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from server.core.log_writer import AgentLogWriter, _format_entry

router = APIRouter(prefix="/api", tags=["results"])

_store = None
_mlflow_external_url: str = "http://localhost:5000"
_PIPELINE_PHASES = ("direction", "volatility", "rl")


def init(store, *, mlflow_external_url: str = "http://localhost:5000"):
    global _store, _mlflow_external_url
    _store = store
    _mlflow_external_url = mlflow_external_url


# ------------------------------------------------------------------
# Iteration enrichment — parse metrics_json into structured fields
# ------------------------------------------------------------------

# Secondary metrics to surface per model type.
# Keys → display labels used by the frontend.
_SECONDARY_METRICS: Dict[str, Dict[str, str]] = {
    "direction": {
        "walkforward_auc": "WF AUC",
        "auc": "AUC",
        "meta_auc_oof": "Meta AUC (OOF)",
        "walkforward_cv": "WF CV",
        "precision": "Precision",
        "recall": "Recall",
        "f1": "F1",
        "signal_rate": "Signal Rate",
        "optimal_threshold": "Threshold",
        "prediction_horizon": "Horizon",
    },
    "volatility": {
        "walkforward_auc": "WF AUC",
        "auc": "AUC",
        "walkforward_cv": "WF CV",
        "precision": "Precision",
        "recall": "Recall",
        "f1": "F1",
        "positive_rate": "Positive Rate",
        "atr_mult": "ATR Mult",
        "signal_rate": "Signal Rate",
        "optimal_threshold": "Threshold",
    },
    "rl": {
        "mean_oos_sharpe": "OOS Sharpe",
        "mean_oos_return": "OOS Return",
        "mean_oos_drawdown": "OOS Drawdown",
        "std_oos_sharpe": "Sharpe Std",
        "sharpe_cv": "Sharpe CV",
        "mean_oos_trades": "OOS Trades",
        "trading_score": "Trading Score",
        "mean_oos_trading_score": "Trading Score",
        "folds_passed": "Folds Passed",
    },
}


def _enrich_iteration(row: Dict[str, Any], model_type: str) -> Dict[str, Any]:
    """Add parsed metrics, MLflow link, and secondary metrics to an iteration dict."""
    enriched = dict(row)

    # Parse metrics_json
    raw_json = row.get("metrics_json")
    metrics: Dict[str, Any] = {}
    if raw_json:
        try:
            metrics = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
        except (json.JSONDecodeError, TypeError):
            pass
    enriched["metrics"] = metrics

    raw_snapshot = row.get("attempt_snapshot_json")
    attempt_snapshot: Dict[str, Any] = {}
    if raw_snapshot:
        try:
            parsed = (
                json.loads(raw_snapshot)
                if isinstance(raw_snapshot, str)
                else raw_snapshot
            )
            attempt_snapshot = parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            attempt_snapshot = {}
    if not attempt_snapshot and isinstance(metrics.get("attempt_snapshot"), dict):
        attempt_snapshot = metrics["attempt_snapshot"]
    enriched["attempt_snapshot"] = attempt_snapshot or None
    enriched["attempt_snapshot_path"] = (
        row.get("attempt_snapshot_path")
        or metrics.get("attempt_snapshot_path")
    )
    enriched["attempt_snapshot_hash"] = (
        row.get("attempt_snapshot_hash")
        or metrics.get("attempt_snapshot_hash")
        or attempt_snapshot.get("snapshot_hash")
    )
    enriched["config_snapshot_sha256"] = attempt_snapshot.get(
        "config_snapshot_sha256"
    )
    enriched["artifact_hash"] = (
        attempt_snapshot.get("artifact_hash")
        or metrics.get("artifact_hash")
        or metrics.get("model_artifact_hash")
    )

    # Resolve mlflow_run_id: column first, then metrics_json
    run_id = row.get("mlflow_run_id") or metrics.get("mlflow_run_id") or ""
    enriched["mlflow_run_id"] = run_id

    # MLflow deep-link
    if run_id:
        enriched["mlflow_url"] = f"{_mlflow_external_url}/#/experiments/0/runs/{run_id}"
    else:
        enriched["mlflow_url"] = None

    # Model registry info
    enriched["model_version"] = metrics.get("model_version")
    enriched["model_registry_name"] = metrics.get("model_registry_name")

    # Training time
    enriched["training_time_s"] = row.get("training_time_s") or metrics.get("training_time_s")

    # Training mode (gpu/local)
    enriched["training_mode"] = metrics.get("training_mode")

    # Description
    enriched["description"] = row.get("description") or metrics.get("description")

    # ML-59: Search phase (hpo_screening, validation, robustness, or None)
    enriched["search_phase"] = row.get("search_phase") or metrics.get("search_phase")

    # Secondary metrics (model-type-aware)
    spec = _SECONDARY_METRICS.get(model_type, {})
    secondary: Dict[str, Any] = {}
    for key, label in spec.items():
        val = metrics.get(key)
        if val is not None:
            secondary[key] = {"label": label, "value": val}
    enriched["secondary_metrics"] = secondary

    return enriched


def _enrich_iterations(rows: List[Dict[str, Any]], model_type: str) -> List[Dict[str, Any]]:
    return [_enrich_iteration(r, model_type) for r in rows]


async def _resolve_result_context(
    research_id: str,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Resolve a research or pipeline ID to the most relevant session context.

    Returns:
        pipeline: pipeline row for pipe_* IDs, else None
        session: current/latest phase session for pipelines, or the session itself
        sessions: ordered phase sessions for pipelines, or [session] for a session
    """
    if research_id.startswith("pipe_"):
        pipeline = await _store.get_pipeline(research_id)
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")

        sessions: list[Dict[str, Any]] = []
        for phase in _PIPELINE_PHASES:
            session_id = pipeline.get(f"{phase}_session_id")
            if not session_id:
                continue
            session = await _store.get_session(session_id)
            if not session:
                continue
            session = dict(session)
            session["pipeline_phase"] = phase
            sessions.append(session)

        current_phase = pipeline.get("current_phase")
        if current_phase:
            current = next(
                (s for s in sessions if s.get("pipeline_phase") == current_phase),
                None,
            )
            if current:
                return pipeline, current, sessions

        return pipeline, (sessions[-1] if sessions else None), sessions

    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return None, session, [session]


def _collect_log_entries(
    sessions: List[Dict[str, Any]],
    *,
    after_line: int = 0,
) -> List[Dict[str, Any]]:
    """Read and flatten agent log entries across one or more sessions."""
    entries: list[Dict[str, Any]] = []
    line_index = 0

    for session in sessions:
        workspace = session.get("workspace_path", "")
        if not workspace:
            continue
        log_path = Path(workspace) / "agent_log.jsonl"
        if not log_path.exists():
            continue

        phase = session.get("pipeline_phase") or session.get("model_type")
        session_id = session.get("id")
        for raw_entry in AgentLogWriter.read_lines(log_path, after_line=0):
            if line_index >= after_line:
                entry = dict(raw_entry)
                meta = entry.get("meta")
                meta = dict(meta) if isinstance(meta, dict) else {}
                if phase:
                    meta.setdefault("phase", phase)
                if session_id:
                    meta.setdefault("research_id", session_id)
                entry["meta"] = meta
                if session_id:
                    entry["research_id"] = session_id
                if phase:
                    entry["pipeline_phase"] = phase
                entries.append(entry)
            line_index += 1

    return entries


def _build_log_text(entries: List[Dict[str, Any]]) -> str:
    return "\n".join(_format_entry(entry) for entry in entries)


@router.get("/research/{research_id}/results")
async def get_results(research_id: str):
    """Full experiment history for a research session."""
    pipeline, session, _ = await _resolve_result_context(research_id)
    if not session:
        return {
            "research_id": research_id,
            "session": pipeline,
            "iterations": [],
        }
    iterations = await _store.get_iterations(session["id"])
    model_type = session.get("model_type", "")
    return {
        "research_id": research_id,
        "resolved_research_id": session["id"],
        "session": pipeline or session,
        "iterations": _enrich_iterations(iterations, model_type),
    }


@router.get("/research/{research_id}/iterations")
async def get_iterations(research_id: str):
    """All iterations with metrics and config snapshots."""
    _, session, _ = await _resolve_result_context(research_id)
    if not session:
        return []
    iterations = await _store.get_iterations(session["id"])
    return _enrich_iterations(iterations, session.get("model_type", ""))


@router.get("/research/{research_id}/iterations/{iteration_num}")
async def get_iteration(research_id: str, iteration_num: int):
    """Single iteration detail."""
    _, session, _ = await _resolve_result_context(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Phase session not found yet")

    iteration = await _store.get_iteration(session["id"], iteration_num)
    if not iteration:
        raise HTTPException(status_code=404, detail="Iteration not found")
    return _enrich_iteration(iteration, session.get("model_type", ""))


@router.get("/research/{research_id}/best")
async def get_best_iteration(research_id: str):
    """Best iteration (highest primary metric with gates passed)."""
    _, session, _ = await _resolve_result_context(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Phase session not found yet")
    best = await _store.get_best_iteration(session["id"])
    if not best:
        raise HTTPException(
            status_code=404,
            detail="No winning iteration found (no iteration with all gates passed)",
        )
    return _enrich_iteration(best, session.get("model_type", ""))


@router.get("/research/{research_id}/agent-log")
async def get_agent_log(
    research_id: str,
    after: Optional[int] = Query(default=None, description="Return only entries after this line number (0-based)"),
    format: Optional[str] = Query(default=None, description="Set to 'json' for raw structured entries"),
):
    """Agent conversation log — full Claude transcript captured during execution."""
    after_line = after if isinstance(after, int) and after > 0 else 0
    _, session, sessions = await _resolve_result_context(research_id)
    if not session and research_id.startswith("pipe_"):
        if format == "json":
            return {
                "research_id": research_id,
                "resolved_research_id": None,
                "entries": [],
                "total_lines": 0,
            }
        return {"research_id": research_id, "log": "No log available yet."}

    entries = _collect_log_entries(sessions, after_line=after_line)
    total_lines = len(_collect_log_entries(sessions, after_line=0))

    if format == "json":
        return {
            "research_id": research_id,
            "resolved_research_id": session["id"] if session else None,
            "entries": entries,
            "total_lines": total_lines,
        }

    text = _build_log_text(entries)
    return {"research_id": research_id, "log": text or "No log available yet."}


@router.get("/research/{research_id}/hpo-studies")
async def get_hpo_studies(research_id: str):
    """HPO study results for a research session (ML-59)."""
    _, session, _ = await _resolve_result_context(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Phase session not found yet")
    studies = await _store.get_hpo_studies(session["id"])
    # Parse top_trials_json for each study
    for study in studies:
        raw = study.get("top_trials_json")
        if raw:
            try:
                study["top_trials"] = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                study["top_trials"] = []
        else:
            study["top_trials"] = []
    return {"research_id": research_id, "hpo_studies": studies}


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
    _, session, _ = await _resolve_result_context(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Phase session not found yet")

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
    _, session, sessions = await _resolve_result_context(research_id)
    if not session and research_id.startswith("pipe_"):
        raise HTTPException(status_code=404, detail="Agent log not found")
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    entries = _collect_log_entries(sessions, after_line=0)
    if not entries:
        raise HTTPException(status_code=404, detail="Agent log not found")

    instrument = session.get("instrument", "unknown")
    model_type = session.get("model_type", "model")
    filename = f"{instrument}_{model_type}_agent_log.jsonl"

    return Response(
        content="".join(json.dumps(entry, default=str) + "\n" for entry in entries),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/research/{research_id}/download/results")
async def download_results(research_id: str):
    """Download the full session + iterations as a JSON file."""
    pipeline, session, _ = await _resolve_result_context(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Phase session not found yet")

    iterations = await _store.get_iterations(session["id"])
    model_type = session.get("model_type", "")

    payload = {
        "research_id": research_id,
        "resolved_research_id": session["id"],
        "session": pipeline or session,
        "iterations": _enrich_iterations(iterations, model_type),
    }

    instrument = session.get("instrument", "unknown")
    model_type = session.get("model_type", "model")
    filename = f"{instrument}_{model_type}_results.json"

    return Response(
        content=json.dumps(payload, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
