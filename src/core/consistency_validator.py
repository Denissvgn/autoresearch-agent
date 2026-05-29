"""Cross-service consistency validation for autoresearch candidates."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Set

from src.core.artifact_reference import (
    first_valid_artifact_ref,
    is_sentinel_artifact_ref,
    normalize_optional_artifact_ref,
)
from src.core.gate_status import training_gates_passed_from

logger = logging.getLogger(__name__)

# AR-5: phases that require artifact-presence validation before marking complete.
EVIDENCE_ARTIFACT_PHASES: frozenset = frozenset(
    {
        "multi_seed_robustness",
        "inference_parity_replay",
        "calibration_replay_gates",
        "promotion_proposal",
    }
)

ADAPTIVE_FEATURE_PHASE_ID = "adaptive_feature_sweeps"
ACCEPTED_ADAPTIVE_NOOP_REASONS: frozenset[str] = frozenset(
    {
        "adaptive_features_unavailable",
        "adaptive_feature_schema_unchanged",
        "adaptive_not_applicable",
    }
)
REJECTED_ADAPTIVE_NOOP_REASONS: frozenset[str] = frozenset(
    {
        "adaptive_flag_not_applied",
        "adaptive_feature_requested_but_inactive",
        "adaptive_enabled_no_selected_features",
    }
)


def _normalize_report_mode(mode: Optional[str]) -> Optional[str]:
    if mode is None:
        return None
    normalized = str(mode).strip().lower()
    if normalized not in {"sweep", "finalist", "promotion"}:
        raise ValueError(f"Unknown consistency report mode: {mode!r}")
    return normalized


def build_consistency_report(
    *,
    research_id: str,
    iteration: int,
    model_type: str,
    config_snapshot: Optional[str],
    metrics_payload: Optional[Dict[str, Any]] = None,
    attempt_snapshot: Optional[Dict[str, Any]] = None,
    preflight: Optional[Dict[str, Any]] = None,
    search_phase: Optional[str] = None,
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a readable cross-service candidate consistency report."""

    metrics = metrics_payload or {}
    attempt = attempt_snapshot or {}
    preflight = preflight or {}
    model_type = str(model_type or "").strip().lower()
    report_mode = _normalize_report_mode(mode)
    strict_mode = report_mode in {"finalist", "promotion"}
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

    # A candidate is "promotable" (eligible for hard consistency blockers) only
    # when the agent has explicitly nominated it as a finalist or promotion
    # candidate, OR when training gates passed AND late-phase evidence is
    # already present (calibration/replay/inference data from later research
    # phases).  Early tabular sweeps that pass primary gates alone must NOT
    # trigger hard blockers — those checks are meaningful only for finalists
    # that have completed the calibration/replay and inference-parity phases.
    _has_late_phase_evidence = bool(
        not metrics.get("auto_phase_evidence")
        and (
            metrics.get("calibration_full_validation")
            or (
                isinstance(metrics.get("config"), dict)
                and metrics["config"].get("calibration_full_validation")
            )
            or metrics.get("economic_replay")
            or metrics.get("inference_parity")
            or metrics.get("inference_reload_validation")
        )
    )
    promotable = bool(
        metrics.get("finalist")
        or metrics.get("promotion_candidate")
        or (training_gates_passed_from(metrics) and _has_late_phase_evidence)
    )
    hard_consistency = strict_mode or (report_mode is None and promotable)

    add(
        "config_snapshot_present",
        "passed" if bool(config_snapshot) else "failed",
        blocker="missing_config_snapshot",
    )
    config_sha = _sha256_text(config_snapshot)
    invalid_mlflow_run_id = any(
        is_sentinel_artifact_ref(container.get("mlflow_run_id"))
        for container in (metrics, attempt)
        if isinstance(container, dict) and "mlflow_run_id" in container
    )
    add(
        "mlflow_run_id_valid",
        "failed" if invalid_mlflow_run_id else "passed",
        blocker="invalid_mlflow_run_id_sentinel",
    )
    artifact_hash = first_valid_artifact_ref(
        attempt.get("artifact_hash"),
        attempt.get("model_artifact_hash"),
        metrics.get("artifact_hash"),
        metrics.get("model_artifact_hash"),
    )
    result_artifact_ref = None
    result_artifact_path = first_valid_artifact_ref(
        attempt.get("result_artifact_path"),
        metrics.get("result_artifact_path"),
    )
    result_artifact_sha = first_valid_artifact_ref(
        attempt.get("result_artifact_sha256"),
        metrics.get("result_artifact_sha256"),
    )
    if result_artifact_path and result_artifact_sha:
        result_artifact_ref = result_artifact_path
    mlflow_run_id = first_valid_artifact_ref(
        metrics.get("mlflow_run_id"),
        attempt.get("mlflow_run_id"),
    )
    artifact_ref = (
        artifact_hash
        or first_valid_artifact_ref(metrics.get("artifact_uri"), attempt.get("artifact_uri"))
        or mlflow_run_id
        or result_artifact_ref
    )
    add(
        "artifact_reference_present",
        "passed" if artifact_ref else ("failed" if hard_consistency else "warning"),
        blocker="missing_artifact_reference" if hard_consistency else None,
    )

    calibration = _calibration_payload(metrics)
    add(
        "calibration_diagnostics_present",
        "passed"
        if calibration
        else (
            "failed"
            if hard_consistency and model_type in {"direction", "volatility"}
            else "warning"
        ),
        blocker="missing_calibration_diagnostics"
        if hard_consistency and model_type in {"direction", "volatility"}
        else None,
    )
    replay = (
        _rl_economic_replay_payload(metrics)
        if model_type == "rl"
        else metrics.get("economic_replay")
    )
    replay_ok = _nested_bool(replay, ("gates", "all_gates_passed"))
    if replay is None:
        add(
            "economic_replay_present",
            "failed" if hard_consistency and model_type == "rl" else "warning",
            blocker="missing_economic_replay"
            if hard_consistency and model_type == "rl"
            else None,
        )
    else:
        add(
            "economic_replay_gates",
            "passed"
            if replay_ok is not False
            else ("failed" if model_type == "rl" else "warning"),
            blocker="failed_economic_replay" if model_type == "rl" else None,
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
            "failed" if hard_consistency else "warning",
            blocker="missing_inference_parity" if hard_consistency else None,
        )

    parity_metadata = _dict_at(metrics, "parity_metadata")
    feature_schema = _dict_at(metrics, "feature_schema")
    feature_hash = first_valid_artifact_ref(
        parity_metadata.get("feature_schema_hash"),
        feature_schema.get("feature_schema_hash"),
        metrics.get("feature_schema_hash"),
        metrics.get("schema_hash"),
        attempt.get("feature_schema_hash"),
        attempt.get("schema_hash"),
    )
    add(
        "feature_schema_hash_recorded",
        "passed"
        if feature_hash
        else (
            "failed"
            if hard_consistency and model_type in {"direction", "volatility"}
            else "warning"
        ),
        blocker="missing_feature_schema_hash"
        if hard_consistency
        and model_type in {"direction", "volatility"}
        and not feature_hash
        else None,
    )
    adaptive_schema_blocker = _adaptive_schema_flags_blocker(metrics)
    if adaptive_schema_blocker:
        adaptive_schema_status = (
            "failed"
            if hard_consistency or search_phase == ADAPTIVE_FEATURE_PHASE_ID
            else "warning"
        )
        add(
            "adaptive_feature_schema_flags_recorded",
            adaptive_schema_status,
            blocker=adaptive_schema_blocker
            if adaptive_schema_status == "failed"
            else None,
        )
    else:
        add(
            "adaptive_feature_schema_flags_recorded",
            "passed",
        )

    if model_type == "rl":
        obs_hash = _first_present(attempt, metrics, "obs_spec_hash", "observation_spec_hash")
        add(
            "obs_spec_hash_recorded",
            "passed" if obs_hash else ("failed" if hard_consistency else "warning"),
            blocker="missing_obs_spec_hash" if hard_consistency else None,
        )
        rl_oos = metrics.get("rl_oos")
        add(
            "rl_oos_gates_present",
            "passed"
            if isinstance(rl_oos, dict)
            else ("failed" if hard_consistency else "warning"),
            blocker="missing_rl_oos_gates" if hard_consistency else None,
        )
        if isinstance(rl_oos, dict):
            direction_provenance = _rl_channel_provenance(metrics, rl_oos, "direction")
            volatility_provenance = _rl_channel_provenance(metrics, rl_oos, "volatility")
            add(
                "rl_direction_feature_provenance_present",
                "passed"
                if direction_provenance
                else ("failed" if hard_consistency else "warning"),
                blocker="missing_direction_feature_provenance"
                if hard_consistency
                else None,
            )
            add(
                "rl_volatility_feature_provenance_present",
                "passed"
                if volatility_provenance
                else ("failed" if hard_consistency else "warning"),
                blocker="missing_volatility_feature_provenance"
                if hard_consistency
                else None,
            )
            add(
                "rl_feature_bundle_hash_recorded",
                "passed"
                if _rl_feature_bundle_hash(metrics, rl_oos)
                else ("failed" if hard_consistency else "warning"),
                blocker="missing_rl_feature_bundle_hash" if hard_consistency else None,
            )
            add(
                "rl_nested_or_blocked_validation_present",
                "passed"
                if _rl_nested_validation_present(rl_oos)
                else ("failed" if hard_consistency else "warning"),
                blocker="missing_nested_validation" if hard_consistency else None,
            )
            add(
                "rl_multi_seed_validation_present",
                "passed"
                if _rl_multi_seed_present(rl_oos)
                else ("failed" if hard_consistency else "warning"),
                blocker="missing_multi_seed_rl_validation" if hard_consistency else None,
            )
            add(
                "rl_oos_metrics_present",
                "passed"
                if _rl_required_metrics_present(rl_oos)
                else ("failed" if hard_consistency else "warning"),
                blocker="missing_rl_oos_metrics" if hard_consistency else None,
            )
            add(
                "rl_no_direction_feature_fallback",
                "passed"
                if not _rl_unsafe_feature_provenance(direction_provenance)
                else ("failed" if hard_consistency else "warning"),
                blocker="proxy_or_neutral_direction_proba_fallback"
                if hard_consistency
                else None,
            )
            add(
                "rl_no_volatility_feature_fallback",
                "passed"
                if not _rl_unsafe_feature_provenance(volatility_provenance)
                else ("failed" if hard_consistency else "warning"),
                blocker="proxy_or_neutral_volatility_feature_fallback"
                if hard_consistency
                else None,
            )
        if isinstance(replay, dict):
            replay_hash = first_valid_artifact_ref(
                replay.get("artifact_hash"),
                replay.get("replay_artifact_hash"),
                metrics.get("rl_economic_replay_artifact_hash"),
            )
            add(
                "rl_economic_replay_artifact_hash_recorded",
                "passed"
                if replay_hash
                else ("failed" if hard_consistency else "warning"),
                blocker="missing_rl_economic_replay_artifact_hash"
                if hard_consistency
                else None,
            )
            add(
                "rl_economic_replay_assumptions_present",
                "passed"
                if _rl_replay_assumptions_present(replay)
                else ("failed" if hard_consistency else "warning"),
                blocker="missing_rl_replay_assumptions" if hard_consistency else None,
            )
            add(
                "rl_profit_score_present",
                "passed"
                if _first_number(
                    replay.get("rl_profit_score"),
                    metrics.get("rl_profit_score"),
                )
                is not None
                else ("failed" if hard_consistency else "warning"),
                blocker="missing_rl_profit_score" if hard_consistency else None,
            )
            replay_worsening = _rl_replay_worse_than_baseline(replay)
            add(
                "rl_economic_replay_not_worse_than_baseline",
                "passed"
                if not replay_worsening
                else ("failed" if hard_consistency else "warning"),
                blocker="worsening_post_cost_replay" if hard_consistency else None,
                detail=json.dumps(replay_worsening, sort_keys=True)
                if replay_worsening
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
        "passed" if rollback_target else ("failed" if hard_consistency else "warning"),
        blocker="missing_rollback_target" if hard_consistency else None,
    )

    smoke = preflight.get("smoke_validation") or metrics.get("smoke_validation")
    smoke_passed = smoke.get("passed") if isinstance(smoke, dict) else None
    add(
        "smoke_or_paper_validation",
        "passed" if smoke_passed is True else ("failed" if hard_consistency else "warning"),
        blocker="failed_smoke_validation" if hard_consistency else None,
    )

    docs_status = metrics.get("docs_wiki_status")
    add(
        "docs_wiki_status_recorded",
        "passed" if docs_status else "warning",
    )

    if search_phase == ADAPTIVE_FEATURE_PHASE_ID:
        adaptive_blocker = check_adaptive_feature_sweep(metrics)
        add(
            "adaptive_feature_sweep_effective",
            "passed" if adaptive_blocker is None else "failed",
            blocker=adaptive_blocker,
        )

    # AR-5: artifact-bound evidence-key validation for promotion-family phases.
    if search_phase and search_phase in EVIDENCE_ARTIFACT_PHASES:
        artifact_blocker = check_evidence_artifact(metrics, search_phase)
        add(
            "evidence_artifact_present",
            "passed" if artifact_blocker is None else "failed",
            blocker=artifact_blocker,
        )

    return {
        "schema_version": "cross_service_consistency_report.v1",
        "research_id": research_id,
        "iteration": iteration,
        "model_type": model_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": report_mode or "legacy",
        "passed": not blockers,
        "blockers": _dedupe(blockers),
        "checks": checks,
        "config_snapshot_sha256": config_sha,
        "artifact_hash": artifact_hash,
        "feature_schema_hash": feature_hash,
        "mlflow_run_id": mlflow_run_id,
    }


