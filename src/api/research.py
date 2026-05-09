"""Research session management endpoints."""

from __future__ import annotations

import glob
import hashlib
import json
import os
from collections.abc import Awaitable, Callable
from typing import Any, Dict, Optional

import yaml
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from src.api.audit import record_api_audit_event
from src.api.auth import require_api_auth
from src.config import settings

router = APIRouter(tags=["research"], dependencies=[Depends(require_api_auth)])
VALID_PIPELINE_PHASES = {"direction", "volatility", "rl"}

# These will be injected by main.py
_session_manager = None
_store = None


def init(session_manager, store):
    global _session_manager, _store
    _session_manager = session_manager
    _store = store


def _start_metadata(req: "StartResearchRequest") -> dict[str, Any]:
    return {
        "instrument": req.instrument,
        "timeframe": req.timeframe,
        "model_type": req.model_type,
        "tag": req.tag,
        "quick_mode": req.quick_mode,
        "max_iterations": req.max_iterations,
        "max_budget_usd": req.max_budget_usd,
        "timeout_minutes": req.timeout_minutes,
        "trading_mode": req.trading_mode,
        "agent_strategy": req.agent_strategy,
        "initial_balance": req.initial_balance,
        "enable_hpo": req.enable_hpo,
        "hpo_trials": req.hpo_trials,
        "hpo_timesteps": req.hpo_timesteps,
        "phase_budgets": req.phase_budgets,
        "manifest_supplied": req.manifest is not None,
    }


def _continue_metadata(req: "ContinueResearchRequest") -> dict[str, Any]:
    return {
        "max_iterations": req.max_iterations,
        "max_budget_usd": req.max_budget_usd,
        "timeout_minutes": req.timeout_minutes,
        "focus_hint_supplied": req.focus_hint is not None,
    }


def _runtime_resume_metadata(req: "RuntimeResumeRequest") -> dict[str, Any]:
    return {
        "reason_supplied": bool(req.reason),
        "allow_interrupted": req.allow_interrupted,
        "max_iterations": req.max_iterations,
        "max_budget_usd": req.max_budget_usd,
        "timeout_minutes": req.timeout_minutes,
        "focus_hint_supplied": req.focus_hint is not None,
    }


async def _audit(
    request: Request,
    *,
    action: str,
    outcome: str,
    research_id: str | None = None,
    pipeline_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
):
    return await record_api_audit_event(
        request,
        _store,
        action=action,
        outcome=outcome,
        research_id=research_id,
        pipeline_id=pipeline_id,
        metadata=metadata,
        error_message=error_message,
    )


def _validate_phase_budgets(value: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]:
    if value is None:
        return None
    unknown = sorted(set(value) - VALID_PIPELINE_PHASES)
    if unknown:
        raise ValueError(f"Unknown phase budget keys: {', '.join(unknown)}")
    invalid = {
        phase: budget
        for phase, budget in value.items()
        if not isinstance(budget, int) or budget < 1
    }
    if invalid:
        raise ValueError("phase_budgets values must be integers >= 1")
    return value


def _json_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _run_idempotent(
    *,
    operation: str,
    parent_id: str,
    key: str | None,
    request_payload: Dict[str, Any],
    call: Callable[[], Awaitable[Dict[str, Any]]],
) -> Dict[str, Any]:
    if not key or not key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    if _store is None:
        raise HTTPException(status_code=503, detail="Results store is not initialized")

    key_hash = hashlib.sha256(key.strip().encode("utf-8")).hexdigest()
    request_hash = _json_hash(
        {
            "operation": operation,
            "parent_id": parent_id,
            "request": request_payload,
        }
    )
    existing = await _store.begin_idempotency_record(
        operation=operation,
        parent_id=parent_id,
        key_hash=key_hash,
        request_hash=request_hash,
    )
    if existing:
        if existing.get("request_hash") != request_hash:
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key was already used for a different request",
            )
        if existing.get("status") == "completed" and existing.get("response_json"):
            try:
                return json.loads(existing["response_json"])
            except (json.JSONDecodeError, TypeError) as exc:
                raise HTTPException(
                    status_code=500,
                    detail="Stored idempotency response is invalid",
                ) from exc
        raise HTTPException(
            status_code=409,
            detail="Idempotent request is already in progress",
        )

    try:
        response = await call()
    except Exception:
        await _store.delete_idempotency_record(
            operation=operation,
            parent_id=parent_id,
            key_hash=key_hash,
        )
        raise

    await _store.complete_idempotency_record(
        operation=operation,
        parent_id=parent_id,
        key_hash=key_hash,
        child_id=response.get("id"),
        response=response,
    )
    return response


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------


