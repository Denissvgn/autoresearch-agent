"""Cross-service consistency validation for autoresearch candidates."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional


def build_consistency_report(
    *,
    research_id: str,
    iteration: int,
    model_type: str,
    config_snapshot: Optional[str],
    metrics_payload: Optional[Dict[str, Any]] = None,
    attempt_snapshot: Optional[Dict[str, Any]] = None,
    preflight: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a readable cross-service candidate consistency report."""

    metrics = metrics_payload or {}
    attempt = attempt_snapshot or {}
    preflight = preflight or {}
    checks: list[Dict[str, Any]] = []
    blockers: list[str] = []

    def add(
        name: str,
        status: str,
        *,
        blocker: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        checks.append({"name": name, "status": status, "detail": detail})
        if blocker and status == "failed":
            blockers.append(blocker)

    promotable = bool(
        metrics.get("all_gates_passed")
        or metrics.get("finalist")
        or metrics.get("promotion_candidate")
    )

    add(
        "config_snapshot_present",
        "passed" if bool(config_snapshot) else "failed",
        blocker="missing_config_snapshot",
    )
    config_sha = _sha256_text(config_snapshot)
    artifact_hash = _first_present(
        attempt,
        metrics,
        "artifact_hash",
        "model_artifact_hash",
    )
    artifact_ref = artifact_hash or metrics.get("artifact_uri") or metrics.get("mlflow_run_id")
    add(
        "artifact_reference_present",
        "passed" if artifact_ref else ("failed" if promotable else "warning"),
        blocker="missing_artifact_reference" if promotable else None,
    )

    calibration = _calibration_payload(metrics)
    add(
        "calibration_diagnostics_present",
        "passed" if calibration else ("failed" if promotable and model_type in {"direction", "volatility"} else "warning"),
        blocker="missing_calibration_diagnostics"
        if promotable and model_type in {"direction", "volatility"}
        else None,
    )
    replay = metrics.get("economic_replay")
    replay_ok = _nested_bool(replay, ("gates", "all_gates_passed"))
    if replay is None:
        add(
            "economic_replay_present",
            "failed" if promotable and model_type in {"direction", "volatility"} else "warning",
            blocker="missing_economic_replay"
            if promotable and model_type in {"direction", "volatility"}
            else None,
        )
    else:
        add(
            "economic_replay_gates",
            "passed" if replay_ok is not False else "failed",
            blocker="failed_economic_replay",
        )

    parity = metrics.get("inference_parity") or preflight.get("inference_reload_validation")
    if isinstance(parity, dict):
        parity_passed = _all_true(
            parity,
            (
                "feature_name_alignment_passed",
                "feature_count_alignment_passed",
                "model_roster_parity_passed",
            ),
        )
        if parity_passed is None:
            parity_passed = parity.get("passed")
        add(
            "inference_feature_roster_parity",
            "passed" if parity_passed is not False else "failed",
            blocker="inference_feature_schema_mismatch",
        )
    else:
        add(
            "inference_feature_roster_parity",
            "failed" if promotable else "warning",
            blocker="missing_inference_parity" if promotable else None,
        )

    feature_hash = _first_present(
        attempt,
        metrics,
        "feature_schema_hash",
        "schema_hash",
    )
    add(
        "feature_schema_hash_recorded",
        "passed" if feature_hash else "warning",
    )

    if model_type == "rl":
        obs_hash = _first_present(attempt, metrics, "obs_spec_hash", "observation_spec_hash")
        add(
            "obs_spec_hash_recorded",
            "passed" if obs_hash else ("failed" if promotable else "warning"),
            blocker="missing_obs_spec_hash" if promotable else None,
        )
        rl_oos = metrics.get("rl_oos")
        add(
            "rl_oos_gates_present",
            "passed" if isinstance(rl_oos, dict) else ("failed" if promotable else "warning"),
            blocker="missing_rl_oos_gates" if promotable else None,
        )
        if isinstance(rl_oos, dict):
            direction_provenance = _rl_channel_provenance(metrics, rl_oos, "direction")
            volatility_provenance = _rl_channel_provenance(metrics, rl_oos, "volatility")
            add(
                "rl_direction_feature_provenance_present",
                "passed"
                if direction_provenance
                else ("failed" if promotable else "warning"),
                blocker="missing_direction_feature_provenance"
                if promotable
                else None,
            )
            add(
                "rl_volatility_feature_provenance_present",
                "passed"
                if volatility_provenance
                else ("failed" if promotable else "warning"),
                blocker="missing_volatility_feature_provenance"
                if promotable
                else None,
            )
            add(
                "rl_feature_bundle_hash_recorded",
                "passed"
                if _rl_feature_bundle_hash(metrics, rl_oos)
                else ("failed" if promotable else "warning"),
                blocker="missing_rl_feature_bundle_hash" if promotable else None,
            )
            add(
                "rl_nested_or_blocked_validation_present",
                "passed"
                if _rl_nested_validation_present(rl_oos)
                else ("failed" if promotable else "warning"),
                blocker="missing_nested_validation" if promotable else None,
            )
            add(
                "rl_multi_seed_validation_present",
                "passed"
                if _rl_multi_seed_present(rl_oos)
                else ("failed" if promotable else "warning"),
                blocker="missing_multi_seed_rl_validation" if promotable else None,
            )
            add(
                "rl_oos_metrics_present",
                "passed"
                if _rl_required_metrics_present(rl_oos)
                else ("failed" if promotable else "warning"),
                blocker="missing_rl_oos_metrics" if promotable else None,
            )
            add(
                "rl_no_direction_feature_fallback",
                "passed"
                if not _rl_unsafe_feature_provenance(direction_provenance)
                else ("failed" if promotable else "warning"),
                blocker="proxy_or_neutral_direction_proba_fallback"
                if promotable
                else None,
            )
            add(
                "rl_no_volatility_feature_fallback",
                "passed"
                if not _rl_unsafe_feature_provenance(volatility_provenance)
                else ("failed" if promotable else "warning"),
                blocker="proxy_or_neutral_volatility_feature_fallback"
                if promotable
                else None,
            )

    rollback = preflight.get("rollback_readiness") or metrics.get("rollback_readiness")
    rollback_target = (
        metrics.get("rollback_target")
        or preflight.get("rollback_target")
        or (rollback or {}).get("rollback_target")
    )
    add(
        "rollback_target_addressable",
        "passed" if rollback_target else ("failed" if promotable else "warning"),
        blocker="missing_rollback_target" if promotable else None,
    )

    smoke = preflight.get("smoke_validation") or metrics.get("smoke_validation")
    smoke_passed = smoke.get("passed") if isinstance(smoke, dict) else None
    add(
        "smoke_or_paper_validation",
        "passed" if smoke_passed is True else ("failed" if promotable else "warning"),
        blocker="failed_smoke_validation" if promotable else None,
    )

    docs_status = metrics.get("docs_wiki_status")
    add(
        "docs_wiki_status_recorded",
        "passed" if docs_status else "warning",
    )

    return {
        "schema_version": "cross_service_consistency_report.v1",
        "research_id": research_id,
        "iteration": iteration,
        "model_type": model_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": not blockers,
        "blockers": _dedupe(blockers),
        "checks": checks,
        "config_snapshot_sha256": config_sha,
        "artifact_hash": artifact_hash,
        "feature_schema_hash": feature_hash,
        "mlflow_run_id": metrics.get("mlflow_run_id") or attempt.get("mlflow_run_id"),
    }


def consistency_report_json(report: Dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True)


def parse_consistency_report(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _calibration_payload(metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    config = metrics.get("config")
    if isinstance(config, dict) and isinstance(
        config.get("calibration_full_validation"), dict
    ):
        return config["calibration_full_validation"]
    calibration = metrics.get("calibration_full_validation")
    return calibration if isinstance(calibration, dict) else None


def _nested_bool(container: Any, path: Iterable[str]) -> Optional[bool]:
    current = container
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, bool) else None


def _all_true(container: Dict[str, Any], keys: Iterable[str]) -> Optional[bool]:
    values = [container.get(key) for key in keys if key in container]
    if not values:
        return None
    return all(value is True for value in values)


def _first_present(
    primary: Dict[str, Any],
    secondary: Dict[str, Any],
    *keys: str,
) -> Any:
    for container in (primary, secondary):
        for key in keys:
            value = container.get(key)
            if value is not None:
                return value
    return None


def _sha256_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dict_at(root: Any, *path: str) -> Dict[str, Any]:
    value = root
    for key in path:
        if not isinstance(value, dict):
            return {}
        value = value.get(key)
    return value if isinstance(value, dict) else {}


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


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


def _rl_channel_provenance(
    metrics: Dict[str, Any],
    rl_oos: Dict[str, Any],
    channel: str,
) -> Dict[str, Any]:
    feature_provenance = _first_dict(
        rl_oos.get("feature_provenance"),
        rl_oos.get("feature_provenance_by_channel"),
        metrics.get("feature_provenance"),
        metrics.get("feature_provenance_by_channel"),
    )
    probability_provenance = _first_dict(
        rl_oos.get("probability_provenance"),
        metrics.get("probability_provenance"),
    )
    return _first_dict(
        rl_oos.get(f"{channel}_probability_provenance"),
        rl_oos.get(f"{channel}_feature_provenance"),
        metrics.get(f"{channel}_probability_provenance"),
        metrics.get(f"{channel}_feature_provenance"),
        feature_provenance.get(channel),
        probability_provenance.get(channel),
    )


def _rl_feature_bundle_hash(
    metrics: Dict[str, Any],
    rl_oos: Dict[str, Any],
) -> Optional[str]:
    candidates = (
        rl_oos.get("feature_bundle_hash"),
        rl_oos.get("rl_feature_bundle_hash"),
        rl_oos.get("dataset_hash"),
        rl_oos.get("enriched_dataset_hash"),
        metrics.get("feature_bundle_hash"),
        metrics.get("rl_feature_bundle_hash"),
        metrics.get("dataset_hash"),
        metrics.get("enriched_dataset_hash"),
        _dict_at(rl_oos, "feature_bundle").get("hash"),
        _dict_at(rl_oos, "rl_dataset").get("feature_bundle_hash"),
    )
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _rl_nested_validation_present(rl_oos: Dict[str, Any]) -> bool:
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
    folds = rl_oos.get("folds")
    if isinstance(folds, list) and folds:
        return all(bool(_dict_at(fold, "validation")) for fold in folds if isinstance(fold, dict))
    return bool(_dict_at(rl_oos, "validation"))


def _rl_multi_seed_present(rl_oos: Dict[str, Any]) -> bool:
    n_seed_trials = _first_number(rl_oos.get("n_seed_trials"))
    if n_seed_trials is not None and n_seed_trials >= 2:
        return True
    folds = rl_oos.get("folds")
    if isinstance(folds, list) and folds:
        for fold in folds:
            if not isinstance(fold, dict):
                continue
            fold_trials = _first_number(
                fold.get("n_seed_trials"),
                _dict_at(fold, "validation").get("n_seed_trials"),
                _dict_at(fold, "oos").get("n_seed_trials"),
            )
            if fold_trials is not None and fold_trials >= 2:
                return True
    return rl_oos.get("multi_seed") is True


def _rl_required_metrics_present(rl_oos: Dict[str, Any]) -> bool:
    required = (
        "oos_sharpe",
        "return",
        "drawdown",
        "trade_count",
        "mean_absolute_position",
        "flip_count",
        "folds_passed",
    )
    metrics = _first_dict(
        rl_oos.get("metrics"),
        rl_oos.get("aggregate"),
        rl_oos.get("oos"),
        rl_oos,
    )
    return all(_rl_metric_value(metrics, name) is not None for name in required)


def _rl_metric_value(metrics: Dict[str, Any], name: str) -> Optional[float]:
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
        "flip_count": ("flip_count", "flips", "oos_flips", "mean_flip_count"),
        "folds_passed": ("folds_passed",),
        "oos_sharpe": ("oos_sharpe", "mean_oos_sharpe", "sharpe"),
    }
    candidates = aliases.get(name, (name, f"mean_{name}", f"mean_oos_{name}"))
    return _first_number(*(metrics.get(candidate) for candidate in candidates))


def _rl_unsafe_feature_provenance(provenance: Dict[str, Any]) -> bool:
    if not provenance:
        return False
    unsafe_count = _first_number(provenance.get("unsafe_count")) or 0
    unsafe_values = _string_list(provenance.get("unsafe_values"))
    status_values = []
    for key in (
        "status",
        "quality",
        "provenance",
        "provenance_status",
        "oof_status",
        "source",
    ):
        status_values.extend(_string_list(provenance.get(key)))
    if any(
        _truthy(provenance.get(key))
        for key in (
            "fallback_used",
            "neutral_fallback_used",
            "proxy_used",
            "synthetic_fallback_used",
            "stale",
            "leaked",
        )
    ):
        return True
    unsafe_tokens = {
        "fallback",
        "legacy_inferred",
        "leak",
        "neutral",
        "proxy",
        "sdk_proxy",
        "stale",
        "synthetic",
        "unknown",
    }
    return unsafe_count > 0 or any(
        any(token in value for token in unsafe_tokens)
        and "quasi_oof" not in value
        and value != "oof"
        for value in status_values + unsafe_values
    )


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
