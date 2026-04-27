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

