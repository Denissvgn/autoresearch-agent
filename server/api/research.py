"""Research session management endpoints."""

from __future__ import annotations

import glob
import os
from typing import Optional

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
    model_type: str = Field(..., pattern="^(direction|volatility|rl)$")
    tag: str = Field(..., examples=["doge-apr01"])
    quick_mode: Optional[bool] = Field(
        default=None,
        description="If null, uses server default (standard/full mode)",
    )
    max_iterations: Optional[int] = Field(default=None, ge=1, le=100)
    max_budget_usd: Optional[float] = Field(default=None, ge=0.1, le=100.0)
    focus_hint: Optional[str] = Field(
        default=None, max_length=1000,
        description="Optional hint for the agent about what to focus on",
    )


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/research/start", status_code=201)
async def start_research(req: StartResearchRequest):
    try:
        session = await _session_manager.start_session(
            instrument=req.instrument,
            timeframe=req.timeframe,
            model_type=req.model_type,
            tag=req.tag,
            quick_mode=req.quick_mode,
            max_iterations=req.max_iterations,
            max_budget_usd=req.max_budget_usd,
            focus_hint=req.focus_hint,
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
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/research/{research_id}/stop")
async def stop_research(research_id: str):
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

    # Also check RL configs
    rl_dir = os.path.join(settings.configs_dir, "rl")
    if os.path.isdir(rl_dir):
        for path in sorted(glob.glob(os.path.join(rl_dir, "*_production.yaml"))):
            filename = os.path.basename(path)
            name = filename.replace("_production.yaml", "")
            # Avoid duplicates
            if not any(i["name"] == name for i in instruments):
                parts = name.rsplit("_", 1)
                if len(parts) == 2:
                    instruments.append({
                        "name": name,
                        "instrument": "_".join(parts[0].split("_")[:2]),
                        "timeframe": parts[1],
                    })

    return instruments


@router.get("/models")
async def list_models():
    return [
        {"id": "direction", "name": "Direction", "skill": "direction-autotuner"},
        {"id": "volatility", "name": "Volatility", "skill": "volatility-autotuner"},
        {"id": "rl", "name": "RL (PPO)", "skill": "rl-autotuner"},
    ]


@router.get("/status")
async def system_status():
    return {
        "active_sessions": _session_manager.active_count,
        "max_concurrent": settings.max_concurrent_sessions,
        "anthropic_model": settings.anthropic_model,
        "default_quick_mode": settings.default_quick_mode,
        "max_iterations": settings.max_iterations,
        "max_budget_usd": settings.max_budget_usd,
    }
