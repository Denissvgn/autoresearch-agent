"""Development gate bundle evaluation for autoresearch promotions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml

from src.core.gate_status import training_gates_passed_from_iteration

DEFAULT_GATE_BUNDLE_RELATIVE_PATH = (
    "reports/direction-tuning/promotion/development_gate_bundle_v1.yaml"
)
PRODUCTION_GATE_BUNDLE_RELATIVE_PATH = (
    "reports/direction-tuning/promotion/production_gate_bundle_v1.yaml"
)


def load_gate_bundle(workspace_root: str | Path) -> dict[str, Any]:
    """Load the versioned development gate bundle from the workspace."""
    path = Path(workspace_root) / DEFAULT_GATE_BUNDLE_RELATIVE_PATH
    return _load_bundle(path)


def load_production_gate_bundle(workspace_root: str | Path) -> dict[str, Any]:
    """Load the versioned production-scope promotion gate bundle."""
    path = Path(workspace_root) / PRODUCTION_GATE_BUNDLE_RELATIVE_PATH
    return _load_bundle(path)


def _load_bundle(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Gate bundle {path} did not contain a mapping")
    return data


def evaluate_development_gate_bundle(
    *,
    bundle: dict[str, Any],
    model_type: str,
    best_iteration: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate a best autoresearch iteration against the gate bundle.

    The evaluation is intentionally conservative: missing required evidence is
    a blocker unless the iteration explicitly carries a matching waiver.
    """
    if model_type == "rl":
        return _evaluate_rl_development_gate_bundle(
            bundle=bundle,
            model_type=model_type,
            best_iteration=best_iteration,
        )

    if model_type != "direction":
        return {
            "gate_bundle_id": bundle.get("gate_bundle_id"),
            "version": bundle.get("version"),
            "model_type": model_type,
            "applicable": False,
            "passed": True,
            "checks": [],
            "blockers": [],
            "waivers": [],
            "notes": ["development_direction_prediction_v1 applies to direction models"],
        }

    payload = _iteration_payload(best_iteration)
    waivers = _waivers(payload)
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add_check(name: str, passed: bool, reason: str, details: Any = None) -> None:
        waived = reason in waivers or name in waivers
        status = "passed" if passed else "waived" if waived else "failed"
        checks.append(
            {
                "name": name,
                "status": status,
                "reason": reason if not passed else None,
                "details": details,
            }
        )
        if not passed and not waived:
            _append_blocker(blockers, reason)

    policy = bundle.get("promotion_policy", {})
    add_check(
        "auc_only_promotion_disabled",
        policy.get("auc_only_promotion_allowed") is False,
        "auc_only_promotion_allowed",
        {"auc_only_promotion_allowed": policy.get("auc_only_promotion_allowed")},
    )
    add_check(
        "live_production_promotion_disabled",
        policy.get("live_production_promotion_allowed") is False,
        "live_production_promotion_policy_missing_or_allowed",
        {
            "live_production_promotion_allowed": policy.get(
                "live_production_promotion_allowed"
            )
        },
    )
    add_check(
        "development_scope_required",
        not _live_production_promotion_requested(payload),
        "live_production_promotion_forbidden",
        {"requested_scope": _requested_promotion_scope(payload)},
    )

    gates = _dict_at(payload, "gate_results")
    metrics = _dict_at(payload, "metrics")
    config = _dict_at(payload, "config")
    cal_full = _first_dict(
        config.get("calibration_full_validation"),
        payload.get("calibration_full_validation"),
    )
    cal_diag = _first_dict(
        config.get("calibration_diagnostics"),
        payload.get("calibration_diagnostics"),
    )

    direction_checks = bundle.get("gate_tiers", {}).get("direction_quality", {}).get(
        "checks", {}
    )
    add_check(
        "direction_quality_supported_gates",
        bool(
            gates.get("all_supported_gates_passed")
            or training_gates_passed_from_iteration(best_iteration)
        ),
        "direction_quality_gates_failed_or_missing",
        gates,
    )
    _numeric_gate(
        checks=checks,
        blockers=blockers,
        waivers=waivers,
        name="min_direction_auc",
        value=_first_number(
            gates.get("direction_auc"),
            metrics.get("auc"),
            payload.get("direction_auc"),
            payload.get("auc"),
            payload.get("walkforward_auc"),
        ),
        threshold=direction_checks.get("min_direction_auc"),
        comparator=">=",
        reason="direction_auc_below_gate_or_missing",
    )
    _numeric_gate(
        checks=checks,
        blockers=blockers,
        waivers=waivers,
        name="max_signal_rate",
        value=_max_number(
            gates.get("operating_signal_rate"),
            config.get("operating_signal_rate"),
            metrics.get("signal_rate"),
            payload.get("operating_signal_rate"),
            payload.get("signal_rate"),
        ),
        threshold=direction_checks.get("max_signal_rate"),
        comparator="<=",
        reason="signal_saturation",
    )

    calibration_checks = bundle.get("gate_tiers", {}).get("calibration", {}).get(
        "checks", {}
    )
    selected_metrics = _dict_at(cal_full, "selected", "metrics")
    calibrated_ece = _first_number(
        selected_metrics.get("ece"),
        cal_full.get("ece_calibrated"),
        metrics.get("ece_calibrated"),
        metrics.get("ece"),
        payload.get("ece_calibrated"),
        payload.get("ece"),
        cal_diag.get("cal_ece_after"),
    )
    _numeric_gate(
        checks=checks,
        blockers=blockers,
        waivers=waivers,
        name="max_ece_calibrated",
        value=calibrated_ece,
        threshold=calibration_checks.get("max_ece_calibrated"),
        comparator="<=",
        reason="weak_calibration",
    )
    add_check(
        "brier_score_required",
        _first_number(
            selected_metrics.get("brier_score"),
            metrics.get("brier_score_calibrated"),
            metrics.get("brier_score"),
            payload.get("brier_score_calibrated"),
            payload.get("brier_score"),
        )
        is not None,
        "missing_brier_score",
        selected_metrics,
    )
    add_check(
        "reliability_diagram_required",
        bool(_dict_or_list(cal_full, "selected", "reliability_diagram")),
        "missing_reliability_diagram",
    )
    add_check(
        "threshold_stability_by_fold_required",
        bool(_dict_at(cal_full, "threshold_stability_by_fold").get("folds")),
        "missing_threshold_stability_by_fold",
    )
    threshold_stability = _dict_at(cal_full, "threshold_stability_by_fold")
    _numeric_gate(
        checks=checks,
        blockers=blockers,
        waivers=waivers,
        name="max_threshold_cv",
        value=_first_number(
            threshold_stability.get("threshold_cv"),
            metrics.get("threshold_cv"),
            gates.get("threshold_cv"),
            payload.get("threshold_cv"),
        ),
        threshold=_first_number(
            calibration_checks.get("max_threshold_cv"),
            calibration_checks.get("max_fold_threshold_cv"),
        ),
        comparator="<=",
        reason="unstable_fold_thresholds",
    )
    add_check(
        "signal_rate_distribution_required",
        bool(_dict_at(cal_full, "signal_rate_distribution")),
        "missing_signal_rate_distribution",
    )
    signal_rate_distribution = _dict_at(cal_full, "signal_rate_distribution")
    signal_distribution_value = _max_number(
        signal_rate_distribution.get("max"),
        signal_rate_distribution.get("mean"),
        metrics.get("signal_rate_distribution_max"),
        payload.get("signal_rate_distribution_max"),
    )
    if signal_distribution_value is not None:
        _numeric_gate(
            checks=checks,
            blockers=blockers,
            waivers=waivers,
            name="max_signal_rate_distribution",
            value=signal_distribution_value,
            threshold=direction_checks.get("max_signal_rate"),
            comparator="<=",
            reason="signal_saturation",
        )
    per_regime = _dict_at(cal_full, "per_regime_calibration")
    add_check(
        "per_regime_calibration_graceful",
        bool(per_regime)
        and (
            per_regime.get("available") is True
            or per_regime.get("reason") == "regime_labels_absent"
        ),
        "missing_per_regime_calibration_status",
        per_regime,
    )

    replay = _first_dict(payload.get("economic_replay"), payload.get("replay"))
    replay_gates = _first_dict(replay.get("gates"), payload.get("replay_gates"))
    add_check(
        "feature_model_economic_replay_not_required",
        True,
        "feature_model_economic_replay_not_required",
        {
            "model_type": model_type,
            "reason": "RL policy owns post-cost action economics",
            "replay_present": bool(replay),
        },
    )
    if replay_gates:
        add_check(
            "economic_replay_gates_passed",
            replay_gates.get("all_gates_passed") is True,
            "worsening_post_cost_replay",
            replay_gates,
        )
        replay_checks = bundle.get("gate_tiers", {}).get("economic_replay", {}).get(
            "checks", {}
        )
        if replay_checks.get("worsening_vs_baseline_blocks_promotion") is True:
            worsening_details = _post_cost_replay_worsening_details(
                replay,
                replay_gates,
            )
            add_check(
                "economic_replay_not_worse_than_baseline",
                not worsening_details["worsened"],
                "worsening_post_cost_replay",
                worsening_details,
            )

    _evaluate_rl_oos_gates(
        bundle=bundle,
        payload=payload,
        checks=checks,
        blockers=blockers,
        waivers=waivers,
        add_check=add_check,
    )
    _evaluate_inference_parity_gates(
        bundle=bundle,
        payload=payload,
        add_check=add_check,
    )
    _evaluate_signal_health_gates(
        bundle=bundle,
        payload=payload,
        add_check=add_check,
    )
    _evaluate_inference_reload_gates(
        bundle=bundle,
        payload=payload,
        add_check=add_check,
    )
    _evaluate_rollback_readiness_gates(
        bundle=bundle,
        payload=payload,
        add_check=add_check,
    )
    _evaluate_smoke_validation_gates(
        bundle=bundle,
        payload=payload,
        add_check=add_check,
    )

    return {
        "gate_bundle_id": bundle.get("gate_bundle_id"),
        "version": bundle.get("version"),
        "scope": bundle.get("scope") or "development",
        "model_type": model_type,
        "applicable": True,
        "passed": not blockers,
        "checks": checks,
        "blockers": blockers,
        "waivers": sorted(waivers),
    }


