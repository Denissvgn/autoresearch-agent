"""Immutable research-session manifests for autoresearch runs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from server.config import settings
from server.core.service_preflight import build_not_run_preflight, sanitize_service_url


class ResearchSessionManifest(BaseModel):
    """Complete immutable manifest for one autonomous research session."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "research_session_manifest.v1"
    research_id: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    instrument: str
    timeframe: str
    model_type: str = Field(pattern="^(direction|volatility|rl)$")
    objective: str
    model_family: str
    data_window: Dict[str, Any]
    baseline_config: Dict[str, Any]
    roster: Dict[str, Any]
    tsfm: Dict[str, Any]
    adaptive_features: Dict[str, Any]
    split_ids: Dict[str, Any]
    cost_model: Dict[str, Any]
    gate_bundle: Dict[str, Any]
    budget: Dict[str, Any]
    max_iterations: int = Field(ge=1)
    timeout_s: int = Field(ge=0)
    mlflow_experiment: str
    promotion_policy: Dict[str, Any]
    service_urls: Dict[str, str]
    preflight: Dict[str, Any]
    runtime: Dict[str, Any]
    hpo: Dict[str, Any] = Field(default_factory=dict)
    focus_hint: Optional[str] = None
    manifest_hash: Optional[str] = None

    @field_validator("instrument", "timeframe", "objective", "model_family")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("field must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def _require_manifest_sections(self) -> "ResearchSessionManifest":
        required = (
            "data_window",
            "baseline_config",
            "roster",
            "tsfm",
            "adaptive_features",
            "split_ids",
            "cost_model",
            "gate_bundle",
            "budget",
            "promotion_policy",
            "service_urls",
            "preflight",
            "runtime",
        )
        missing = [name for name in required if not getattr(self, name)]
        if missing:
            raise ValueError(f"manifest missing required section(s): {missing}")
        return self

    def canonical_json(self, *, include_hash: bool = True) -> str:
        payload = self.model_dump(mode="json")
        if not include_hash:
            payload.pop("manifest_hash", None)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def with_hash(self) -> "ResearchSessionManifest":
        payload = self.model_copy(update={"manifest_hash": None})
        digest = hashlib.sha256(
            payload.canonical_json(include_hash=False).encode("utf-8")
        ).hexdigest()
        return payload.model_copy(update={"manifest_hash": digest})


def build_research_manifest(
    *,
    research_id: str,
    instrument: str,
    timeframe: str,
    model_type: str,
    tag: str,
    quick_mode: bool,
    max_iterations: int,
    max_budget_usd: float,
    timeout_s: int,
    focus_hint: Optional[str],
    trading_mode: Optional[str],
    agent_strategy: Optional[str],
    initial_balance: Optional[float],
    enable_hpo: bool,
    hpo_trials: int,
    hpo_timesteps: int,
    overrides: Optional[Dict[str, Any]] = None,
) -> ResearchSessionManifest:
    """Build and validate a complete manifest from request/server state."""

    instrument_under = instrument.replace("-", "_")
    defaults = {
        "research_id": research_id,
        "instrument": instrument,
        "timeframe": timeframe,
        "model_type": model_type,
        "objective": _default_objective(model_type),
        "model_family": _default_model_family(model_type),
        "data_window": {
            "source": "experiment_matrix_v1",
            "matrix_path": "reports/direction-tuning/experiment_matrix_v1.yaml",
            "instrument": instrument,
            "timeframe": timeframe,
            "quick_mode": quick_mode,
        },
        "baseline_config": {
            "tag": tag,
            "workspace_config": (
                f"runs/autotuner/{instrument_under}_{timeframe}/"
                f"{model_type}/train.yaml"
            ),
        },
        "roster": {
            "source": "config_snapshot",
            "model_type": model_type,
        },
        "tsfm": {
            "enabled": False,
            "source": None,
            "weights": None,
            "license": None,
        },
        "adaptive_features": {
            "enabled": False,
            "version": None,
        },
        "split_ids": {
            "source": "experiment_matrix_v1",
            "value": None,
        },
        "cost_model": {
            "source": "experiment_matrix_v1",
            "fee_slippage_spread": "matrix_defined",
        },
        "gate_bundle": {
            "id": "development_direction_prediction_v1",
            "version": 1,
            "path": "reports/direction-tuning/promotion/development_gate_bundle_v1.yaml",
        },
        "budget": {
            "max_budget_usd": max_budget_usd,
            "quick_mode": quick_mode,
        },
        "max_iterations": max_iterations,
        "timeout_s": timeout_s,
        "mlflow_experiment": f"autoresearch/{instrument_under}/{timeframe}/{model_type}",
        "promotion_policy": {
            "scope": "development",
            "live_production_promotion_allowed": False,
            "auc_only_promotion_allowed": False,
        },
        "service_urls": {
            "ensemble_trainer": sanitize_service_url(settings.ensemble_trainer_url),
            "rl_trainer": sanitize_service_url(settings.rl_trainer_url),
            "feature_service": sanitize_service_url(settings.feature_service_url),
            "data_ingest": sanitize_service_url(settings.data_ingest_url),
            "mlflow_tracking": sanitize_service_url(settings.mlflow_tracking_uri),
            "mlflow_service": sanitize_service_url(settings.mlflow_service_url),
            "mlflow_external": sanitize_service_url(settings.mlflow_external_url),
            "admin_service": sanitize_service_url(settings.admin_service_url),
            "promotion_api": sanitize_service_url(settings.promotion_service_url),
        },
        "preflight": build_not_run_preflight(),
        "runtime": {
            "environment": settings.environment,
            "workspace_root": settings.workspace_root,
            "runs_dir": settings.runs_dir,
            "db_path": settings.db_path,
            "host_configs_path": settings.host_configs_path,
            "anthropic_model": settings.anthropic_model,
            "trading_mode": trading_mode,
            "agent_strategy": agent_strategy,
            "initial_balance": initial_balance,
        },
        "hpo": {
            "enabled": enable_hpo,
            "trials": hpo_trials if enable_hpo else None,
            "timesteps": hpo_timesteps if enable_hpo else None,
        },
        "focus_hint": focus_hint,
    }
    payload = _deep_merge(defaults, overrides or {})
    if payload.get("research_id") != research_id:
        raise ValueError("manifest research_id must match server session id")
    if payload.get("instrument") != instrument:
        raise ValueError("manifest instrument must match request instrument")
    if payload.get("timeframe") != timeframe:
        raise ValueError("manifest timeframe must match request timeframe")
    if payload.get("model_type") != model_type:
        raise ValueError("manifest model_type must match request model_type")
    return ResearchSessionManifest(**payload).with_hash()


def manifest_pretty_json(manifest: ResearchSessionManifest) -> str:
    return json.dumps(
        manifest.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    ) + "\n"


def _default_objective(model_type: str) -> str:
    return {
        "direction": "improve calibrated direction_proba for development promotion",
        "volatility": "improve calibrated volatility_proba for development promotion",
        "rl": "improve PPO OOS trading robustness using honest predictive inputs",
    }.get(model_type, f"improve {model_type} model")


def _default_model_family(model_type: str) -> str:
    return {
        "direction": "stacked_tabular_direction",
        "volatility": "stacked_tabular_volatility",
        "rl": "ppo_trading_agent",
    }.get(model_type, model_type)


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if (
            isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
