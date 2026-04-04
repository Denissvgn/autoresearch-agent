"""Experiment results query endpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from server.core.log_writer import AgentLogWriter

router = APIRouter(prefix="/api", tags=["results"])

_store = None
_mlflow_external_url: str = "http://localhost:5000"


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


@router.get("/research/{research_id}/results")
async def get_results(research_id: str):
    """Full experiment history for a research session."""
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    iterations = await _store.get_iterations(research_id)
    model_type = session.get("model_type", "")
    return {
        "research_id": research_id,
        "session": session,
        "iterations": _enrich_iterations(iterations, model_type),
    }


@router.get("/research/{research_id}/iterations")
async def get_iterations(research_id: str):
    """All iterations with metrics and config snapshots."""
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    iterations = await _store.get_iterations(research_id)
    return _enrich_iterations(iterations, session.get("model_type", ""))


@router.get("/research/{research_id}/iterations/{iteration_num}")
async def get_iteration(research_id: str, iteration_num: int):
    """Single iteration detail."""
    iteration = await _store.get_iteration(research_id, iteration_num)
    if not iteration:
        raise HTTPException(status_code=404, detail="Iteration not found")
    # Need session for model_type
    session = await _store.get_session(research_id)
    model_type = session.get("model_type", "") if session else ""
    return _enrich_iteration(iteration, model_type)


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
    return _enrich_iteration(best, session.get("model_type", ""))


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


@router.get("/research/{research_id}/hpo-studies")
async def get_hpo_studies(research_id: str):
    """HPO study results for a research session (ML-59)."""
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    studies = await _store.get_hpo_studies(research_id)
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
    model_type = session.get("model_type", "")

    payload = {
        "research_id": research_id,
        "session": session,
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
