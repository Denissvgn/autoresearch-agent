"""Structured promotion blocker classification for operator-facing previews."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional


_BLOCKER_LABELS = {
    "candidate_training_gates_not_passed": "Candidate training gates did not pass.",
    "development_promotion_not_allowed": "Development promotion gates have not passed.",
    "direction_auc_below_gate_or_missing": "Direction AUC is below the required gate or missing.",
    "failed_smoke_validation": "Smoke or paper validation failed or is missing.",
    "inference_adapter_load_failure": "Inference adapter loading failed.",
    "inference_feature_schema_mismatch": "Inference feature schema does not match training.",
    "inference_reload_failed": "Inference reload or parity validation failed.",
    "inference_reload_validation_missing": "Inference reload validation is missing.",
    "missing_brier_score": "Calibration Brier score is missing.",
    "missing_canary_duration": "Canary validation duration is missing or too short.",
    "missing_canary_promotion": "A canary promotion record is required first.",
    "missing_development_promotion": "A development promotion record is required first.",
    "missing_direction_feature_provenance": "Direction feature provenance is missing.",
    "missing_economic_replay": "Economic replay evidence is missing.",
    "missing_feature_readiness": "Direction and volatility feature readiness evidence is missing.",
    "missing_inference_parity": "Inference parity evidence is missing.",
    "missing_live_risk_limits": "Production risk limits are not configured.",
    "missing_model_card": "A reviewed model card is required.",
    "missing_monitoring_alerts": "Production monitoring and alerts are not configured.",
    "missing_multi_seed_rl_validation": "Multi-seed RL validation is missing.",
    "missing_nested_validation": "Nested or blocked-time RL validation is missing.",
    "missing_paper_promotion": "A paper promotion record is required first.",
    "missing_paper_validation": "Paper trading validation evidence is missing.",
    "missing_per_regime_calibration_status": "Per-regime calibration status is missing.",
    "missing_production_approval": "Production approval is required.",
    "missing_reliability_diagram": "Calibration reliability diagram is missing.",
    "missing_rl_economic_replay": "RL economic replay evidence is missing.",
    "missing_rl_feature_bundle_hash": "The RL feature bundle hash is missing.",
    "missing_rl_oos_metrics": "RL out-of-sample metrics are missing.",
    "missing_rl_oos_provenance": "RL OOS and feature provenance evidence is missing.",
    "missing_rollback_target": "Rollback target is missing.",
    "missing_scope_approval": "Promotion approval is required for this scope.",
    "missing_signal_health_metrics": "Signal-health metrics are missing.",
    "missing_signal_rate_distribution": "Signal-rate distribution is missing.",
    "missing_threshold_stability_by_fold": "Threshold stability by fold is missing.",
    "missing_volatility_feature_provenance": "Volatility feature provenance is missing.",
    "model_roster_mismatch": "Inference model roster does not match training.",
    "signal_health_alerts_present": "Signal-health alerts are present.",
    "signal_saturation": "Signal rate is above the allowed limit.",
    "stale_or_leaked_feature_provenance": "Feature provenance is stale or leaked.",
    "tsfm_adapter_load_failure_without_tabular_fallback": (
        "TSFM adapter loading failed without a valid tabular fallback."
    ),
    "tsfm_latency_budget_failure": "TSFM latency budget failed.",
    "unstable_fold_thresholds": "Fold thresholds are unstable.",
    "weak_calibration": "Calibration is weaker than the required gate.",
}

_NESTED_RESULT_BLOCKERS = {
    "direction_auc_below_gate_or_missing",
    "missing_brier_score",
    "missing_per_regime_calibration_status",
    "missing_reliability_diagram",
    "missing_signal_rate_distribution",
    "missing_threshold_stability_by_fold",
    "unstable_fold_thresholds",
    "weak_calibration",
}

_LATE_PHASE_BLOCKERS = {
    "failed_smoke_validation": "promotion_proposal",
    "inference_adapter_load_failure": "inference_parity_replay",
    "inference_feature_schema_mismatch": "inference_parity_replay",
    "inference_reload_failed": "inference_parity_replay",
    "inference_reload_validation_missing": "inference_parity_replay",
    "missing_signal_health_metrics": "promotion_proposal",
    "model_roster_mismatch": "inference_parity_replay",
    "signal_health_alerts_present": "promotion_proposal",
    "tsfm_adapter_load_failure_without_tabular_fallback": "tsfm_sweeps",
    "tsfm_latency_budget_failure": "tsfm_sweeps",
}

_LIKELY_FIXES = {
    "actual_gate_failure": "Adjust the candidate or rerun validation until this gate passes.",
    "missing_evidence": "Produce the required evidence payload before promotion.",
    "missing_nested_result_payload": (
        "Preserve and merge the full results.json payload, especially "
        "calibration_full_validation, into metrics_json."
    ),
    "phase_not_run": "Complete the required later research phase and emit its evidence payload.",
    "tsfm_scope_mismatch": (
        "Mark tabular candidates with candidate_family=tabular and "
        "is_tsfm_candidate=false, or run the TSFM fallback checks for TSFM candidates."
    ),
}


def classify_blockers(
    blockers: Iterable[Any],
    *,
    checks: Optional[Iterable[Mapping[str, Any]]] = None,
    metrics_payload: Optional[Mapping[str, Any]] = None,
    phase_state: Optional[Mapping[str, Any]] = None,
    source: str = "promotion_preview",
) -> list[dict[str, Any]]:
    """Return stable structured details for promotion blocker codes."""

    check_by_blocker = _check_names_by_blocker(checks or ())
    details: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in blockers or ():
        code = str(raw)
        if not code or code in seen:
            continue
        seen.add(code)
        category = _category_for(
            code,
            metrics_payload=metrics_payload or {},
            phase_state=phase_state or {},
        )
        detail = {
            "code": code,
            "label": _BLOCKER_LABELS.get(code, _humanize_code(code)),
            "category": category,
            "source": source,
            "likely_fix": _LIKELY_FIXES.get(
                category,
                _LIKELY_FIXES["actual_gate_failure"],
            ),
        }
        check_name = check_by_blocker.get(code)
        if check_name:
            detail["check_name"] = check_name
        phase_id = _LATE_PHASE_BLOCKERS.get(code)
        if category == "phase_not_run" and phase_id:
            detail["phase"] = phase_id
        details.append(detail)
    return details


def blocker_details(
    blockers: Iterable[Any],
    *,
    checks: Optional[Iterable[Mapping[str, Any]]] = None,
    metrics_payload: Optional[Mapping[str, Any]] = None,
    phase_state: Optional[Mapping[str, Any]] = None,
    source: str = "promotion_preview",
) -> list[dict[str, Any]]:
    """Compatibility wrapper for call sites that only need details."""

    return classify_blockers(
        blockers,
        checks=checks,
        metrics_payload=metrics_payload,
        phase_state=phase_state,
        source=source,
    )


def _category_for(
    code: str,
    *,
    metrics_payload: Mapping[str, Any],
    phase_state: Mapping[str, Any],
) -> str:
    if code == "tsfm_adapter_load_failure_without_tabular_fallback" and not _is_tsfm_candidate(
        metrics_payload
    ):
        return "tsfm_scope_mismatch"

    phase_id = _LATE_PHASE_BLOCKERS.get(code)
    if phase_id and _phase_not_completed(phase_state, phase_id):
        return "phase_not_run"

    if code in _NESTED_RESULT_BLOCKERS and _missing_nested_result_payload(
        code,
        metrics_payload,
    ):
        return "missing_nested_result_payload"

    if code.startswith("missing_"):
        return "missing_evidence"
    return "actual_gate_failure"


def _missing_nested_result_payload(
    code: str,
    metrics_payload: Mapping[str, Any],
) -> bool:
    if not _has_result_artifact_reference(metrics_payload):
        return True

    cal_full = _first_mapping(
        _mapping_at(metrics_payload, "config").get("calibration_full_validation"),
        metrics_payload.get("calibration_full_validation"),
    )
    if code in {
        "missing_brier_score",
        "missing_reliability_diagram",
        "missing_threshold_stability_by_fold",
        "missing_signal_rate_distribution",
        "missing_per_regime_calibration_status",
        "unstable_fold_thresholds",
        "weak_calibration",
    }:
        if not cal_full:
            return True
    if code in {"direction_auc_below_gate_or_missing"}:
        return not (
            _mapping_at(metrics_payload, "metrics")
            or _mapping_at(metrics_payload, "gate_results")
        )
    if code == "missing_brier_score":
        return not _mapping_at(_mapping_at(cal_full, "selected"), "metrics")
    if code == "missing_reliability_diagram":
        return not _mapping_at(cal_full, "selected")
    if code == "missing_threshold_stability_by_fold":
        return not _mapping_at(cal_full, "threshold_stability_by_fold")
    if code == "missing_signal_rate_distribution":
        return not _mapping_at(cal_full, "signal_rate_distribution")
    if code == "missing_per_regime_calibration_status":
        return not _mapping_at(cal_full, "per_regime_calibration")
    return False


def _has_result_artifact_reference(metrics_payload: Mapping[str, Any]) -> bool:
    return bool(
        metrics_payload.get("result_artifact_path")
        or metrics_payload.get("result_artifact_sha256")
        or metrics_payload.get("result_artifact_schema_version")
    )


def _phase_not_completed(
    phase_state: Mapping[str, Any],
    phase_id: str,
) -> bool:
    phases = phase_state.get("phases")
    if not isinstance(phases, list):
        return False
    for phase in phases:
        if isinstance(phase, Mapping) and phase.get("id") == phase_id:
            return phase.get("status") != "completed"
    return False


def _check_names_by_blocker(
    checks: Iterable[Mapping[str, Any]],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for check in checks:
        if not isinstance(check, Mapping):
            continue
        reason = check.get("reason")
        status = check.get("status")
        name = check.get("name")
        if reason and status in {"failed", "warning"} and name:
            result.setdefault(str(reason), str(name))
    return result


def _is_tsfm_candidate(metrics_payload: Mapping[str, Any]) -> bool:
    inference = _first_mapping(
        metrics_payload.get("inference_parity"),
        metrics_payload.get("inference_validation"),
        metrics_payload.get("inference"),
        metrics_payload.get("inference_reload_validation"),
    )
    if any(
        value is True
        for value in (
            metrics_payload.get("is_tsfm_candidate"),
            metrics_payload.get("tsfm_candidate"),
            inference.get("is_tsfm_candidate"),
            inference.get("tsfm_candidate"),
        )
    ):
        return True
    for value in (
        metrics_payload.get("model_family"),
        metrics_payload.get("candidate_family"),
        inference.get("model_family"),
        inference.get("candidate_family"),
    ):
        if isinstance(value, str) and value.strip().lower() in {
            "tsfm",
            "ts-fm",
            "timesfm",
        }:
            return True
    return False


def _first_mapping(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _mapping_at(root: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = root.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _humanize_code(value: str) -> str:
    text = value.replace("_", " ").strip()
    return text[:1].upper() + text[1:] + "." if text else "Unknown blocker."