def _iteration_payload(best_iteration: dict[str, Any]) -> dict[str, Any]:
    raw = best_iteration.get("metrics_json")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _waivers(payload: dict[str, Any]) -> set[str]:
    raw = payload.get("gate_waivers") or payload.get("waivers") or []
    if isinstance(raw, dict):
        return {str(key) for key, enabled in raw.items() if enabled}
    if isinstance(raw, str):
        return {item.strip() for item in raw.split(";") if item.strip()}
    if isinstance(raw, Iterable):
        return {str(item) for item in raw}
    return set()


def _evaluate_rl_development_gate_bundle(
    *,
    bundle: dict[str, Any],
    model_type: str,
    best_iteration: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate server-owned RL promotion gates for development promotion."""

    payload = dict(_iteration_payload(best_iteration))
    payload.setdefault("finalist", True)
    payload.setdefault("requires_rl_oos", True)
    waivers = _waivers(payload)
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add_check(name: str, passed: bool, reason: str, details: Any = None) -> None:
        waived = reason in waivers or name in waivers
        status = "passed" if passed else "waived" if waived else "failed"
        checks.append(
            {
                "name": name,
                "status": status,
                "reason": reason if not passed else None,
                "details": details,
            }
        )
        if not passed and not waived:
            _append_blocker(blockers, reason)

    policy = bundle.get("promotion_policy", {})
    add_check(
        "live_production_promotion_disabled",
        policy.get("live_production_promotion_allowed") is False,
        "live_production_promotion_policy_missing_or_allowed",
        {
            "live_production_promotion_allowed": policy.get(
                "live_production_promotion_allowed"
            )
        },
    )
    add_check(
        "development_scope_required",
        not _live_production_promotion_requested(payload),
        "live_production_promotion_forbidden",
        {"requested_scope": _requested_promotion_scope(payload)},
    )

    _evaluate_rl_economic_replay_gates(
        bundle=bundle,
        payload=payload,
        checks=checks,
        blockers=blockers,
        waivers=waivers,
        add_check=add_check,
    )
    _evaluate_rl_oos_gates(
        bundle=bundle,
        payload=payload,
        checks=checks,
        blockers=blockers,
        waivers=waivers,
        add_check=add_check,
        require_feature_provenance=True,
    )

    return {
        "gate_bundle_id": bundle.get("gate_bundle_id"),
        "version": bundle.get("version"),
        "scope": bundle.get("scope") or "development",
        "model_type": model_type,
        "applicable": True,
        "passed": not blockers,
        "checks": checks,
        "blockers": blockers,
        "waivers": sorted(waivers),
    }


def _dict_at(root: Any, *path: str) -> dict[str, Any]:
    value = root
    for key in path:
        if not isinstance(value, dict):
            return {}
        value = value.get(key)
    return value if isinstance(value, dict) else {}


def _dict_or_list(root: Any, *path: str) -> Any:
    value = root
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, (dict, list)) else None


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _first_number(*values: Any) -> float | None:
    for value in values:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _max_number(*values: Any) -> float | None:
    numbers = [_first_number(value) for value in values]
    finite_numbers = [number for number in numbers if number is not None]
    return max(finite_numbers) if finite_numbers else None


def _append_blocker(blockers: list[str], reason: str) -> None:
    if reason not in blockers:
        blockers.append(reason)


def _post_cost_replay_worsening_details(
    replay: dict[str, Any],
    replay_gates: dict[str, Any],
) -> dict[str, Any]:
    """Detect explicit post-cost replay worsening versus baseline evidence."""

    indicators: list[dict[str, Any]] = []
    boolean_keys = (
        "worsening_vs_baseline",
        "post_cost_worse_than_baseline",
        "worse_than_baseline",
    )
    numeric_delta_keys = (
        "post_cost_return_delta_vs_baseline",
        "post_cost_pnl_delta_vs_baseline",
        "net_return_delta_vs_baseline",
        "net_pnl_delta_vs_baseline",
        "post_cost_sharpe_delta_vs_baseline",
        "profit_factor_delta_vs_baseline",
    )
    containers = [
        ("replay", replay),
        ("replay_gates", replay_gates),
        ("replay.metrics", _dict_at(replay, "metrics")),
        ("replay.post_cost_metrics", _dict_at(replay, "post_cost_metrics")),
        ("replay_gates.metrics", _dict_at(replay_gates, "metrics")),
        ("replay.comparison", _dict_at(replay, "comparison")),
        ("replay.baseline_comparison", _dict_at(replay, "baseline_comparison")),
    ]

    for source, container in containers:
        for key in boolean_keys:
            if container.get(key) is True:
                indicators.append(
                    {"source": source, "key": key, "value": True}
                )
        for key in numeric_delta_keys:
            value = _first_number(container.get(key))
            if value is not None and value < 0.0:
                indicators.append(
                    {"source": source, "key": key, "value": value}
                )

    return {
        "worsened": bool(indicators),
        "indicators": indicators,
    }


def _evaluate_rl_economic_replay_gates(
    *,
    bundle: dict[str, Any],
    payload: dict[str, Any],
    checks: list[dict[str, Any]],
    blockers: list[str],
    waivers: set[str],
    add_check: Any,
) -> None:
    """Evaluate first-class RL post-cost economic replay evidence."""

    economic_tier = bundle.get("gate_tiers", {}).get("economic_replay", {})
    if not economic_tier:
        return
    tier_checks = economic_tier.get("checks", {}) if isinstance(economic_tier, dict) else {}
    required = bool(
        economic_tier.get("required")
        or economic_tier.get("required_for_rl")
        or economic_tier.get("required_for_rl_finalists")
    )
    finalist = bool(
        payload.get("finalist")
        or payload.get("is_finalist")
        or payload.get("requires_rl_oos")
        or payload.get("rl_oos")
    )
    replay = _rl_economic_replay_payload(payload)
    if not required and not finalist and not replay:
        return

    add_check(
        "rl_economic_replay_required",
        bool(replay) if finalist or required else True,
        "missing_economic_replay",
        replay,
    )
    if not replay:
        return

    add_check(
        "rl_economic_replay_schema",
        replay.get("schema_version") == "rl_economic_replay.v1",
        "invalid_rl_economic_replay_artifact",
        {"schema_version": replay.get("schema_version")},
    )
    replay_gates = _first_dict(replay.get("gates"), payload.get("replay_gates"))
    if replay_gates:
        add_check(
            "rl_economic_replay_gates_passed",
            replay_gates.get("all_gates_passed") is True,
            "worsening_post_cost_replay",
            replay_gates,
        )

    metrics = _rl_economic_replay_metrics(replay)
    required_metrics = (
        "post_cost_return",
        "max_drawdown",
        "trade_count",
        "turnover",
        "hit_rate",
        "average_trade_return",
    )
    missing_metrics = [
        name for name in required_metrics if _rl_economic_metric_value(metrics, name) is None
    ]
    has_risk_metric = (
        _rl_economic_metric_value(metrics, "sharpe") is not None
        or _rl_economic_metric_value(metrics, "sortino") is not None
    )
    if not has_risk_metric:
        missing_metrics.append("sharpe_or_sortino")
    if tier_checks.get("post_cost_metrics_required", True):
        add_check(
            "rl_post_cost_metrics_required",
            not missing_metrics,
            "missing_rl_replay_metrics",
            {"missing": missing_metrics, "metrics": metrics},
        )

    assumptions = _first_dict(
        replay.get("assumptions"),
        replay.get("cost_assumptions"),
        payload.get("rl_replay_assumptions"),
    )
    missing_assumptions = [
        key
        for key in ("fee_bps", "spread_bps", "slippage_bps")
        if _first_number(assumptions.get(key)) is None
    ]
    if tier_checks.get("replay_assumptions_required", True):
        add_check(
            "rl_replay_assumptions_required",
            not missing_assumptions,
            "missing_rl_replay_assumptions",
            {"missing": missing_assumptions, "assumptions": assumptions},
        )

    if tier_checks.get("profit_score_required", True):
        add_check(
            "rl_profit_score_required",
            _first_number(replay.get("rl_profit_score"), payload.get("rl_profit_score")) is not None,
            "missing_rl_profit_score",
            {"rl_profit_score": replay.get("rl_profit_score") or payload.get("rl_profit_score")},
        )

    if tier_checks.get("replay_artifact_hash_required", True):
        add_check(
            "rl_economic_replay_artifact_hash_recorded",
            bool(
                replay.get("artifact_hash")
                or replay.get("replay_artifact_hash")
                or payload.get("rl_economic_replay_artifact_hash")
            ),
            "missing_rl_economic_replay_artifact_hash",
            {
                "artifact_path": replay.get("artifact_path")
                or payload.get("rl_economic_replay_artifact_path"),
                "artifact_hash": replay.get("artifact_hash")
                or replay.get("replay_artifact_hash")
                or payload.get("rl_economic_replay_artifact_hash"),
            },
        )

    if tier_checks.get("worsening_vs_baseline_blocks_promotion") is True:
        worsening_details = _post_cost_replay_worsening_details(
            replay,
            replay_gates,
        )
        add_check(
            "rl_economic_replay_not_worse_than_baseline",
            not worsening_details["worsened"],
            "worsening_post_cost_replay",
            worsening_details,
        )


def _rl_economic_replay_payload(payload: dict[str, Any]) -> dict[str, Any]:
    rl_oos = _first_dict(payload.get("rl_oos"), payload.get("rl_oos_gates"))
    replay = _first_dict(
        payload.get("rl_economic_replay"),
        payload.get("economic_replay"),
        payload.get("replay"),
        rl_oos.get("rl_economic_replay"),
        rl_oos.get("economic_replay"),
    )
    if replay:
        return replay
    return {}


def _rl_economic_replay_metrics(replay: dict[str, Any]) -> dict[str, Any]:
    return _first_dict(
        replay.get("metrics"),
        replay.get("post_cost_metrics"),
        replay.get("aggregate"),
        replay,
    )


def _rl_economic_metric_value(metrics: dict[str, Any], name: str) -> float | None:
    aliases = {
        "post_cost_return": (
            "post_cost_return",
            "mean_post_cost_return",
            "total_return",
            "mean_oos_return",
            "net_return",
        ),
        "max_drawdown": ("max_drawdown", "mean_max_drawdown", "mean_oos_drawdown"),
        "sharpe": ("sharpe", "mean_sharpe", "mean_oos_sharpe", "oos_sharpe"),
        "sortino": ("sortino", "mean_sortino", "mean_oos_sortino"),
        "trade_count": ("trade_count", "trades", "mean_trades", "mean_oos_trades"),
        "turnover": ("turnover", "mean_turnover", "mean_abs_delta", "mean_flip_count"),
        "hit_rate": ("hit_rate", "win_rate", "mean_hit_rate", "mean_win_rate"),
        "average_trade_return": (
            "average_trade_return",
            "avg_trade_return",
            "mean_trade_return",
        ),
    }
    candidates = aliases.get(name, (name,))
    return _first_number(*(metrics.get(candidate) for candidate in candidates))


def _requested_promotion_scope(payload: dict[str, Any]) -> str:
    request = _first_dict(
        payload.get("promotion_request"),
        payload.get("promotion"),
        payload.get("promotion_policy"),
    )
    for container in (request, payload):
        for key in (
            "scope",
            "target_scope",
            "stage",
            "target_stage",
            "environment",
            "target_environment",
        ):
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
    return "development"


def _live_production_promotion_requested(payload: dict[str, Any]) -> bool:
    request = _first_dict(
        payload.get("promotion_request"),
        payload.get("promotion"),
        payload.get("promotion_policy"),
    )
    boolean_keys = (
        "live_production",
        "live_production_requested",
        "live_production_promotion_requested",
        "production_promotion_requested",
    )
    if any(request.get(key) is True or payload.get(key) is True for key in boolean_keys):
        return True
    return _requested_promotion_scope(payload) in {"live", "prod", "production"}


def _evaluate_rollback_readiness_gates(
    *,
    bundle: dict[str, Any],
    payload: dict[str, Any],
    add_check: Any,
) -> None:
    """Evaluate rollback readiness evidence for development promotion."""

    tier = bundle.get("gate_tiers", {}).get("rollback_readiness", {})
    tier_checks = tier.get("checks", {}) if isinstance(tier, dict) else {}
    rollback = _first_dict(
        payload.get("rollback_readiness"),
        payload.get("rollback"),
        payload.get("rollback_plan"),
    )
    target_recorded = bool(
        payload.get("rollback_target")
        or payload.get("previous_development_version")
        or rollback.get("rollback_target")
        or rollback.get("previous_config_snapshot_path")
    )

    if not tier_checks:
        add_check(
            "rollback_target_recorded",
            target_recorded,
            "missing_rollback_target",
            rollback,
        )
        return

    if tier_checks.get("previous_development_version_addressable"):
        add_check(
            "rollback_previous_development_version_addressable",
            _bool_field(
                rollback,
                "previous_development_version_addressable",
                "previous_version_addressable",
            )
            or target_recorded,
            "missing_rollback_target",
            rollback,
        )
    if tier_checks.get("rollback_by_instrument_timeframe_supported"):
        add_check(
            "rollback_by_instrument_timeframe_supported",
            _bool_field(
                rollback,
                "rollback_by_instrument_timeframe_supported",
                "instrument_timeframe_rollback_supported",
            )
            or rollback.get("rollback_method")
            in {
                "instrument_timeframe",
                "instrument_timeframe_development_config",
            },
            "missing_rollback_target",
            rollback,
        )
    if tier_checks.get("rollback_target_recorded"):
        add_check(
            "rollback_target_recorded",
            target_recorded,
            "missing_rollback_target",
            rollback,
        )


def _evaluate_signal_health_gates(
    *,
    bundle: dict[str, Any],
    payload: dict[str, Any],
    add_check: Any,
) -> None:
    """Evaluate development direction-signal health monitoring evidence."""

    tier = bundle.get("gate_tiers", {}).get("signal_health_monitoring", {})
    tier_checks = tier.get("checks", {}) if isinstance(tier, dict) else {}
    if not tier_checks:
        return

    signal_health = _first_dict(
        payload.get("development_signal_health"),
        payload.get("signal_health"),
        payload.get("direction_signal_health"),
    )
    metrics = _dict_at(signal_health, "metrics")
    operational = _dict_at(signal_health, "operational")
    drift = _dict_at(signal_health, "drift")

    add_check(
        "signal_health_payload_required",
        bool(signal_health),
        "missing_signal_health_metrics",
        signal_health,
    )
    if not signal_health:
        return

    if tier_checks.get("probability_summary_required"):
        add_check(
            "signal_health_probability_summary",
            _first_number(metrics.get("probability_mean")) is not None
            and _first_number(metrics.get("probability_std")) is not None,
            "missing_signal_health_metrics",
            metrics,
        )
    if tier_checks.get("entropy_required"):
        add_check(
            "signal_health_entropy",
            _first_number(metrics.get("entropy_mean")) is not None,
            "missing_signal_health_metrics",
            metrics,
        )
    if tier_checks.get("signal_rate_required"):
        add_check(
            "signal_health_signal_rate",
            _first_number(metrics.get("signal_rate")) is not None,
            "missing_signal_health_metrics",
            metrics,
        )
    if tier_checks.get("drift_metrics_required"):
        add_check(
            "signal_health_drift_metrics",
            _first_number(drift.get("psi")) is not None
            or _first_number(drift.get("kl_divergence")) is not None
            or bool(_dict_at(drift, "deltas")),
            "missing_signal_health_metrics",
            drift,
        )
    if tier_checks.get("operational_metrics_required"):
        add_check(
            "signal_health_operational_metrics",
            "feature_schema_mismatch_count" in operational
            and "adapter_failure_count" in operational
            and "rl_hold_rate" in operational,
            "missing_signal_health_metrics",
            operational,
        )
    if tier_checks.get("alerts_block_promotion"):
        alerts = signal_health.get("alerts")
        add_check(
            "signal_health_no_alerts",
            not alerts,
            "signal_health_alerts_present",
            alerts,
        )


def _evaluate_inference_reload_gates(
    *,
    bundle: dict[str, Any],
    payload: dict[str, Any],
    add_check: Any,
) -> None:
    """Evaluate DPU-073 inference reload/parity validation evidence."""

    tier = bundle.get("gate_tiers", {}).get("inference_reload", {})
    tier_checks = tier.get("checks", {}) if isinstance(tier, dict) else {}
    if not tier_checks:
        return

    validation = _first_dict(
        payload.get("inference_reload_validation"),
        payload.get("reload_validation"),
    )
    checks = _dict_at(validation, "checks")
    add_check(
        "inference_reload_validation_required",
        bool(validation),
        "inference_reload_validation_missing",
        validation,
    )
    if not validation:
        return

    if tier_checks.get("feature_alignment_required"):
        add_check(
            "inference_reload_feature_alignment",
            checks.get("feature_name_alignment_passed") is True
            and checks.get("feature_count_alignment_passed") is True,
            "inference_feature_schema_mismatch",
            checks,
        )
    if tier_checks.get("adapter_loading_required"):
        add_check(
            "inference_reload_adapter_loading",
            checks.get("adapter_loading_passed") is True,
            "tsfm_adapter_load_failure_without_tabular_fallback",
            checks,
        )
    if tier_checks.get("roster_parity_required"):
        add_check(
            "inference_reload_roster_parity",
            checks.get("model_roster_parity_passed") is True,
            "model_roster_mismatch",
            checks,
        )
    if tier_checks.get("observation_dimension_parity_required"):
        add_check(
            "inference_reload_observation_dimension_parity",
            checks.get("observation_dimension_parity_passed") is True,
            "inference_feature_schema_mismatch",
            checks,
        )
    if tier_checks.get("fallback_behavior_required"):
        add_check(
            "inference_reload_fallback_behavior",
            checks.get("fallback_behavior_passed") is True,
            "tsfm_adapter_load_failure_without_tabular_fallback",
            checks,
        )
    if tier_checks.get("latency_budget_required"):
        add_check(
            "inference_reload_latency_budget",
            checks.get("latency_budget_passed") is True,
            "tsfm_latency_budget_failure",
            checks,
        )
    if tier_checks.get("composite_reload_required"):
        add_check(
            "inference_reload_composite_reload",
            checks.get("composite_reload_passed") is True,
            "inference_reload_failed",
            checks,
        )
    if tier_checks.get("rollback_ready_required"):
        add_check(
            "inference_reload_rollback_ready",
            checks.get("rollback_ready") is True,
            "missing_rollback_target",
            checks,
        )
    if tier_checks.get("prior_version_preserved_on_reload_failure"):
        add_check(
            "inference_reload_prior_version_preserved_on_failure",
            checks.get("prior_version_preserved_on_reload_failure") is True,
            "inference_reload_failed",
            checks,
        )


def _evaluate_smoke_validation_gates(
    *,
    bundle: dict[str, Any],
    payload: dict[str, Any],
    add_check: Any,
) -> None:
    """Evaluate smoke or paper validation evidence before promotion."""

    tier = bundle.get("gate_tiers", {}).get("smoke_validation", {})
    tier_checks = tier.get("checks", {}) if isinstance(tier, dict) else {}
    smoke = _first_dict(
        payload.get("smoke_validation"),
        payload.get("paper_validation"),
        payload.get("promotion_smoke_validation"),
    )
    inference = _first_dict(
        payload.get("inference_parity"),
        payload.get("inference_validation"),
        payload.get("inference"),
    )
    composite = _first_dict(
        payload.get("composite_metadata"),
        payload.get("composite"),
    )
    rollback = _first_dict(
        payload.get("rollback_readiness"),
        payload.get("rollback"),
        payload.get("rollback_plan"),
    )
    smoke_passed = (
        payload.get("smoke_validation_passed") is True
        or smoke.get("passed") is True
        or smoke.get("paper_validation_passed") is True
    )

    if not tier_checks:
        add_check(
            "smoke_validation_passed",
            smoke_passed,
            "failed_smoke_validation",
            smoke,
        )
        return

    if tier_checks.get("paper_or_smoke_validation_required"):
        add_check(
            "smoke_validation_passed",
            smoke_passed,
            "failed_smoke_validation",
            smoke,
        )
    if tier_checks.get("composite_reload_required"):
        add_check(
            "smoke_composite_reload_supported",
            _bool_field(
                smoke,
                "composite_reload_passed",
                "composite_reload_supported",
                "reload_supported",
            )
            or _bool_field(
                inference,
                "composite_reload_passed",
                "composite_reload_supported",
                "reload_supported",
            )
            or _bool_field(
                composite,
                "composite_reload_passed",
                "composite_reload_supported",
                "reload_supported",
            ),
            "failed_smoke_validation",
            {"smoke_validation": smoke, "composite_metadata": composite},
        )
    if tier_checks.get("prior_version_left_intact_on_failure"):
        add_check(
            "smoke_prior_version_left_intact_on_failure",
            _bool_field(
                smoke,
                "prior_version_left_intact_on_failure",
                "prior_version_left_intact",
            )
            or _bool_field(
                rollback,
                "prior_version_left_intact_on_failure",
                "previous_development_version_addressable",
            ),
            "failed_smoke_validation",
            {"smoke_validation": smoke, "rollback_readiness": rollback},
        )


def _evaluate_inference_parity_gates(
    *,
    bundle: dict[str, Any],
    payload: dict[str, Any],
    add_check: Any,
) -> None:
    """Evaluate required inference parity evidence for development promotion."""

    tier = bundle.get("gate_tiers", {}).get("inference_parity", {})
    if not tier:
        return
    tier_checks = tier.get("checks", {})
    if not (tier.get("required") or tier_checks):
        return

    inference = _first_dict(
        payload.get("inference_parity"),
        payload.get("inference_validation"),
        payload.get("inference"),
    )
    add_check(
        "inference_parity_required",
        bool(inference),
        "inference_feature_schema_mismatch",
        inference,
    )
    if not inference:
        return

    feature_details = _first_dict(
        inference.get("features"),
        inference.get("feature_schema"),
        payload.get("feature_parity"),
    )
    if tier_checks.get("feature_name_alignment_required"):
        add_check(
            "inference_feature_name_alignment",
            _bool_field(
                inference,
                "feature_name_alignment_passed",
                "feature_names_aligned",
                "feature_name_alignment",
            )
            or _bool_field(
                feature_details,
                "feature_name_alignment_passed",
                "feature_names_aligned",
                "names_aligned",
            ),
            "inference_feature_schema_mismatch",
            feature_details or inference,
        )
    if tier_checks.get("feature_count_alignment_required"):
        add_check(
            "inference_feature_count_alignment",
            _bool_field(
                inference,
                "feature_count_alignment_passed",
                "feature_count_aligned",
                "feature_count_alignment",
            )
            or _bool_field(
                feature_details,
                "feature_count_alignment_passed",
                "feature_count_aligned",
                "count_aligned",
            ),
            "inference_feature_schema_mismatch",
            feature_details or inference,
        )

    roster_details = _first_dict(
        inference.get("roster"),
        inference.get("model_roster"),
        payload.get("roster_parity"),
    )
    if tier_checks.get("model_roster_parity_required"):
        add_check(
            "inference_model_roster_parity",
            _bool_field(
                inference,
                "model_roster_parity_passed",
                "roster_parity_passed",
                "model_roster_matches",
            )
            or _bool_field(
                roster_details,
                "model_roster_parity_passed",
                "roster_parity_passed",
                "matches",
            ),
            "model_roster_mismatch",
            roster_details or inference,
        )

    tsfm_candidate = _is_tsfm_candidate(payload, inference)
    adapter_details = _first_dict(
        inference.get("adapter"),
        inference.get("tsfm_adapter"),
        payload.get("tsfm_adapter"),
    )
    if tier_checks.get("adapter_loading_required") and tsfm_candidate:
        fallback_ok = _bool_field(
            inference,
            "tabular_fallback_passed",
            "fallback_check_passed",
            "fallback_available",
        ) or _bool_field(adapter_details, "tabular_fallback_passed", "fallback_available")
        add_check(
            "inference_tsfm_adapter_loading",
            fallback_ok
            or _bool_field(
                inference,
                "adapter_loading_passed",
                "adapter_loaded",
                "tsfm_adapter_loaded",
            )
            or _bool_field(adapter_details, "loaded", "adapter_loaded"),
            "tsfm_adapter_load_failure_without_tabular_fallback",
            {"adapter": adapter_details, "fallback_ok": fallback_ok},
        )

    rl_details = _first_dict(
        inference.get("rl"),
        inference.get("observation"),
        payload.get("rl_inference_parity"),
    )
    rl_observation_changed = any(
        value is True
        for value in (
            payload.get("rl_observation_changed"),
            payload.get("obs_spec_changed"),
            inference.get("rl_observation_changed"),
            inference.get("obs_spec_changed"),
            rl_details.get("observation_changed"),
            rl_details.get("obs_spec_changed"),
        )
    )
    if (
        tier_checks.get("observation_dimension_parity_required_when_rl_changes")
        and rl_observation_changed
    ):
        add_check(
            "inference_rl_observation_dimension_parity",
            _bool_field(
                inference,
                "observation_dimension_parity_passed",
                "obs_dim_parity_passed",
            )
            or _bool_field(
                rl_details,
                "observation_dimension_parity_passed",
                "obs_dim_parity_passed",
                "dimension_parity_passed",
            ),
            "inference_feature_schema_mismatch",
            rl_details or inference,
        )

    if tier_checks.get("latency_budget_required_for_tsfm") and tsfm_candidate:
        add_check(
            "inference_tsfm_latency_budget",
            _bool_field(
                inference,
                "latency_budget_passed",
                "tsfm_latency_budget_passed",
            )
            or _bool_field(adapter_details, "latency_budget_passed"),
            "tsfm_latency_budget_failure",
            adapter_details or inference,
        )
    if tier_checks.get("fallback_required_for_tsfm") and tsfm_candidate:
        add_check(
            "inference_tsfm_fallback_check",
            _bool_field(
                inference,
                "fallback_check_passed",
                "tabular_fallback_passed",
                "fallback_available",
            )
            or _bool_field(adapter_details, "fallback_check_passed", "fallback_available"),
            "tsfm_adapter_load_failure_without_tabular_fallback",
            adapter_details or inference,
        )


def _bool_field(container: dict[str, Any], *keys: str) -> bool:
    return any(container.get(key) is True for key in keys)


def _is_tsfm_candidate(payload: dict[str, Any], inference: dict[str, Any]) -> bool:
    if any(
        value is True
        for value in (
            payload.get("is_tsfm_candidate"),
            payload.get("tsfm_candidate"),
            inference.get("is_tsfm_candidate"),
            inference.get("tsfm_candidate"),
        )
    ):
        return True
    for value in (
        payload.get("model_family"),
        payload.get("candidate_family"),
        inference.get("model_family"),
        inference.get("candidate_family"),
    ):
        if isinstance(value, str) and value.lower() in {"tsfm", "ts-fm", "timesfm"}:
            return True
    return False


def _evaluate_rl_oos_gates(
    *,
    bundle: dict[str, Any],
    payload: dict[str, Any],
    checks: list[dict[str, Any]],
    blockers: list[str],
    waivers: set[str],
    add_check: Any,
    require_feature_provenance: bool = False,
) -> None:
    """Evaluate DPU-063 RL OOS gate evidence when a candidate is a finalist."""

    rl_tier = bundle.get("gate_tiers", {}).get("rl_oos", {})
    if not rl_tier:
        return

    rl_oos = _first_dict(
        payload.get("rl_oos"),
        payload.get("rl_oos_gates"),
        payload.get("rl_walk_forward"),
        payload.get("rl"),
    )
    finalist = bool(
        payload.get("finalist")
        or payload.get("is_finalist")
        or payload.get("requires_rl_oos")
        or rl_oos
    )
    if not finalist:
        return

    add_check(
        "rl_oos_required_for_finalist",
        bool(rl_oos),
        "missing_rl_oos_gate_results",
        rl_oos,
    )
    if not rl_oos:
        return

    tier_checks = rl_tier.get("checks", {})
    direction_provenance = _rl_channel_provenance(payload, rl_oos, "direction")
    volatility_provenance = _rl_channel_provenance(payload, rl_oos, "volatility")

    if require_feature_provenance or tier_checks.get("feature_provenance_required"):
        _evaluate_rl_feature_provenance_gate(
            channel="direction",
            provenance=direction_provenance,
            checks=checks,
            blockers=blockers,
            waivers=waivers,
        )
        _evaluate_rl_feature_provenance_gate(
            channel="volatility",
            provenance=volatility_provenance,
            checks=checks,
            blockers=blockers,
            waivers=waivers,
        )
        add_check(
            "rl_feature_bundle_hash_recorded",
            bool(_rl_feature_bundle_hash(payload, rl_oos)),
            "missing_rl_feature_bundle_hash",
            {
                "feature_bundle_hash": _rl_feature_bundle_hash(payload, rl_oos),
            },
        )

    if tier_checks.get("oof_direction_proba_required"):
        honest_coverage = _first_number(
            direction_provenance.get("honest_coverage"),
            direction_provenance.get("oof_available_coverage"),
            direction_provenance.get("oof_coverage"),
        )
        _numeric_gate(
            checks=checks,
            blockers=blockers,
            waivers=waivers,
            name="rl_oof_direction_proba_required",
            value=honest_coverage,
            threshold=0.95,
            comparator=">=",
            reason="missing_oof_provenance",
        )

    if tier_checks.get("oof_volatility_proba_required") or require_feature_provenance:
        honest_coverage = _first_number(
            volatility_provenance.get("honest_coverage"),
            volatility_provenance.get("oof_available_coverage"),
            volatility_provenance.get("oof_coverage"),
        )
        _numeric_gate(
            checks=checks,
            blockers=blockers,
            waivers=waivers,
            name="rl_oof_volatility_proba_required",
            value=honest_coverage,
            threshold=0.95,
            comparator=">=",
            reason="missing_volatility_oof_provenance",
        )

    if tier_checks.get("proxy_or_neutral_fallback_blocks_promotion"):
        direction_unsafe = _rl_unsafe_feature_details(direction_provenance)
        add_check(
            "rl_no_proxy_or_neutral_direction_fallback",
            not direction_unsafe["unsafe"],
            "proxy_or_neutral_direction_proba_fallback",
            direction_unsafe,
        )
        if require_feature_provenance or tier_checks.get(
            "volatility_fallback_blocks_promotion"
        ):
            volatility_unsafe = _rl_unsafe_feature_details(volatility_provenance)
            add_check(
                "rl_no_proxy_or_neutral_volatility_fallback",
                not volatility_unsafe["unsafe"],
                "proxy_or_neutral_volatility_feature_fallback",
                volatility_unsafe,
            )

    if require_feature_provenance or tier_checks.get("stale_or_leaked_blocks_promotion"):
        for channel, provenance in (
            ("direction", direction_provenance),
            ("volatility", volatility_provenance),
        ):
            stale_or_leaked = _rl_stale_or_leaked_details(provenance)
            add_check(
                f"rl_no_{channel}_stale_or_leaked_feature",
                not stale_or_leaked["unsafe"],
                "stale_or_leaked_feature_provenance",
                stale_or_leaked,
            )

    if tier_checks.get("nested_validation_required"):
        add_check(
            "rl_nested_validation_required",
            _rl_nested_validation_present(rl_oos),
            "missing_nested_validation",
            rl_oos,
        )

    if tier_checks.get("multi_seed_required"):
        add_check(
            "rl_multi_seed_required",
            _rl_multi_seed_present(rl_oos),
            "missing_multi_seed_rl_validation",
            rl_oos,
        )

    required_metrics = tier_checks.get("metrics_required") or []
    if required_metrics:
        metrics = _first_dict(
            rl_oos.get("metrics"),
            rl_oos.get("aggregate"),
            rl_oos.get("oos"),
            rl_oos,
        )
        missing = [
            name
            for name in required_metrics
            if _rl_metric_value(metrics, name) is None
        ]
        add_check(
            "rl_oos_metrics_required",
            not missing,
            "missing_rl_oos_metrics",
            {"missing": missing, "metrics": metrics},
        )


def _evaluate_rl_feature_provenance_gate(
    *,
    channel: str,
    provenance: dict[str, Any],
    checks: list[dict[str, Any]],
    blockers: list[str],
    waivers: set[str],
) -> None:
    missing_reason = f"missing_{channel}_feature_provenance"
    complete_reason = f"incomplete_{channel}_feature_provenance"
    _boolean_gate(
        checks=checks,
        blockers=blockers,
        waivers=waivers,
        name=f"rl_{channel}_feature_provenance_required",
        passed=bool(provenance),
        reason=missing_reason,
        details=provenance,
    )
    if not provenance:
        return

    missing = _rl_required_provenance_fields_missing(provenance)
    _boolean_gate(
        checks=checks,
        blockers=blockers,
        waivers=waivers,
        name=f"rl_{channel}_feature_provenance_complete",
        passed=not missing,
        reason=complete_reason,
        details={"missing": missing, "provenance": provenance},
    )


def _rl_channel_provenance(
    payload: dict[str, Any],
    rl_oos: dict[str, Any],
    channel: str,
) -> dict[str, Any]:
    feature_provenance = _first_dict(
        rl_oos.get("feature_provenance"),
        rl_oos.get("feature_provenance_by_channel"),
        payload.get("feature_provenance"),
        payload.get("feature_provenance_by_channel"),
    )
    probability_provenance = _first_dict(
        rl_oos.get("probability_provenance"),
        payload.get("probability_provenance"),
    )
    return _first_dict(
        rl_oos.get(f"{channel}_probability_provenance"),
        rl_oos.get(f"{channel}_feature_provenance"),
        payload.get(f"{channel}_probability_provenance"),
        payload.get(f"{channel}_feature_provenance"),
        feature_provenance.get(channel),
        probability_provenance.get(channel),
    )


def _rl_feature_bundle_hash(
    payload: dict[str, Any],
    rl_oos: dict[str, Any],
) -> str | None:
    candidates = (
        rl_oos.get("feature_bundle_hash"),
        rl_oos.get("rl_feature_bundle_hash"),
        rl_oos.get("dataset_hash"),
        rl_oos.get("enriched_dataset_hash"),
        payload.get("feature_bundle_hash"),
        payload.get("rl_feature_bundle_hash"),
        payload.get("dataset_hash"),
        payload.get("enriched_dataset_hash"),
        _dict_at(rl_oos, "feature_bundle").get("hash"),
        _dict_at(rl_oos, "rl_dataset").get("feature_bundle_hash"),
        _dict_at(payload, "feature_bundle").get("hash"),
        _dict_at(payload, "rl_dataset").get("feature_bundle_hash"),
    )
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _rl_required_provenance_fields_missing(
    provenance: dict[str, Any],
) -> list[str]:
    required_aliases = {
        "source_model_registry_name": (
            "source_model_registry_name",
            "model_registry_name",
            "registered_model_name",
            "registry_name",
            "source_model_name",
        ),
        "source_model_registry_version": (
            "source_model_registry_version",
            "model_registry_version",
            "registered_model_version",
            "registry_version",
            "model_version",
            "source_model_version",
        ),
        "mlflow_run_id": ("source_mlflow_run_id", "mlflow_run_id", "run_id"),
        "feature_schema_hash": (
            "feature_schema_hash",
            "source_feature_schema_hash",
            "schema_hash",
        ),
        "prediction_timestamp_coverage": (
            "prediction_timestamp_coverage",
            "timestamp_coverage",
            "prediction_coverage",
            "coverage",
        ),
    }
    missing: list[str] = []
    for field, aliases in required_aliases.items():
        if not any(_present_value(provenance.get(alias)) for alias in aliases):
            missing.append(field)
    return missing


def _present_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list, tuple, set)):
        return bool(value)
    return True


def _rl_unsafe_feature_details(provenance: dict[str, Any]) -> dict[str, Any]:
    unsafe_count = int(_first_number(provenance.get("unsafe_count")) or 0)
    unsafe_values = _string_list(provenance.get("unsafe_values"))
    status_values = _provenance_status_values(provenance)
    flagged_keys = [
        key
        for key in (
            "fallback_used",
            "neutral_fallback_used",
            "proxy_used",
            "synthetic_fallback_used",
            "model_proxy_used",
        )
        if _truthy(provenance.get(key))
    ]
    unsafe_tokens = {
        "fallback",
        "legacy_inferred",
        "neutral",
        "neutral_fallback",
        "proxy",
        "sdk_proxy",
        "synthetic",
        "unknown",
    }
    unsafe_statuses = [
        value
        for value in status_values + unsafe_values
        if any(token in value for token in unsafe_tokens)
        and "quasi_oof" not in value
        and "oof" not in value
    ]
    unsafe = bool(unsafe_count > 0 or unsafe_values or flagged_keys or unsafe_statuses)
    return {
        "unsafe": unsafe,
        "unsafe_count": unsafe_count,
        "unsafe_values": unsafe_values,
        "status_values": status_values,
        "unsafe_statuses": unsafe_statuses,
        "flagged_keys": flagged_keys,
        "provenance": provenance,
    }


def _rl_stale_or_leaked_details(provenance: dict[str, Any]) -> dict[str, Any]:
    status_values = _provenance_status_values(provenance) + _string_list(
        provenance.get("unsafe_values")
    )
    flagged_keys = [
        key
        for key in (
            "stale",
            "is_stale",
            "stale_features",
            "leaked",
            "is_leaked",
            "leaked_features",
            "leakage_detected",
            "lookahead_leakage",
        )
        if _truthy(provenance.get(key))
    ]
    unsafe_statuses = [
        value
        for value in status_values
        if any(token in value for token in ("stale", "leak", "lookahead", "future"))
    ]
    unsafe = bool(flagged_keys or unsafe_statuses)
    return {
        "unsafe": unsafe,
        "status_values": status_values,
        "unsafe_statuses": unsafe_statuses,
        "flagged_keys": flagged_keys,
        "provenance": provenance,
    }


def _provenance_status_values(provenance: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (
        "status",
        "quality",
        "provenance",
        "provenance_status",
        "oof_status",
        "feature_status",
        "prediction_status",
        "source",
    ):
        values.extend(_string_list(provenance.get(key)))
    return values


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, dict):
        raw = [key for key, count in value.items() if count]
    elif isinstance(value, Iterable):
        raw = list(value)
    else:
        raw = [value]
    return [str(item).strip().lower() for item in raw if str(item).strip()]


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "used"}
    return bool(value)


def _boolean_gate(
    *,
    checks: list[dict[str, Any]],
    blockers: list[str],
    waivers: set[str],
    name: str,
    passed: bool,
    reason: str,
    details: Any = None,
) -> None:
    waived = reason in waivers or name in waivers
    status = "passed" if passed else "waived" if waived else "failed"
    checks.append(
        {
            "name": name,
            "status": status,
            "reason": reason if not passed else None,
            "details": details,
        }
    )
    if not passed and not waived:
        _append_blocker(blockers, reason)


def _rl_nested_validation_present(rl_oos: dict[str, Any]) -> bool:
    if rl_oos.get("nested_validation_used") is True:
        return True
    if rl_oos.get("blocked_time_validation_used") is True:
        return True
    validation_mode = str(
        rl_oos.get("validation_mode")
        or rl_oos.get("oos_validation_mode")
        or ""
    ).strip().lower()
    if validation_mode in {"blocked_time", "blocked-time", "nested", "walk_forward"}:
        return True
    if _first_number(rl_oos.get("wf_nested_eval_ratio")):
        return True
    folds = rl_oos.get("folds")
    if isinstance(folds, list) and folds:
        return all(bool(_dict_at(fold, "validation")) for fold in folds if isinstance(fold, dict))
    return bool(_dict_at(rl_oos, "validation"))


def _rl_metric_value(metrics: dict[str, Any], name: str) -> float | None:
    aliases = {
        "return": ("return", "oos_return", "mean_return", "mean_oos_return"),
        "drawdown": (
            "drawdown",
            "oos_drawdown",
            "max_drawdown",
            "mean_oos_drawdown",
        ),
        "trade_count": (
            "trade_count",
            "trades",
            "oos_trades",
            "mean_trades",
            "mean_oos_trades",
        ),
        "mean_absolute_position": (
            "mean_absolute_position",
            "mean_abs_position",
            "mean_abs_pos",
            "oos_mean_position",
        ),
        "flip_count": (
            "flip_count",
            "flips",
            "oos_flips",
            "mean_flip_count",
        ),
        "is_oos_ratio": ("is_oos_ratio", "is_oos_return_ratio"),
        "folds_passed": ("folds_passed",),
        "oos_sharpe": ("oos_sharpe", "mean_oos_sharpe", "sharpe"),
    }
    candidates = aliases.get(
        name,
        (name, f"mean_{name}", f"mean_oos_{name}", f"oos_{name}"),
    )
    return _first_number(*(metrics.get(candidate) for candidate in candidates))


def _rl_multi_seed_present(rl_oos: dict[str, Any]) -> bool:
    n_seed_trials = _first_number(rl_oos.get("n_seed_trials"))
    if n_seed_trials is not None and n_seed_trials >= 2:
        return True
    folds = rl_oos.get("folds")
    if isinstance(folds, list) and folds:
        for fold in folds:
            if isinstance(fold, dict):
                fold_trials = _first_number(
                    fold.get("n_seed_trials"),
                    _dict_at(fold, "validation").get("n_seed_trials"),
                    _dict_at(fold, "oos").get("n_seed_trials"),
                )
                if fold_trials is not None and fold_trials >= 2:
                    return True
    return rl_oos.get("multi_seed") is True


def _numeric_gate(
    *,
    checks: list[dict[str, Any]],
    blockers: list[str],
    waivers: set[str],
    name: str,
    value: float | None,
    threshold: Any,
    comparator: str,
    reason: str,
) -> None:
    if threshold is None:
        return
    threshold_f = _first_number(threshold)
    if value is None or threshold_f is None:
        passed = False
    elif comparator == ">=":
        passed = value >= threshold_f
    elif comparator == "<=":
        passed = value <= threshold_f
    else:
        raise ValueError(f"Unsupported comparator {comparator}")

    waived = reason in waivers or name in waivers
    status = "passed" if passed else "waived" if waived else "failed"
    checks.append(
        {
            "name": name,
            "status": status,
            "reason": reason if not passed else None,
            "details": {"value": value, "threshold": threshold_f},
        }
    )
    if not passed and not waived:
        _append_blocker(blockers, reason)
