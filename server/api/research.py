"""Research session management endpoints."""

from __future__ import annotations

import glob
import os
from typing import Any, Dict, Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.config import settings

router = APIRouter(prefix="/api", tags=["research"])

# These will be injected by main.py
_session_manager = None
_store = None


def init(session_manager, store):
    global _session_manager, _store
    _session_manager = session_manager
    _store = store


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
        description="Per-phase iteration budget for pipeline mode: {direction: N, volatility: N, rl: N}",
    )
    manifest: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional research-session manifest overrides. Immutable identity "
            "fields must still match the server-generated session."
        ),
    )


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/research/start", status_code=201)
async def start_research(req: StartResearchRequest):
    try:
        # ML-63: Route pipeline requests to the pipeline controller
        if req.model_type == "pipeline":
            return await _session_manager.start_pipeline(
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
        return session
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/research")
async def list_research(
    status: Optional[str] = None,
    model_type: Optional[str] = None,
    instrument: Optional[str] = None,
):
    return await _store.list_sessions(
        status=status, model_type=model_type, instrument=instrument,
    )


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
async def stop_research(research_id: str):
    # ML-63: Handle pipeline stop
    if research_id.startswith("pipe_"):
        ok = await _session_manager.stop_pipeline(research_id)
        if ok:
            return {"status": "stop_requested", "pipeline_id": research_id}
    ok = await _session_manager.stop_session(research_id)
    if not ok:
        raise HTTPException(
            status_code=404, detail="Session not found or not running",
        )
    return {"status": "stop_requested", "research_id": research_id}


@router.post("/research/{research_id}/pause")
async def pause_research(research_id: str):
    ok = await _session_manager.pause_session(research_id)
    if not ok:
        raise HTTPException(
            status_code=404, detail="Session not found or not running",
        )
    return {"status": "paused", "research_id": research_id}


@router.post("/research/{research_id}/resume")
async def resume_research(research_id: str):
    ok = await _session_manager.resume_session(research_id)
    if not ok:
        raise HTTPException(
            status_code=404, detail="Session not found or not running",
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


@router.post("/research/{research_id}/continue", status_code=201)
async def continue_research(research_id: str, req: ContinueResearchRequest = None):
    """ML-62: Continue a timed-out or completed session as a new chained session.

    Creates a new session that inherits all settings from the parent and
    picks up where it left off — workspace is preserved, no setup/baseline
    re-run.
    """
    if req is None:
        req = ContinueResearchRequest()
    try:
        # ML-63: Handle pipeline continue
        if research_id.startswith("pipe_"):
            return await _session_manager.continue_pipeline(
                research_id,
                max_iterations=req.max_iterations,
                max_budget_usd=req.max_budget_usd,
                timeout_minutes=req.timeout_minutes,
                focus_hint=req.focus_hint,
            )
        session = await _session_manager.continue_session(
            research_id,
            max_iterations=req.max_iterations,
            max_budget_usd=req.max_budget_usd,
            timeout_minutes=req.timeout_minutes,
            focus_hint=req.focus_hint,
        )
        return session
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/research/{research_id}")
async def delete_research(research_id: str):
    if _session_manager.is_running(research_id):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a running session — stop it first",
        )
    ok = await _store.delete_session(research_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
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
):
    return await _store.list_pipelines(status=status, instrument=instrument)


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
