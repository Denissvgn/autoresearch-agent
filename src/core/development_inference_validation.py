"""Inference reload/parity validation summaries for development promotion."""

from __future__ import annotations

from typing import Any, Dict


def build_development_inference_validation(
    *,
    metrics_payload: Dict[str, Any],
    rollback_readiness: Dict[str, Any],
    smoke_validation: Dict[str, Any],
) -> Dict[str, Any]:
    """Normalize DPU-073 inference parity and reload evidence."""

    inference = _first_dict(
        metrics_payload.get("inference_reload_validation"),
        metrics_payload.get("inference_parity"),
        metrics_payload.get("inference_validation"),
        metrics_payload.get("inference"),
    )
    adapter = _first_dict(inference.get("adapter"), inference.get("tsfm_adapter"))
    composite = _first_dict(
        metrics_payload.get("composite_metadata"),
        metrics_payload.get("composite"),
    )
    rl = _first_dict(
        inference.get("rl"),
        inference.get("observation"),
        metrics_payload.get("rl_inference_parity"),
    )
    tsfm_required = _is_tsfm_candidate(metrics_payload, inference)
    obs_changed = any(
        value is True
        for value in (
            metrics_payload.get("rl_observation_changed"),
            metrics_payload.get("obs_spec_changed"),
            inference.get("rl_observation_changed"),
            inference.get("obs_spec_changed"),
            rl.get("observation_changed"),
            rl.get("obs_spec_changed"),
        )
    )

    checks = {
        "feature_name_alignment_passed": _bool_field(
            inference,
            "feature_name_alignment_passed",
            "feature_names_aligned",
            "feature_name_alignment",
        ),
        "feature_count_alignment_passed": _bool_field(
            inference,
            "feature_count_alignment_passed",
            "feature_count_aligned",
            "feature_count_alignment",
        ),
        "model_roster_parity_passed": _bool_field(
            inference,
            "model_roster_parity_passed",
            "roster_parity_passed",
            "model_roster_matches",
        ),
        "adapter_loading_passed": _bool_field(
            inference,
            "adapter_loading_passed",
            "adapter_loaded",
            "tsfm_adapter_loaded",
        )
        or _bool_field(adapter, "loaded", "adapter_loaded"),
        "observation_dimension_parity_passed": (
            True
            if not obs_changed
            else _bool_field(
                inference,
                "observation_dimension_parity_passed",
                "obs_dim_parity_passed",
            )
            or _bool_field(
                rl,
                "observation_dimension_parity_passed",
                "obs_dim_parity_passed",
                "dimension_parity_passed",
            )
        ),
        "fallback_behavior_passed": (
            True
            if not tsfm_required
            else _bool_field(
                inference,
                "fallback_check_passed",
                "tabular_fallback_passed",
                "fallback_available",
            )
            or _bool_field(adapter, "fallback_check_passed", "fallback_available")
        ),
        "latency_budget_passed": (
            True
            if not tsfm_required
            else _bool_field(
                inference,
                "latency_budget_passed",
                "tsfm_latency_budget_passed",
            )
            or _bool_field(adapter, "latency_budget_passed")
        ),
        "composite_reload_passed": _bool_field(
            inference,
            "composite_reload_passed",
            "composite_reload_supported",
            "reload_supported",
        )
        or _bool_field(
            smoke_validation,
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
        "rollback_ready": bool(
            rollback_readiness.get("rollback_target")
            and rollback_readiness.get("rollback_by_instrument_timeframe_supported")
        ),
        "prior_version_preserved_on_reload_failure": _bool_field(
            rollback_readiness,
            "prior_version_left_intact_on_failure",
            "previous_development_version_addressable",
        ),
    }
    required = {
        "feature_name_alignment_passed",
        "feature_count_alignment_passed",
        "model_roster_parity_passed",
        "adapter_loading_passed",
        "observation_dimension_parity_passed",
        "fallback_behavior_passed",
        "latency_budget_passed",
        "composite_reload_passed",
        "rollback_ready",
        "prior_version_preserved_on_reload_failure",
    }
    failed = sorted(name for name in required if checks.get(name) is not True)
    return {
        "schema_version": "development_inference_reload_validation.v1",
        "source": "autoresearch_config_promoter",
        "passed": not failed,
        "failed_checks": failed,
        "checks": checks,
        "requirements": {
            "tsfm_fallback_required": tsfm_required,
            "rl_observation_changed": obs_changed,
        },
        "details": {
            "inference": inference,
            "adapter": adapter,
            "composite": composite,
        },
    }


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _bool_field(container: Dict[str, Any], *keys: str) -> bool:
    return any(container.get(key) is True for key in keys)


def _is_tsfm_candidate(
    metrics_payload: Dict[str, Any],
    inference: Dict[str, Any],
) -> bool:
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
        if isinstance(value, str) and value.lower() in {"tsfm", "ts-fm", "timesfm"}:
            return True
    return False
