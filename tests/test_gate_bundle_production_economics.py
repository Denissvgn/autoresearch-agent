
"""MQ-B5 — production-scope unconditional post-cost economic gate.

Pins (development_gate_bundle.evaluate_development_gate_bundle):
1. PRODUCTION scope: a worsening post-cost replay BLOCKS even when the bundle
   YAML lacks `worsening_vs_baseline_blocks_promotion` AND the iteration
   carries a matching waiver (unconditional + unwaivable).
2. DEVELOPMENT scope: legacy behavior preserved — the check runs only when the
   YAML flag is set, and a waiver still bypasses it.
3. Both the direction path and the RL path enforce the production rule.
"""
from __future__ import annotations

import json
import os
import sys
import types
from types import ModuleType
from typing import cast

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

try:  # the orchestrator imports Anthropic SDK at module load
    import anthropic  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover — only needed in slim test envs
    _stub = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = cast(ModuleType, _stub)
from src.core.development_gate_bundle import (  # noqa: E402
    evaluate_development_gate_bundle,
)

WORSENING_REPLAY = {
    "schema_version": "rl_economic_replay.v1",
    "rl_profit_score": -0.4,
    "metrics": {
        "post_cost_return": -0.03,
        "max_drawdown": 0.10,
        "sharpe": -0.2,
        "trade_count": 120,
        "turnover": 5.0,
        "hit_rate": 0.45,
        "average_trade_return": -0.00025,
    },
    "assumptions": {"fee_bps": 5.0, "spread_bps": 2.0, "slippage_bps": 2.0},
    "artifact_hash": "deadbeef",
    "comparison": {
        "baseline_post_cost_return": 0.0,
        "post_cost_return_delta_vs_baseline": -0.03,
        "post_cost_sharpe_delta_vs_baseline": -0.2,
    },
    "gates": {
        "all_gates_passed": False,
        "worsening_vs_baseline": True,
        "metrics": {"post_cost_return_delta_vs_baseline": -0.03},
    },
}


def _rl_iteration(*, waive: bool = False) -> dict:
    payload = {
        "rl_economic_replay": WORSENING_REPLAY,
        "finalist": True,
    }
    if waive:
        payload["gate_waivers"] = ["worsening_post_cost_replay"]
    return {"metrics_json": json.dumps(payload)}


def _bundle(scope: str, *, with_flag: bool) -> dict:
    checks = {
        "post_cost_metrics_required": True,
        "replay_assumptions_required": True,
        "profit_score_required": True,
        "replay_artifact_hash_required": True,
    }
    if with_flag:
        checks["worsening_vs_baseline_blocks_promotion"] = True
    return {
        "gate_bundle_id": f"test_bundle_{scope}",
        "version": 1,
        "scope": scope,
        "promotion_policy": {"live_production_promotion_allowed": False},
        "gate_tiers": {"economic_replay": {"required": True, "checks": checks}},
    }


def _check(result: dict, name: str) -> dict | None:
    for check in result["checks"]:
        if check["name"] == name:
            return check
    return None


def test_production_scope_blocks_worsening_without_yaml_flag() -> None:
    result = evaluate_development_gate_bundle(
        bundle=_bundle("production", with_flag=False),
        model_type="rl",
        best_iteration=_rl_iteration(),
    )
    check = _check(result, "rl_economic_replay_not_worse_than_baseline")
    assert check is not None, "production scope must run the worsening check unconditionally"
    assert check["status"] == "failed"
    assert "worsening_post_cost_replay" in result["blockers"]
    assert result["passed"] is False


def test_production_scope_ignores_waiver() -> None:
    result = evaluate_development_gate_bundle(
        bundle=_bundle("production", with_flag=True),
        model_type="rl",
        best_iteration=_rl_iteration(waive=True),
    )
    check = _check(result, "rl_economic_replay_not_worse_than_baseline")
    assert check is not None
    assert check["status"] == "failed", "production economics must be unwaivable"
    assert "worsening_post_cost_replay" in result["blockers"]


def test_development_scope_without_flag_skips_check() -> None:
    result = evaluate_development_gate_bundle(
        bundle=_bundle("development", with_flag=False),
        model_type="rl",
        best_iteration=_rl_iteration(),
    )
    check = _check(result, "rl_economic_replay_not_worse_than_baseline")
    assert check is None, "development scope without the YAML flag keeps legacy behavior"


def test_development_scope_waiver_still_works() -> None:
    result = evaluate_development_gate_bundle(
        bundle=_bundle("development", with_flag=True),
        model_type="rl",
        best_iteration=_rl_iteration(waive=True),
    )
    check = _check(result, "rl_economic_replay_not_worse_than_baseline")
    assert check is not None
    assert check["status"] == "waived", "development waivers must keep working"
    assert "worsening_post_cost_replay" not in result["blockers"]