"""Experiment results query endpoints."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from src.api.auth import require_api_auth

# P1-2: legacy ML enrichment helpers moved to src/compat (historical
# pre-migration DB-row projection only).
from src.compat.ml_enrichment import (  # noqa: F401
    _feature_readiness_metrics,
    _first_number,
    _rl_economic_replay,
    _rl_economic_replay_summary,
)
from src.core.artifact_reference import first_valid_artifact_ref
from src.core.consistency_validator import (
    build_consistency_report,
    parse_consistency_report,
)
from src.core.gate_status import training_gates_passed_from
from src.core.log_writer import AgentLogWriter, _format_entry
from src.core.pagination import MAX_PAGE_SIZE, build_cursor_page, decode_cursor
from src.core.research_state import build_research_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["results"], dependencies=[Depends(require_api_auth)])

_store = None
_mlflow_external_url: str = "http://localhost:5000"
_PIPELINE_PHASES = ("direction", "volatility", "rl")


def init(store, *, mlflow_external_url: str = "http://localhost:5000"):
    global _store, _mlflow_external_url
    _store = store
    _mlflow_external_url = mlflow_external_url


def _iteration_cursor_extractor(row: Mapping[str, Any]) -> tuple[Any, Any]:
    """Cursor extractor for iterations (sorted by iteration ASC, id ASC)."""

    return (row["iteration"], row["id"])


def _decode_pipeline_payload(pipeline: Dict[str, Any]) -> Dict[str, Any]:
    decoded = dict(pipeline)
    for source, target, fallback_type in (
        ("promotion_blockers_json", "promotion_blockers", list),
        ("promotion_preview_json", "promotion_preview", dict),
    ):
        if target in decoded:
            continue
        raw = decoded.get(source)
        if not raw:
            continue
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, fallback_type):
            decoded[target] = parsed
    return decoded


def _decode_session_payload(session: Dict[str, Any]) -> Dict[str, Any]:
    decoded = dict(session)
    if "promotion_blockers" not in decoded:
        raw = decoded.get("promotion_blockers_json")
        if raw:
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, list):
                decoded["promotion_blockers"] = parsed
    return decoded


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
        "rl_profit_score": "RL Profit Score",
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


def _enrich_iteration(
    row: Dict[str, Any],
    model_type: str,
    *,
    skill_id: str = "",
) -> Dict[str, Any]:
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
    training_gates_passed = training_gates_passed_from(
        metrics,
        default=bool(row.get("all_gates_passed")),
    )
    enriched["training_gates_passed"] = training_gates_passed
    enriched["all_gates_passed"] = training_gates_passed

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
    enriched["config_snapshot_sha256"] = (
        attempt_snapshot.get("config_snapshot_sha256")
    )
    enriched["canonical_config_hash"] = (
        row.get("canonical_config_hash")
        or metrics.get("canonical_config_hash")
        or attempt_snapshot.get("canonical_config_hash")
    )
    raw_identity = row.get("trial_identity_json") or metrics.get("trial_identity")
    if isinstance(raw_identity, str):
        try:
            trial_identity = json.loads(raw_identity)
        except (json.JSONDecodeError, TypeError):
            trial_identity = None
    else:
        trial_identity = raw_identity if isinstance(raw_identity, dict) else None
    enriched["trial_identity"] = (
        trial_identity or attempt_snapshot.get("trial_identity")
    )
    enriched["trial_identity_hash"] = (
        row.get("trial_identity_hash")
        or metrics.get("trial_identity_hash")
        or attempt_snapshot.get("trial_identity_hash")
    )
    enriched["duplicate_reason"] = (
        row.get("duplicate_reason") or metrics.get("duplicate_reason")
    )
    enriched["duplicate_of"] = {
        "research_id": row.get("duplicate_of_research_id")
        or metrics.get("duplicate_of_research_id"),
        "iteration": row.get("duplicate_of_iteration")
        or metrics.get("duplicate_of_iteration"),
    }
    if not any(enriched["duplicate_of"].values()):
        enriched["duplicate_of"] = None
    enriched["artifact_hash"] = first_valid_artifact_ref(
        attempt_snapshot.get("artifact_hash"),
        metrics.get("artifact_hash"),
        metrics.get("model_artifact_hash"),
    )
    consistency_report = parse_consistency_report(
        row.get("consistency_report_json")
    )
    if consistency_report is None:
        consistency_report = build_consistency_report(
            research_id=row.get("research_id", ""),
            iteration=row.get("iteration", 0),
            model_type=model_type,
            config_snapshot=row.get("config_snapshot"),
            metrics_payload=metrics,
            attempt_snapshot=attempt_snapshot,
        )
    enriched["consistency_report"] = consistency_report
    enriched["consistency_report_passed"] = bool(
        consistency_report.get("passed")
    )

    # Resolve mlflow_run_id: column first, then metrics_json.
    run_id = first_valid_artifact_ref(
        row.get("mlflow_run_id"),
        metrics.get("mlflow_run_id"),
        attempt_snapshot.get("mlflow_run_id"),
    )
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
        if val is None and key == "rl_profit_score":
            replay = _rl_economic_replay(metrics)
            val = replay.get("rl_profit_score") if replay else None
        if val is not None:
            secondary[key] = {"label": label, "value": val}
    enriched["secondary_metrics"] = secondary
    enriched["rl_economic_replay"] = _rl_economic_replay_summary(
        metrics,
        attempt_snapshot,
    )
    enriched["feature_readiness_metrics"] = _feature_readiness_metrics(metrics)

    # P3-015 / P3-016: canonical skill fields — additive, derived from legacy.
    # ``skill_id`` ← ``model_type`` via the alias registry; ``skill_phase`` ←
    # the legacy ``search_phase`` column; ``evidence_keys`` ← the metrics dict's
    # known phase-evidence keys. These mirror the WS enrichment (P3-018) so API
    # and WebSocket payloads carry the same canonical surface (§10 guarantee #4).
    #
    # AC-deviation (P1-007 house style): the P3-016 AC names
    # ``src/core/state_store.py`` and reads as if ``skill_phase``/``evidence_keys``
    # were persisted columns on the iteration row. They are NOT persisted — the
    # canonical fields are synthesized here at read time because they derive
    # deterministically from existing columns (``search_phase``) and existing
    # metrics payload keys (``phase_evidence``). Persisting them would require a
    # v7 migration + write-path changes for no semantic gain and would couple the
    # storage layer to the skill vocabulary. The contract is fixed by GEN-010
    # (``test_generalization_falsifiability.py``) which asserts these fields are
    # present and additive on every enriched iteration row.
    from src.core.legacy_alias import model_type_to_skill_id

    if not enriched.get("skill_id"):
        # ARC-012 P7-011: the session's native skill_id column (P7-005) wins
        # — non-ML sessions carry model_type="" and must not enrich to "".
        enriched["skill_id"] = skill_id or (
            model_type_to_skill_id(model_type) if model_type else ""
        )
    if not enriched.get("skill_phase"):
        enriched["skill_phase"] = enriched.get("search_phase")
    if "evidence_keys" not in enriched:
        phase_evidence = metrics.get("phase_evidence")
        if isinstance(phase_evidence, dict):
            enriched["evidence_keys"] = list(phase_evidence.keys())
        else:
            enriched["evidence_keys"] = []

    return enriched


def _enrich_iterations(
    rows: List[Dict[str, Any]],
    model_type: str,
    skill_id: str = "",
) -> List[Dict[str, Any]]:
    return [_enrich_iteration(r, model_type, skill_id=skill_id) for r in rows]


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
        pipeline = _decode_pipeline_payload(pipeline)

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
    session = _decode_session_payload(session)
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
        "iterations": _enrich_iterations(
            iterations, model_type, skill_id=session.get("skill_id") or "",
        ),
    }


@router.get("/research/{research_id}/iterations")
async def get_iterations(
    research_id: str,
    limit: Optional[int] = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: Optional[str] = None,
):
    """Iterations with metrics and config snapshots.

    Pagination is opt-in (ARC-011 P0-017): omit ``limit`` to receive the full
    bare list (today's behavior). Pass ``limit`` to receive a cursor-paginated
    envelope ``{items, limit, next_cursor}``.
    """

    # Under direct (non-FastAPI) calls used by the test suite, `limit` receives
    # the Query() sentinel rather than its default; coerce it to "not provided".
    if not isinstance(limit, int):
        limit = None
    _, session, _ = await _resolve_result_context(research_id)
    if not session:
        if limit is None:
            return []
        return {"items": [], "limit": limit, "next_cursor": None}
    if limit is None:
        iterations = await _store.get_iterations(session["id"])
        return _enrich_iterations(
            iterations,
            session.get("model_type", ""),
            skill_id=session.get("skill_id") or "",
        )
    decoded = decode_cursor(cursor)
    if decoded is None and cursor:
        logger.warning("malformed /iterations cursor token; serving page 1")
    rows = await _store.get_iterations(session["id"], limit=limit, cursor=decoded)
    page = build_cursor_page(rows, limit, _iteration_cursor_extractor)
    page["items"] = _enrich_iterations(
        rows,
        session.get("model_type", ""),
        skill_id=session.get("skill_id") or "",
    )
    return page


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
    """Best iteration (highest primary metric with training gates passed)."""
    _, session, _ = await _resolve_result_context(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Phase session not found yet")
    best = await _store.get_best_iteration(session["id"])
    if not best:
        raise HTTPException(
            status_code=404,
            detail=(
                "No winning iteration found "
                "(no iteration with training gates passed)"
            ),
        )
    return _enrich_iteration(best, session.get("model_type", ""))


@router.get("/research/{research_id}/agent-log")
async def get_agent_log(
    research_id: str,
    after: Optional[int] = Query(
        default=None,
        description="Return only entries after this line number (0-based)"),
    format: Optional[str] = Query(
        default=None, description="Set to 'json' for raw structured entries"),
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
    # Parse structured JSON payloads for each study.
    for study in studies:
        for source, target, fallback in (
            ("top_trials_json", "top_trials", []),
            ("search_space_json", "search_space", {}),
            ("budget_json", "budget", {}),
        ):
            raw = study.get(source)
            if not raw:
                study[target] = fallback
                continue
            try:
                study[target] = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                study[target] = fallback
    return {"research_id": research_id, "hpo_studies": studies}


@router.get("/research/{research_id}/state")
async def get_research_state(research_id: str):
    """Operator-facing session state, reconstructable from DB rows only."""
    pipeline, session, sessions = await _resolve_result_context(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Phase session not found yet")
    iterations = await _store.get_iterations(session["id"])
    hpo_studies = await _store.get_hpo_studies(session["id"])
    planned_trials = await _store.get_planned_trials(session["id"])
    promotions = await _store.list_promotions()
    audit_events = await _collect_audit_events(
        pipeline=pipeline,
        session=session,
        sessions=sessions,
    )
    state_session = dict(session)
    if pipeline:
        state_session["pipeline_id"] = pipeline.get("id")
        for key in (
            "promotion_blocked_phase",
            "promotion_blockers",
            "promotion_blockers_json",
            "promotion_preview",
            "promotion_preview_json",
        ):
            if pipeline.get(key) is not None:
                state_session[key] = pipeline.get(key)
    return build_research_state(
        session=state_session,
        iterations=iterations,
        hpo_studies=hpo_studies,
        planned_trials=planned_trials,
        promotions=promotions,
        audit_events=audit_events,
    )


async def _collect_audit_events(
    *,
    pipeline: Optional[Dict[str, Any]],
    session: Dict[str, Any],
    sessions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    list_events = getattr(_store, "list_audit_events", None)
    if list_events is None:
        return []

    seen: set[str] = set()
    events: List[Dict[str, Any]] = []

    async def add_for(**filters: Any) -> None:
        try:
            rows = await list_events(limit=20, **filters)
        except TypeError:
            return
        for row in rows:
            key = row.get("event_id") or json.dumps(row, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            events.append(row)

    if pipeline and pipeline.get("id"):
        await add_for(pipeline_id=pipeline["id"])
    for row in sessions or [session]:
        sid = row.get("id")
        if sid:
            await add_for(research_id=sid)
    events.sort(key=lambda row: row.get("timestamp") or "", reverse=True)
    return events[:20]


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
