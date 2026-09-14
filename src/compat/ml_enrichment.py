"""Legacy ML enrichment helpers (moved to src/compat — P1-2).

Historical trading-skill metric projection: RL economic-replay summaries and
feature-readiness metrics for pre-migration DB rows. Nothing here may grow
new features; the domain-neutral runtime never calls these for new skills.
Kept verbatim from ``src/api/results.py`` so old sessions still render.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def _first_number(*values: Any) -> Optional[float]:
    for value in values:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _rl_economic_replay(metrics: Dict[str, Any]) -> Dict[str, Any]:
    rl_oos = metrics.get("rl_oos") if isinstance(metrics.get("rl_oos"), dict) else {}
    replay = (
        metrics.get("rl_economic_replay")
        or metrics.get("economic_replay")
        or metrics.get("replay")
        or rl_oos.get("rl_economic_replay")
        or rl_oos.get("economic_replay")
    )
    return replay if isinstance(replay, dict) else {}


def _rl_economic_replay_summary(
    metrics: Dict[str, Any],
    attempt_snapshot: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    replay = _rl_economic_replay(metrics)
    if not replay:
        return None
    replay_metrics = (
        replay.get("metrics")
        if isinstance(replay.get("metrics"), dict)
        else replay.get("post_cost_metrics")
        if isinstance(replay.get("post_cost_metrics"), dict)
        else {}
    )
    return {
        "schema_version": replay.get("schema_version"),
        "rl_profit_score": _first_number(
            replay.get("rl_profit_score"),
            metrics.get("rl_profit_score"),
        ),
        "post_cost_return": _first_number(
            replay_metrics.get("post_cost_return"),
            replay_metrics.get("mean_oos_return"),
            metrics.get("mean_oos_return"),
        ),
        "max_drawdown": _first_number(
            replay_metrics.get("max_drawdown"),
            replay_metrics.get("mean_oos_drawdown"),
            metrics.get("mean_oos_drawdown"),
        ),
        "sharpe": _first_number(
            replay_metrics.get("sharpe"),
            replay_metrics.get("mean_oos_sharpe"),
            metrics.get("mean_oos_sharpe"),
        ),
        "trade_count": _first_number(
            replay_metrics.get("trade_count"),
            replay_metrics.get("mean_oos_trades"),
            metrics.get("mean_oos_trades"),
        ),
        "turnover": _first_number(
            replay_metrics.get("turnover"),
            replay_metrics.get("mean_turnover"),
            replay_metrics.get("mean_flip_count"),
            metrics.get("mean_flip_count"),
        ),
        "hit_rate": _first_number(
            replay_metrics.get("hit_rate"),
            replay_metrics.get("win_rate"),
        ),
        "average_trade_return": _first_number(
            replay_metrics.get("average_trade_return"),
            replay_metrics.get("avg_trade_return"),
        ),
        "assumptions": replay.get("assumptions"),
        "comparison": replay.get("comparison") or replay.get("baseline_comparison"),
        "artifact_path": (
            replay.get("artifact_path")
            or metrics.get("rl_economic_replay_artifact_path")
            or attempt_snapshot.get("rl_economic_replay_artifact_path")
        ),
        "artifact_hash": (
            replay.get("artifact_hash")
            or replay.get("replay_artifact_hash")
            or metrics.get("rl_economic_replay_artifact_hash")
            or attempt_snapshot.get("rl_economic_replay_artifact_hash")
        ),
    }


def _feature_readiness_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    gate_results = metrics.get("gate_results")
    gate_results = gate_results if isinstance(gate_results, dict) else {}
    config = metrics.get("config")
    config = config if isinstance(config, dict) else {}
    calibration = config.get("calibration_full_validation")
    calibration = calibration if isinstance(calibration, dict) else {}
    selected = calibration.get("selected")
    selected = selected if isinstance(selected, dict) else {}
    selected_metrics = selected.get("metrics")
    selected_metrics = selected_metrics if isinstance(selected_metrics, dict) else {}
    result = {
        "auc": _first_number(gate_results.get("direction_auc"), metrics.get("auc")),
        "ece": _first_number(selected_metrics.get("ece"), metrics.get("ece_calibrated")),
        "brier_score": _first_number(
            selected_metrics.get("brier_score"),
            metrics.get("brier_score_calibrated"),
        ),
        "signal_rate": _first_number(
            gate_results.get("operating_signal_rate"),
            metrics.get("signal_rate"),
        ),
    }
    return {key: value for key, value in result.items() if value is not None}


__all__ = [
    "_feature_readiness_metrics",
    "_first_number",
    "_rl_economic_replay",
    "_rl_economic_replay_summary",
]