def check_adaptive_feature_sweep(metrics: Dict[str, Any]) -> Optional[str]:
    """Return None when adaptive feature evidence proves a real or accepted sweep."""

    evidence = _adaptive_feature_evidence(metrics)
    noop_reason = str(evidence.get("noop_reason") or "").strip()
    if noop_reason:
        if noop_reason in ACCEPTED_ADAPTIVE_NOOP_REASONS:
            return None
        if noop_reason == "adaptive_enabled_no_selected_features":
            return "adaptive_feature_requested_but_no_selected_features"
        if noop_reason in REJECTED_ADAPTIVE_NOOP_REASONS:
            return "adaptive_feature_requested_but_inactive"
        return "adaptive_feature_noop_reason_unrecognized"

    if not evidence.get("present"):
        return "adaptive_feature_evidence_missing"
    if evidence.get("requested") and not evidence.get("enabled"):
        return "adaptive_feature_requested_but_inactive"
    if evidence.get("enabled") and int(evidence.get("selected_count") or 0) <= 0:
        return "adaptive_feature_requested_but_no_selected_features"
    if not evidence.get("requested") and not evidence.get("enabled"):
        # Issue 6 (Fix B): not requested AND not enabled is a legitimate
        # "agent hasn't attempted adaptive yet" state — let the phase
        # next_action / SKILL.md guidance steer the next iteration rather
        # than hard-blocking THIS one. The adaptive_feature_not_enabled
        # blocker (below) is reserved for the gaming-detection case
        # (requested=True AND enabled=False) which the line above already
        # raises as adaptive_feature_requested_but_inactive.
        return None
    if not evidence.get("enabled"):
        return "adaptive_feature_not_enabled"
    return None


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


