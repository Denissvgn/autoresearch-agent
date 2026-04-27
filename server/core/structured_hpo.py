"""Structured HPO plan helpers for autoresearch sessions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict


DIRECTION_SEARCH_SPACE: Dict[str, Any] = {
    "prediction_horizon": [3, 4, 6, 8, 12],
    "deadzone_width": [0.0005, 0.001, 0.0015, 0.002],
    "roster": ["baseline", "expanded_tabular", "tabular_plus_tsfm_adapter"],
    "calibration": ["isotonic", "sigmoid", "none"],
    "threshold": {"low": 0.50, "high": 0.70, "step": 0.02},
    "adaptive_features": [False, True],
}

VOLATILITY_SEARCH_SPACE: Dict[str, Any] = {
    "prediction_horizon": [3, 4, 6, 8],
    "atr_mult": [1.0, 1.25, 1.5, 2.0],
    "roster": ["baseline", "expanded_tabular"],
    "calibration": ["isotonic", "sigmoid", "none"],
    "threshold": {"low": 0.50, "high": 0.75, "step": 0.025},
    "adaptive_features": [False, True],
}

RL_SEARCH_SPACE: Dict[str, Any] = {
    "source": "scripts/autotuner/rl/prepare.py --hpo",
    "sampler": "optuna_tpe",
    "searched_groups": [
        "ppo_training",
        "environment_risk",
        "reward_weights",
    ],
}


def build_structured_hpo_plan(
    *,
    research_id: str,
    model_type: str,
    quick_mode: bool,
    max_iterations: int,
    max_budget_usd: float,
    timeout_s: int,
    enable_hpo: bool,
    hpo_trials: int,
    hpo_timesteps: int,
) -> Dict[str, Any]:
    """Build a bounded HPO plan for manifest, DB, API, and UI state."""

    max_trials = _bounded_trials(model_type, max_iterations, enable_hpo, hpo_trials)
    plan = {
        "schema_version": "autoresearch_structured_hpo_plan.v1",
        "research_id": research_id,
        "study_id": f"hpo_{research_id}_{model_type}",
        "model_type": model_type,
        "enabled": bool(enable_hpo),
        "status": "planned" if enable_hpo else "disabled",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "max_trials": max_trials,
        "timeout_s": timeout_s,
        "quick_mode": quick_mode,
        "budget": {
            "max_iterations": max_iterations,
            "max_budget_usd": max_budget_usd,
            "trial_budget_fraction": 0.5 if model_type in {"direction", "volatility"} else 0.35,
        },
        "search_space": _search_space(model_type),
        "execution": _execution(model_type, hpo_timesteps),
    }
    plan["plan_hash"] = _hash(plan)
    return plan


def hpo_plan_json(plan: Dict[str, Any]) -> str:
    return json.dumps(plan, sort_keys=True)


def _bounded_trials(
    model_type: str,
    max_iterations: int,
    enable_hpo: bool,
    requested_trials: int,
) -> int:
    if not enable_hpo:
        return 0
    if requested_trials <= 0:
        return 0
    if model_type == "rl":
        return min(requested_trials, 200)
    if max_iterations <= 0:
        return 0
    return min(requested_trials, max_iterations, 40)


def _search_space(model_type: str) -> Dict[str, Any]:
    if model_type == "direction":
        return DIRECTION_SEARCH_SPACE
    if model_type == "volatility":
        return VOLATILITY_SEARCH_SPACE
    if model_type == "rl":
        return RL_SEARCH_SPACE
    return {}


def _execution(model_type: str, hpo_timesteps: int) -> Dict[str, Any]:
    if model_type == "rl":
        return {
            "mode": "optuna_prepare_py",
            "hpo_timesteps": hpo_timesteps,
            "result_path": "hpo_results.json",
        }
    return {
        "mode": "agent_bounded_sweep",
        "result_path": "server_hpo_plan.json",
        "enforced_by": "manifest_budget_and_iteration_cap",
    }


def _hash(plan: Dict[str, Any]) -> str:
    payload = dict(plan)
    payload.pop("plan_hash", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