class StartResearchRequest(BaseModel):
    instrument: str = Field(..., examples=["DOGE_USDT"])
    timeframe: str = Field(..., examples=["15m"])
    model_type: str = Field(..., pattern="^(direction|volatility|rl|pipeline)$")
    tag: Optional[str] = Field(default=None, examples=["doge-apr01"])
    quick_mode: Optional[bool] = Field(
        default=None,
        description="If null, uses server default (standard/full mode)",
    )
    max_iterations: Optional[int] = Field(default=None, ge=1, le=500)
    max_budget_usd: Optional[float] = Field(default=None, ge=0.1, le=500.0)
    timeout_minutes: Optional[int] = Field(
        default=None, ge=30, le=1440,
        description="Session timeout in minutes (default: server setting, typically 120)",
    )
    focus_hint: Optional[str] = Field(
        default=None, max_length=1000,
        description="Optional hint for the agent about what to focus on",
    )
    # RL-specific fixed settings (not part of tuning space)
    trading_mode: Optional[str] = Field(
        default=None, pattern="^(stock|margin)$",
        description="Market type: stock (no leverage) or margin (3x leverage). RL only.",
    )
    agent_strategy: Optional[str] = Field(
        default=None, pattern="^(AGGR|CONS|BALA|SCAL)$",
        description="Agent strategy: AGGR, CONS, BALA, SCAL. RL only.",
    )
    initial_balance: Optional[float] = Field(
        default=None, ge=100, le=1_000_000,
        description="Starting balance in USD for RL training.",
    )
    # ML-59: HPO settings (RL only)
    enable_hpo: Optional[bool] = Field(
        default=None,
        description="Enable Optuna HPO screening phase before LLM refinement. RL only.",
    )
    hpo_trials: Optional[int] = Field(
        default=None, ge=5, le=200,
        description="Number of Optuna trials for HPO screening (default: 20). RL only.",
    )
    hpo_timesteps: Optional[int] = Field(
        default=None, ge=10000, le=500000,
        description="Timesteps per HPO trial (default: 50000). RL only.",
    )
    # ML-63: Pipeline settings
    phase_budgets: Optional[Dict[str, int]] = Field(
        default=None,
        description=(
            "Per-phase iteration budget for pipeline mode: "
            "{direction: N, volatility: N, rl: N}"
        ),
    )
    manifest: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional research-session manifest overrides. Immutable identity "
            "fields must still match the server-generated session."
        ),
    )

    @field_validator("phase_budgets")
    @classmethod
    def validate_phase_budgets(cls, value: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]:
        return _validate_phase_budgets(value)


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/research/start", status_code=201)
async def start_research(request: Request, req: StartResearchRequest):
    metadata = _start_metadata(req)
    try:
        # ML-63: Route pipeline requests to the pipeline controller
        if req.model_type == "pipeline":
            pipeline = await _session_manager.start_pipeline(
                instrument=req.instrument,
                timeframe=req.timeframe,
                tag=req.tag,
                quick_mode=req.quick_mode,
                max_iterations=req.max_iterations,
                max_budget_usd=req.max_budget_usd,
                timeout_minutes=req.timeout_minutes,
                focus_hint=req.focus_hint,
                phase_budgets=req.phase_budgets,
                trading_mode=req.trading_mode,
                agent_strategy=req.agent_strategy,
                initial_balance=req.initial_balance,
                enable_hpo=req.enable_hpo,
                hpo_trials=req.hpo_trials,
                hpo_timesteps=req.hpo_timesteps,
            )
            await _audit(
                request,
                action="pipeline.start",
                outcome="success",
                pipeline_id=pipeline.get("id"),
                metadata=metadata,
            )
            return pipeline
        session = await _session_manager.start_session(
            instrument=req.instrument,
            timeframe=req.timeframe,
            model_type=req.model_type,
            tag=req.tag,
            quick_mode=req.quick_mode,
            max_iterations=req.max_iterations,
            max_budget_usd=req.max_budget_usd,
            timeout_minutes=req.timeout_minutes,
            focus_hint=req.focus_hint,
            trading_mode=req.trading_mode,
            agent_strategy=req.agent_strategy,
            initial_balance=req.initial_balance,
            enable_hpo=req.enable_hpo,
            hpo_trials=req.hpo_trials,
            hpo_timesteps=req.hpo_timesteps,
            manifest=req.manifest,
        )
        await _audit(
            request,
            action="research.start",
            outcome="success",
            research_id=session.get("id"),
            metadata=metadata,
        )
        return session
    except RuntimeError as e:
        await _audit(
            request,
            action="pipeline.start" if req.model_type == "pipeline" else "research.start",
            outcome="failure",
            metadata=metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/research")
async def list_research(
    status: Optional[str] = None,
    model_type: Optional[str] = None,
    instrument: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Phase 5.1: paginated session listing."""

    items = await _store.list_sessions(
        status=status, model_type=model_type, instrument=instrument,
        limit=limit, offset=offset,
    )
    total = await _store.count_sessions(
        status=status, model_type=model_type, instrument=instrument,
    )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit-events")
async def list_audit_events(
    limit: int = 100,
    action: Optional[str] = None,
    research_id: Optional[str] = None,
    pipeline_id: Optional[str] = None,
):
    events = await _store.list_audit_events(
        limit=limit,
        action=action,
        research_id=research_id,
        pipeline_id=pipeline_id,
    )
    # Phase 5.3: redact the SHA256 fingerprint suffix in actor_id so the
    # full hash never leaves the service. We keep the prefix so operators
    # can correlate events from the same caller across the audit log,
    # but truncate enough that the full digest cannot be reconstructed.
    for event in events:
        actor_id = event.get("actor_id")
        if (
            isinstance(actor_id, str)
            and actor_id.startswith("token_sha256:")
            and len(actor_id) > len("token_sha256:") + 12
        ):
            prefix = actor_id[: len("token_sha256:") + 8]
            event["actor_id"] = f"{prefix}…"
    return events


@router.get("/research/{research_id}")
async def get_research(research_id: str):
    # ML-63: Check pipelines first if ID starts with pipe_
    if research_id.startswith("pipe_"):
        pipe = await _store.get_pipeline(research_id)
        if pipe:
            payload = dict(pipe)
            payload.setdefault("model_type", "pipeline")
            payload.setdefault("skill_name", "pipeline")
            payload.setdefault("workspace_path", "")
            payload.setdefault("best_iteration", None)
            payload.setdefault("best_metric", None)
            payload.setdefault("resumed_from", None)

            current_phase = pipe.get("current_phase")
            if current_phase in ("direction", "volatility", "rl"):
                session_id = pipe.get(f"{current_phase}_session_id")
                if session_id:
                    session = await _store.get_session(session_id)
                    if session:
                        payload["workspace_path"] = session.get("workspace_path", "")
                        payload["active_phase_session_id"] = session.get("id")
            return payload
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/research/{research_id}/stop")
async def stop_research(request: Request, research_id: str):
    # ML-63: Handle pipeline stop
    if research_id.startswith("pipe_"):
        ok = await _session_manager.stop_pipeline(research_id)
        if ok:
            await _audit(
                request,
                action="pipeline.stop",
                outcome="success",
                pipeline_id=research_id,
            )
            return {"status": "stop_requested", "pipeline_id": research_id}
        await _audit(
            request,
            action="pipeline.stop",
            outcome="failure",
            pipeline_id=research_id,
            error_message="Session not found or not running",
        )
        raise HTTPException(
            status_code=404, detail="Session not found or not running",
        )
    ok = await _session_manager.stop_session(research_id)
    if not ok:
        await _audit(
            request,
            action="research.stop",
            outcome="failure",
            research_id=research_id,
            error_message="Session not found or not running",
        )
        raise HTTPException(
            status_code=404, detail="Session not found or not running",
        )
    await _audit(
        request,
        action="research.stop",
        outcome="success",
        research_id=research_id,
    )
    return {"status": "stop_requested", "research_id": research_id}


@router.post("/research/{research_id}/pause")
async def pause_research(request: Request, research_id: str):
    ok = await _session_manager.pause_session(research_id)
    if not ok:
        await _audit(
            request,
            action="research.pause",
            outcome="failure",
            research_id=research_id,
            error_message="Session not found or not running",
        )
        raise HTTPException(
            status_code=404, detail="Session not found or not running",
        )
    await _audit(
        request,
        action="research.pause",
        outcome="success",
        research_id=research_id,
    )
    return {"status": "paused", "research_id": research_id}


@router.post("/research/{research_id}/resume")
async def resume_research(request: Request, research_id: str):
    ok = await _session_manager.resume_session(research_id)
    if not ok:
        await _audit(
            request,
            action="research.resume",
            outcome="failure",
            research_id=research_id,
            error_message="Session not found or not running",
        )
        raise HTTPException(
            status_code=404, detail="Session not found or not running",
        )
    await _audit(
        request,
        action="research.resume",
        outcome="success",
        research_id=research_id,
    )
    return {"status": "running", "research_id": research_id}


class ContinueResearchRequest(BaseModel):
    """ML-62: Request body for continuing a timed-out/completed session."""
    max_iterations: Optional[int] = Field(default=None, ge=1, le=500)
    max_budget_usd: Optional[float] = Field(default=None, ge=0.1, le=500.0)
    timeout_minutes: Optional[int] = Field(
        default=None, ge=30, le=1440,
        description="Session timeout in minutes",
    )
    focus_hint: Optional[str] = Field(
        default=None, max_length=1000,
        description="Optional hint for what to focus on in the continuation",
    )


class RuntimeResumeRequest(ContinueResearchRequest):
    """Explicit operator action for resuming a restart-recovered session."""

    reason: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Operator reason for resuming the interrupted session.",
    )
    allow_interrupted: bool = Field(
        default=False,
        description="Allow resume from interrupted state when evidence is incomplete.",
    )


@router.post("/research/{research_id}/continue", status_code=201)
async def continue_research(
    request: Request,
    research_id: str,
    req: ContinueResearchRequest = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """ML-62: Continue a timed-out or completed session as a new chained session.

    Creates a new session that inherits all settings from the parent and
    picks up where it left off — workspace is preserved, no setup/baseline
    re-run.
    """
    if req is None:
        req = ContinueResearchRequest()
    metadata = _continue_metadata(req)
    try:
        # ML-63: Handle pipeline continue
        if research_id.startswith("pipe_"):
            pipeline = await _run_idempotent(
                operation="pipeline.continue",
                parent_id=research_id,
                key=idempotency_key,
                request_payload=req.model_dump(),
                call=lambda: _session_manager.continue_pipeline(
                    research_id,
                    max_iterations=req.max_iterations,
                    max_budget_usd=req.max_budget_usd,
                    timeout_minutes=req.timeout_minutes,
                    focus_hint=req.focus_hint,
                ),
            )
            await _audit(
                request,
                action="pipeline.continue",
                outcome="success",
                pipeline_id=research_id,
                metadata={**metadata, "continued_pipeline_id": pipeline.get("id")},
            )
            return pipeline
        session = await _run_idempotent(
            operation="research.continue",
            parent_id=research_id,
            key=idempotency_key,
            request_payload=req.model_dump(),
            call=lambda: _session_manager.continue_session(
                research_id,
                max_iterations=req.max_iterations,
                max_budget_usd=req.max_budget_usd,
                timeout_minutes=req.timeout_minutes,
                focus_hint=req.focus_hint,
            ),
        )
        await _audit(
            request,
            action="research.continue",
            outcome="success",
            research_id=research_id,
            metadata={**metadata, "continued_research_id": session.get("id")},
        )
        return session
    except RuntimeError as e:
        await _audit(
            request,
            action=(
                "pipeline.continue"
                if research_id.startswith("pipe_")
                else "research.continue"
            ),
            outcome="failure",
            research_id=None if research_id.startswith("pipe_") else research_id,
            pipeline_id=research_id if research_id.startswith("pipe_") else None,
            metadata=metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/research/{research_id}/runtime-resume", status_code=201)
async def runtime_resume_research(
    request: Request,
    research_id: str,
    req: RuntimeResumeRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Resume a restart-recovered session only after explicit operator action."""
    metadata = _runtime_resume_metadata(req)
    try:
        session = await _run_idempotent(
            operation="research.runtime_resume",
            parent_id=research_id,
            key=idempotency_key,
            request_payload=req.model_dump(),
            call=lambda: _session_manager.resume_interrupted_session(
                research_id,
                reason=req.reason,
                allow_interrupted=req.allow_interrupted,
                max_iterations=req.max_iterations,
                max_budget_usd=req.max_budget_usd,
                timeout_minutes=req.timeout_minutes,
                focus_hint=req.focus_hint,
            ),
        )
        await _audit(
            request,
            action="research.runtime_resume",
            outcome="success",
            research_id=research_id,
            metadata={**metadata, "continued_research_id": session.get("id")},
        )
        return session
    except RuntimeError as e:
        await _audit(
            request,
            action="research.runtime_resume",
            outcome="failure",
            research_id=research_id,
            metadata=metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/research/{research_id}")
async def delete_research(request: Request, research_id: str):
    if _session_manager.is_running(research_id):
        await _audit(
            request,
            action="research.delete",
            outcome="failure",
            research_id=research_id,
            error_message="Cannot delete a running session — stop it first",
        )
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a running session — stop it first",
        )
    ok = await _store.delete_session(research_id)
    if not ok:
        await _audit(
            request,
            action="research.delete",
            outcome="failure",
            research_id=research_id,
            error_message="Session not found",
        )
        raise HTTPException(status_code=404, detail="Session not found")
    await _audit(
        request,
        action="research.delete",
        outcome="success",
        research_id=research_id,
    )
    return {"status": "deleted", "research_id": research_id}


@router.get("/instruments")
async def list_instruments():
    """List available instruments from configs/instrument_configs/*.yaml."""
    instrument_dir = os.path.join(settings.configs_dir, "instrument_configs")
    instruments = []
    if os.path.isdir(instrument_dir):
        for path in sorted(glob.glob(os.path.join(instrument_dir, "*.yaml"))):
            filename = os.path.basename(path)
            name = filename.rsplit(".", 1)[0]  # e.g. DOGE_USDT_15m
            # Try to split into instrument + timeframe
            parts = name.rsplit("_", 1)
            if len(parts) == 2 and parts[1] in (
                "1m", "5m", "15m", "30m", "1h", "4h", "1d",
            ):
                instruments.append({
                    "name": name,
                    "instrument": "_".join(parts[0].split("_")[:2]),
                    "timeframe": parts[1],
                })
            else:
                instruments.append({"name": name, "instrument": name, "timeframe": "unknown"})

    # Also check RL configs (ML-67: handle new naming with strategy+market)
    rl_dir = os.path.join(settings.configs_dir, "rl")
    _valid_strats = {"AGGR", "CONS", "BALA", "SCAL"}
    _valid_mkts = {"stock", "margin"}
    if os.path.isdir(rl_dir):
        for path in sorted(glob.glob(os.path.join(rl_dir, "*_production.yaml"))):
            filename = os.path.basename(path)
            stem = filename.replace("_production.yaml", "")
            parts = stem.split("_")

            # Try new format: {BASE}_{QUOTE}_{TF}_{STRAT}_{MKT}
            instrument = None
            timeframe = None
            strategy = None
            if (len(parts) >= 5
                    and parts[-2].upper() in _valid_strats
                    and parts[-1].lower() in _valid_mkts):
                instrument = "_".join(parts[:-3])
                timeframe = parts[-3]
                strategy = parts[-2].upper()
            elif len(parts) >= 3:
                # Legacy: {BASE}_{QUOTE}_{TF}
                timeframe = parts[-1]
                instrument = "_".join(parts[:-1])

            display_name = stem
            # Avoid duplicates
            if instrument and not any(i["name"] == display_name for i in instruments):
                entry = {
                    "name": display_name,
                    "instrument": instrument,
                    "timeframe": timeframe or "unknown",
                }
                if strategy:
                    entry["strategy"] = strategy
                instruments.append(entry)

    return instruments


@router.get("/models")
async def list_models():
    return [
        {"id": "direction", "name": "Direction", "skill": "direction-autotuner"},
        {"id": "volatility", "name": "Volatility", "skill": "volatility-autotuner"},
        {"id": "rl", "name": "RL (PPO)", "skill": "rl-autotuner"},
        {"id": "pipeline", "name": "Pipeline (dir→vol→rl)", "skill": "pipeline"},
    ]


# ------------------------------------------------------------------
# ML-63: Pipeline-specific endpoints
# ------------------------------------------------------------------


@router.get("/pipelines")
async def list_pipelines(
    status: Optional[str] = None,
    instrument: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Phase 5.1: paginated pipeline listing."""

    items = await _store.list_pipelines(
        status=status, instrument=instrument, limit=limit, offset=offset,
    )
    total = await _store.count_pipelines(status=status, instrument=instrument)
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/status")
async def system_status():
    return {
        "active_sessions": _session_manager.active_count,
        "active_pipelines": len(_session_manager._active_pipelines),
        "max_concurrent": settings.max_concurrent_sessions,
        "anthropic_model": settings.anthropic_model,
        "default_quick_mode": settings.default_quick_mode,
        "max_iterations": settings.max_iterations,
        "max_budget_usd": settings.max_budget_usd,
        "service_urls": {
            "data_ingest": settings.data_ingest_url,
            "ensemble_trainer": settings.ensemble_trainer_url,
            "feature_service": settings.feature_service_url,
            "vdmc_indicator": settings.vdmc_indicator_url,
            "rl_trainer": settings.rl_trainer_url,
            "mlflow_tracking": settings.mlflow_tracking_uri,
            "mlflow_service": settings.mlflow_service_url,
            "mlflow_external": settings.mlflow_external_url,
            "admin_service": settings.admin_service_url,
            "promotion_api": settings.promotion_service_url,
        },
        "persistence": {
            "db_path": settings.db_path,
            "runs_dir": settings.runs_dir,
            "host_configs_path": settings.host_configs_path,
        },
    }