def check_evidence_artifact(
    metrics: Dict[str, Any],
    phase_id: str,
    *,
    prior_run_ids: Optional[Set[str]] = None,
) -> Optional[str]:
    """Return None on pass or a blocker string on failure.

    Validates that phase evidence keys point to real, distinct artifacts rather
    than synthetic/recycled placeholders emitted by the LLM.

    force_evidence_acceptance: True in ``metrics`` skips all checks (escape hatch
    for legitimate pipeline reuse where artifacts are truly shared).
    """
    if metrics.get("force_evidence_acceptance") is True:
        logger.warning(
            "check_evidence_artifact: force_evidence_acceptance=True for phase %s — skipping artifact validation",
            phase_id,
        )
        return None

    if phase_id == "multi_seed_robustness":
        trials = metrics.get("seed_trials")
        if not isinstance(trials, list) or not trials:
            return "evidence_artifact_missing_for_multi_seed_robustness"
        n_required = metrics.get("n_seed_trials", 2)
        if not isinstance(n_required, int) or n_required < 1:
            n_required = 2
        unique_ids: set[str] = set()
        for t in trials:
            if not isinstance(t, dict):
                continue
            run_id = first_valid_artifact_ref(
                t.get("mlflow_run_id"),
                t.get("artifact_hash"),
            )
            if run_id:
                unique_ids.add(run_id)
        if len(unique_ids) < n_required:
            return "evidence_artifact_missing_for_multi_seed_robustness"
        return None

    if phase_id == "inference_parity_replay":
        parity = metrics.get("inference_parity")
        if not isinstance(parity, dict):
            return "evidence_artifact_missing_for_inference_parity_replay"
        if not parity.get("feature_count_alignment_passed"):
            return "evidence_artifact_missing_for_inference_parity_replay"
        if prior_run_ids is not None:
            run_id = first_valid_artifact_ref(
                parity.get("mlflow_run_id"),
                metrics.get("mlflow_run_id"),
            )
            normalized_prior_ids = {
                normalized
                for value in prior_run_ids
                if (normalized := normalize_optional_artifact_ref(value))
            }
            if not run_id or run_id in normalized_prior_ids:
                return "evidence_artifact_missing_for_inference_parity_replay"
        return None

    if phase_id == "calibration_replay_gates":
        cal = (
            metrics.get("calibration_full_validation")
            or (
                metrics.get("config", {}).get("calibration_full_validation")
                if isinstance(metrics.get("config"), dict)
                else None
            )
        )
        if not isinstance(cal, dict):
            return "evidence_artifact_missing_for_calibration_replay_gates"
        selected = cal.get("selected")
        if not isinstance(selected, dict) or not first_valid_artifact_ref(
            selected.get("run_id"),
            selected.get("mlflow_run_id"),
            selected.get("artifact_hash"),
        ):
            return "evidence_artifact_missing_for_calibration_replay_gates"
        # economic_replay.gates may be nested inside calibration_full_validation
        # or at the top level of metrics (both layouts are valid).
        economic = cal.get("economic_replay") or metrics.get("economic_replay")
        if not isinstance(economic, dict) or not isinstance(
            economic.get("gates"), dict
        ):
            return "evidence_artifact_missing_for_calibration_replay_gates"
        return None

    if phase_id == "promotion_proposal":
        dev_meta = metrics.get("development_promotion_metadata")
        if dev_meta is None:
            # Key absent — conservative: don't block, not enough info.
            return None
        if not isinstance(dev_meta, dict):
            return "evidence_artifact_missing_for_promotion_proposal"
        if not dev_meta.get("rollback_target"):
            return "evidence_artifact_missing_for_promotion_proposal"
        return None

    # Phase not in scope — no artifact check required.
    return None


