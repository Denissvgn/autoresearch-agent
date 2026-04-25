"""Development gate bundle evaluation for autoresearch promotions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml


DEFAULT_GATE_BUNDLE_RELATIVE_PATH = (
    "reports/direction-tuning/promotion/development_gate_bundle_v1.yaml"
)


def load_gate_bundle(workspace_root: str | Path) -> dict[str, Any]:
    """Load the versioned development gate bundle from the workspace."""
    path = Path(workspace_root) / DEFAULT_GATE_BUNDLE_RELATIVE_PATH
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
            blockers.append(reason)

    policy = bundle.get("promotion_policy", {})
    add_check(
        "auc_only_promotion_disabled",
        policy.get("auc_only_promotion_allowed") is False,
        "auc_only_promotion_allowed",
        {"auc_only_promotion_allowed": policy.get("auc_only_promotion_allowed")},
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
            or best_iteration.get("all_gates_passed")
            or payload.get("all_gates_passed")
        ),
        "direction_quality_gates_failed_or_missing",
        gates,
    )
    _numeric_gate(
        checks=checks,
        blockers=blockers,
        waivers=waivers,
        name="min_direction_auc",
        value=_first_number(gates.get("direction_auc"), metrics.get("auc")),
        threshold=direction_checks.get("min_direction_auc"),
        comparator=">=",
        reason="direction_auc_below_gate_or_missing",
    )
    _numeric_gate(
        checks=checks,
        blockers=blockers,
        waivers=waivers,
        name="max_signal_rate",
        value=_first_number(
            gates.get("operating_signal_rate"),
            config.get("operating_signal_rate"),
        ),
        threshold=direction_checks.get("max_signal_rate"),
        comparator="<=",
        reason="signal_saturation_or_missing",
    )

    calibration_checks = bundle.get("gate_tiers", {}).get("calibration", {}).get(
        "checks", {}
    )
    selected_metrics = _dict_at(cal_full, "selected", "metrics")
    calibrated_ece = _first_number(
        selected_metrics.get("ece"),
        cal_full.get("ece_calibrated"),
        metrics.get("ece_calibrated"),
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
        _first_number(selected_metrics.get("brier_score"), metrics.get("brier_score_calibrated"))
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
    add_check(
        "signal_rate_distribution_required",
        bool(_dict_at(cal_full, "signal_rate_distribution")),
        "missing_signal_rate_distribution",
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
        "economic_replay_required",
        bool(replay_gates),
        "missing_economic_replay",
        replay_gates,
    )
    if replay_gates:
        add_check(
            "economic_replay_gates_passed",
            replay_gates.get("all_gates_passed") is True,
            "worsening_post_cost_replay",
            replay_gates,
        )

    add_check(
        "rollback_target_recorded",
        bool(payload.get("rollback_target") or payload.get("previous_development_version")),
        "missing_rollback_target",
    )
    add_check(
        "smoke_validation_passed",
        payload.get("smoke_validation_passed") is True
        or _dict_at(payload, "smoke_validation").get("passed") is True,
        "failed_smoke_validation",
    )

    return {
        "gate_bundle_id": bundle.get("gate_bundle_id"),
        "version": bundle.get("version"),
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
        blockers.append(reason)