def _is_synthetic_promotion_iteration(
    metrics: Dict[str, Any],
    prior_best_metrics: Dict[str, Any],
    phase_id: str,
) -> Optional[str]:
    """Return a blocker string when an iteration appears synthetic (no real work ran).

    A promotion-family iteration is **synthetic** when ALL of:
    1. ``training_time_s`` is ``None`` — no training command was actually executed.
    2. ``primary_metric`` rounded to 4 d.p. equals the prior-best iteration's
       ``primary_metric`` — the metric value was copied rather than computed.
    3. No new ``mlflow_run_id`` — either absent or identical to the prior-best run.

    **Exception:** not synthetic when ``development_promotion_metadata`` carries
    both a ``promotion_decision`` and a ``rollback_target`` — this is a legitimate
    server-owned promotion finalisation that intentionally omits a training run.

    Returns ``"synthetic_phase_iteration_<phase_id>"`` on synthetic detection,
    or ``None`` when the iteration is genuine.

    ``prior_best_metrics`` should be the metrics dict of the best
    non-promotion-family iteration with a ``primary_metric`` value.  An empty
    dict disables the check conservatively (no block).
    """
    # Exception: real promotion finalisation has no training run but carries
    # decision + rollback metadata — never treat this as synthetic.
    dev_meta = metrics.get("development_promotion_metadata")
    if (
        isinstance(dev_meta, dict)
        and dev_meta.get("promotion_decision")
        and dev_meta.get("rollback_target")
    ):
        return None

    # DM-1 exception: explicit evidence-replay iterations carry an audited
    # link to the session's best (``evidence_replayed_from_iteration``) and
    # inherit that iteration's phase-advancement evidence. The orchestrator
    # only emits this marker when the canonical config-hash matches the
    # session-best AND the active phase is in
    # ``EVIDENCE_INHERITABLE_PHASES`` — so the source iteration is
    # provably the canonical one for this evidence. Treat as a legitimate
    # replay (not synthetic) so the phase machine advances without forcing
    # another ~7-minute re-train of an unchanged config.
    if metrics.get("evidence_replayed_from_iteration") is not None:
        return None

    # Condition 1: no training ran.
    if metrics.get("training_time_s") is not None:
        return None

    # Condition 2: primary_metric unchanged from prior best.
    current_raw = metrics.get("primary_metric")
    prior_raw = prior_best_metrics.get("primary_metric")
    if current_raw is None or prior_raw is None:
        # Cannot compare — conservative: do not block.
        return None
    try:
        if round(float(current_raw), 4) != round(float(prior_raw), 4):
            return None
    except (TypeError, ValueError):
        return None

    # Condition 3: no new mlflow_run_id.
    current_run_id = normalize_optional_artifact_ref(metrics.get("mlflow_run_id"))
    prior_run_id = normalize_optional_artifact_ref(
        prior_best_metrics.get("mlflow_run_id")
    )
    if current_run_id and current_run_id != prior_run_id:
        return None

    logger.warning(
        "_is_synthetic_promotion_iteration: phase %s iteration appears synthetic "
        "(training_time_s=None, metric=%s unchanged from prior, no new run_id)",
        phase_id,
        current_raw,
    )
    return f"synthetic_phase_iteration_{phase_id}"


def _calibration_payload(metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    config = metrics.get("config")
    if isinstance(config, dict) and isinstance(
        config.get("calibration_full_validation"), dict
    ):
        return config["calibration_full_validation"]
    calibration = metrics.get("calibration_full_validation")
    return calibration if isinstance(calibration, dict) else None


def _adaptive_feature_evidence(metrics: Dict[str, Any]) -> Dict[str, Any]:
    config = _dict_at(metrics, "config")
    feature_schema = _dict_at(metrics, "feature_schema")
    schema_adaptive = _dict_at(feature_schema, "adaptive_levels")
    adaptive = _dict_at(metrics, "adaptive_features")

    requested = _first_non_none(
        adaptive.get("requested"),
        schema_adaptive.get("requested"),
        config.get("adaptive_levels_enabled"),
        metrics.get("adaptive_levels_enabled"),
    )
    enabled = _first_non_none(
        adaptive.get("enabled"),
        schema_adaptive.get("enabled"),
        config.get("adaptive_levels_enabled"),
        metrics.get("adaptive_levels_enabled"),
    )
    selected_count = _first_non_none(
        adaptive.get("selected_count"),
        schema_adaptive.get("selected_count"),
    )
    selected_names = _first_non_none(
        adaptive.get("selected_feature_names"),
        schema_adaptive.get("selected_feature_names"),
    )
    noop_reason = _first_non_none(
        metrics.get("adaptive_feature_noop_reason"),
        adaptive.get("noop_reason"),
        schema_adaptive.get("noop_reason"),
    )
    return {
        "present": bool(adaptive or schema_adaptive),
        "requested": _truthy(requested),
        "enabled": _truthy(enabled),
        "selected_count": _int_value(selected_count, default=0),
        "selected_feature_names": _string_list(selected_names),
        "noop_reason": noop_reason,
    }


def _adaptive_schema_flags_blocker(metrics: Dict[str, Any]) -> Optional[str]:
    evidence = _adaptive_feature_evidence(metrics)
    adaptive_names = evidence.get("selected_feature_names") or []
    if not (
        evidence.get("enabled")
        or evidence.get("requested")
        or _int_value(evidence.get("selected_count"), default=0) > 0
        or adaptive_names
    ):
        return None

    flags = _feature_schema_flags(metrics)
    adaptive_flags = _dict_at(flags, "adaptive_levels")
    if not adaptive_flags.get("enabled"):
        return "missing_adaptive_feature_schema_flags"
    flagged_names = _string_list(adaptive_flags.get("selected_feature_names"))
    if not flagged_names:
        return "missing_adaptive_selected_feature_names"
    if adaptive_names and not set(adaptive_names).issubset(set(flagged_names)):
        return "adaptive_feature_schema_flags_mismatch"
    return None


def _feature_schema_flags(metrics: Dict[str, Any]) -> Dict[str, Any]:
    feature_schema = _dict_at(metrics, "feature_schema")
    parity_metadata = _dict_at(metrics, "parity_metadata")
    return _first_dict(
        parity_metadata.get("feature_schema_flags"),
        feature_schema.get("feature_schema_flags"),
        metrics.get("feature_schema_flags"),
    )


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


def _first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _int_value(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sha256_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        # Deterministic JSON serialisation for non-string inputs (e.g. dicts
        # emitted by the LLM instead of YAML text).
        value = json.dumps(value, sort_keys=True, separators=(",", ":"))
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
        normalized = normalize_optional_artifact_ref(value)
        if normalized:
            return normalized
    return None


def _rl_economic_replay_payload(metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rl_oos = _first_dict(metrics.get("rl_oos"), metrics.get("rl_oos_gates"))
    replay = _first_dict(
        metrics.get("rl_economic_replay"),
        metrics.get("economic_replay"),
        metrics.get("replay"),
        rl_oos.get("rl_economic_replay"),
        rl_oos.get("economic_replay"),
    )
    return replay or None


def _rl_replay_assumptions_present(replay: Dict[str, Any]) -> bool:
    assumptions = _first_dict(
        replay.get("assumptions"),
        replay.get("cost_assumptions"),
    )
    return all(
        _first_number(assumptions.get(key)) is not None
        for key in ("fee_bps", "spread_bps", "slippage_bps")
    )


def _rl_replay_worse_than_baseline(
    replay: Dict[str, Any],
) -> list[Dict[str, Any]]:
    indicators: list[Dict[str, Any]] = []
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
        ("replay.metrics", _dict_at(replay, "metrics")),
        ("replay.post_cost_metrics", _dict_at(replay, "post_cost_metrics")),
        ("replay.comparison", _dict_at(replay, "comparison")),
        ("replay.baseline_comparison", _dict_at(replay, "baseline_comparison")),
        ("replay.gates", _dict_at(replay, "gates")),
    ]
    for source, container in containers:
        for key in boolean_keys:
            if container.get(key) is True:
                indicators.append({"source": source, "key": key, "value": True})
        for key in numeric_delta_keys:
            value = _first_number(container.get(key))
            if value is not None and value < 0.0:
                indicators.append({"source": source, "key": key, "value": value})
    return indicators


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
