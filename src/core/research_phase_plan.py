"""Phase-state helpers for autoresearch sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from src.core.artifact_reference import normalize_optional_artifact_ref
from src.core.consistency_validator import (  # AR-5/AR-6
    ACCEPTED_ADAPTIVE_NOOP_REASONS,
    EVIDENCE_ARTIFACT_PHASES,
    _is_synthetic_promotion_iteration,
    check_adaptive_feature_sweep,
    check_evidence_artifact,
)


# Direction-research phase plan.
#
# Each entry carries `min_iterations` (a soft floor enforced when phase advance
# depends purely on iteration cardinality, used by phases that do not emit a
# specific evidence key) and `max_iterations` (a hard ceiling used by the
# orchestrator loop guard to prevent the agent from burning the entire budget
# inside a single phase, see F7 in AUTORESEARCH-PHASE-COVERAGE-res_0efe45aaa28f.md).
#
# NOTE: `rl_finalist_retraining` is intentionally absent from direction
# research. That phase trains a downstream RL agent that consumes direction
# probabilities and belongs in the RL autotuner. Coupling it here forced the
# direction loop to wait on RL training and conflated failure modes.
DIRECTION_PHASES: List[Dict[str, Any]] = [
    {
        "id": "baseline_capture",
        "label": "Baseline Capture",
        "next_action": "Run the immutable baseline config and record the first server-owned attempt.",
        "min_iterations": 1,
        "max_iterations": 3,
    },
    {
        "id": "tabular_sweeps",
        "label": "Tabular Sweeps",
        "next_action": "Sweep bounded tabular roster, horizon, dead-zone, calibration, and threshold settings. Emit metrics.tabular_sweep_variant on each attempt so the phase advances.",
        "min_iterations": 6,
        "max_iterations": 40,
    },
    {
        "id": "adaptive_feature_sweeps",
        "label": "Adaptive Feature Sweeps",
        "next_action": "Compare adaptive support/resistance and cycle feature variants against the tabular baseline. Emit metrics.adaptive_features with active selected features and a changed schema/count, or an accepted adaptive_feature_noop_reason.",
        "min_iterations": 4,
        "max_iterations": 30,
    },
    {
        "id": "tsfm_sweeps",
        "label": "TS-FM Sweeps",
        "next_action": "Evaluate allowed TS-FM probability adapter candidates with tabular fallback preserved. Emit metrics.tsfm_adapter or tsfm_fallback_validation so the phase advances.",
        "min_iterations": 2,
        "max_iterations": 15,
    },
    {
        "id": "calibration_replay_gates",
        "label": "Calibration/Replay Gates",
        "next_action": "Run full calibration diagnostics and post-cost replay gates on finalists. Emit metrics.calibration_full_validation and metrics.economic_replay.",
        "min_iterations": 1,
        "max_iterations": 8,
    },
    {
        "id": "multi_seed_robustness",
        "label": "Multi-Seed Robustness",
        "next_action": "Confirm finalist stability across configured seed trials. Emit metrics.seed_trials or seeds_passed_gates.",
        "min_iterations": 1,
        "max_iterations": 6,
    },
    {
        "id": "inference_parity_replay",
        "label": "Inference Parity Replay",
        "next_action": "Validate feature parity, adapter loading, composite reload, latency, and rollback readiness. Emit metrics.inference_parity or inference_reload_validation.",
        "min_iterations": 1,
        "max_iterations": 4,
    },
    {
        "id": "promotion_proposal",
        "label": "Promotion Proposal",
        "next_action": "Prepare a development-scoped promotion proposal with ownership and rollback metadata.",
        "min_iterations": 0,
        "max_iterations": 4,
    },
]


FALLBACK_PHASES: List[Dict[str, Any]] = [
    {
        "id": "baseline_capture",
        "label": "Baseline Capture",
        "next_action": "Run the baseline config and record the first server-owned attempt.",
        "min_iterations": 1,
        "max_iterations": 3,
    },
    {
        "id": "hpo_screening",
        "label": "HPO Screening",
        "next_action": "Run or inspect bounded HPO trials when enabled.",
        "min_iterations": 1,
        "max_iterations": 20,
    },
    {
        "id": "validation",
        "label": "Validation",
        "next_action": "Validate candidate metrics and gates against the manifest budget.",
        "min_iterations": 2,
        "max_iterations": 10,
    },
    {
        "id": "promotion_proposal",
        "label": "Promotion Proposal",
        "next_action": "Prepare a development-scoped promotion proposal when gates pass.",
        "min_iterations": 0,
        "max_iterations": 4,
    },
]


# Volatility-research phase plan.
#
# Mirrors the VOLATILITY_PHASES playbook in volatility-autotuner/SKILL.md:
#   Phase 1: ATR multiplier discovery (highest-impact knob)
#   Phase 2: Decision boundary & calibration
#   Phase 3: Temporal stability & ensemble pruning
#   Phases 4-7: Shared final gates with direction (calibration/replay, seeds,
#               inference parity, promotion proposal)
#
# Evidence-key completion (same contract as F3 for direction): each phase
# requires the LLM to emit at least one of the listed keys in metrics_json
# before the phase is marked complete.  Pure cardinality is only the fallback
# for `atr_sweep` (4+ phase-tagged iterations) when the evidence key is absent.
VOLATILITY_PHASES: List[Dict[str, Any]] = [
    {
        "id": "baseline_capture",
        "label": "Baseline Capture",
        "next_action": "Run the immutable baseline config and record the first server-owned attempt.",
        "min_iterations": 1,
        "max_iterations": 3,
    },
    {
        "id": "atr_sweep",
        "label": "ATR Multiplier Sweep",
        "next_action": (
            "Sweep `volatility_atr_mult` from low (1.5–2.5) to high (4.0–6.0) to find the "
            "multiplier that achieves 10–40% positive_rate AND highest AUC. "
            "Emit metrics.volatility_atr_mult or atr_multiplier on each attempt so the phase advances."
        ),
        "min_iterations": 4,
        "max_iterations": 20,
    },
    {
        "id": "threshold_calibration",
        "label": "Threshold & Calibration",
        "next_action": (
            "Sweep threshold_strategy (f1/f_beta/youden_j/gmean), threshold_beta, and "
            "calibration_method (isotonic/sigmoid). "
            "Emit metrics.threshold_strategy or calibration_method so the phase advances."
        ),
        "min_iterations": 2,
        "max_iterations": 12,
    },
    {
        "id": "temporal_ensemble",
        "label": "Temporal Stability & Ensemble",
        "next_action": (
            "Tune sample_weight_halflife for recency weighting, sweep prediction_horizon, "
            "and prune noisy learners (lgb_dart/lgb_goss). "
            "Emit metrics.sample_weight_halflife or prediction_horizon so the phase advances."
        ),
        "min_iterations": 2,
        "max_iterations": 10,
    },
    {
        "id": "calibration_replay_gates",
        "label": "Calibration/Replay Gates",
        "next_action": "Run full calibration diagnostics and post-cost replay gates on finalists. Emit metrics.calibration_full_validation and metrics.economic_replay.",
        "min_iterations": 1,
        "max_iterations": 8,
    },
    {
        "id": "multi_seed_robustness",
        "label": "Multi-Seed Robustness",
        "next_action": "Confirm finalist stability across configured seed trials. Emit metrics.seed_trials or seeds_passed_gates.",
        "min_iterations": 1,
        "max_iterations": 6,
    },
    {
        "id": "inference_parity_replay",
        "label": "Inference Parity Replay",
        "next_action": "Validate feature parity, adapter loading, composite reload, latency, and rollback readiness. Emit metrics.inference_parity or inference_reload_validation.",
        "min_iterations": 1,
        "max_iterations": 4,
    },
    {
        "id": "promotion_proposal",
        "label": "Promotion Proposal",
        "next_action": "Prepare a development-scoped promotion proposal with ownership and rollback metadata.",
        "min_iterations": 0,
        "max_iterations": 4,
    },
]


def build_phase_state(
    *,
    session: Dict[str, Any],
    iterations: Iterable[Dict[str, Any]],
    hpo_studies: Optional[Iterable[Dict[str, Any]]] = None,
    promotions: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Derive an operator-facing phase plan and next action."""

    rows = list(iterations)
    studies = list(hpo_studies or [])
    promotion_rows = list(promotions or [])
    model_type = session.get("model_type")
    phases = phases_for_model(model_type)

    completed = _completed_phase_ids(rows, studies, promotion_rows, model_type)
    blocked = _blocked_reason(rows)
    current_phase = _select_current_phase(phases, completed, blocked)
    next_action = _next_action(phases, current_phase, blocked)
    stalled_count = _count_stalled_iterations(rows, phases, current_phase)

    return {
        "schema_version": "autoresearch_phase_state.v1",
        "research_id": session.get("id"),
        "model_type": model_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_phase": current_phase,
        "next_action": next_action,
        "blocked": blocked is not None,
        "block_reason": blocked,
        "iterations_in_current_phase": stalled_count,
        "phases": [
            {
                **phase,
                "status": _phase_status(phase["id"], current_phase, completed, blocked, phases),
            }
            for phase in phases
        ],
    }


def phase_state_json(state: Dict[str, Any]) -> str:
    return json.dumps(state, sort_keys=True)


def phases_for_model(model_type: Optional[str]) -> List[Dict[str, Any]]:
    """Return the canonical phase list for the given model_type."""
    if model_type == "direction":
        return DIRECTION_PHASES
    if model_type == "volatility":
        return VOLATILITY_PHASES
    return FALLBACK_PHASES


def incomplete_phase_ids(state: Dict[str, Any]) -> List[str]:
    """Return phase ids whose status is not 'completed' in a built state."""
    phases = state.get("phases") or []
    return [
        str(p.get("id"))
        for p in phases
        if isinstance(p, dict) and p.get("status") != "completed" and p.get("id")
    ]


def phase_cap_exceeded(
    state: Dict[str, Any],
    iterations_in_phase: int,
) -> bool:
    """True when the active phase's `max_iterations` cap has been reached.

    F7 hook: orchestrator passes how many iterations have been recorded under
    the current phase via search_phase tagging; once that exceeds the cap, the
    orchestrator should nudge the LLM to advance even if it has not yet
    emitted the phase's evidence key.
    """
    current_id = state.get("current_phase")
    if not current_id:
        return False
    phases = state.get("phases") or []
    for phase in phases:
        if isinstance(phase, dict) and phase.get("id") == current_id:
            cap = phase.get("max_iterations")
            if isinstance(cap, int) and cap > 0:
                return iterations_in_phase >= cap
            return False
    return False


# Maps each phase id to the metrics_json evidence keys whose presence in an
# iteration marks that phase as having produced output.  Mirrors the logic in
# _completed_phase_ids() so both stay in sync.
#
# F3: `tabular_sweeps` previously had no evidence key and so was marked done by
# pure cardinality. We now require an explicit `tabular_sweep_variant`
# (or any of the historical canonical knobs `roster_preset`,
# `direction_pct_threshold`, `deadzone_width`, `calibration_method`) in the
# config or metrics payload, so the phase only completes when the LLM has
# actually explored the sweep space.
#
# Volatility phases (atr_sweep, threshold_calibration, temporal_ensemble)
# follow the same contract: emit the listed key or fall back to phase-tagged
# cardinality (4+ for atr_sweep, 2+ for others).
_PHASE_ADVANCEMENT_KEYS: Dict[str, tuple] = {
    "baseline_capture": (),
    "tabular_sweeps": (
        "tabular_sweep_variant",
        "roster_preset",
        "direction_pct_threshold",
        "deadzone_width",
        "calibration_method",
    ),
    "hpo_screening": (),
    "validation": (),
    # --- Volatility-specific phases ---
    "atr_sweep": (
        "volatility_atr_mult",
        "atr_multiplier",
        "atr_mult_sweep_enabled",
    ),
    "threshold_calibration": (
        "threshold_strategy",
        "threshold_beta",
        "calibration_method",
    ),
    "temporal_ensemble": (
        "sample_weight_halflife",
        "prediction_horizon",
        "ensemble_pruning",
        "base_model_keys",
    ),
    # --- Shared late phases ---
    "adaptive_feature_sweeps": ("adaptive_features", "adaptive_feature_noop_reason"),
    "tsfm_sweeps": ("tsfm", "tsfm_adapter", "tsfm_fallback_validation"),
    "calibration_replay_gates": ("calibration_full_validation", "economic_replay"),
    "multi_seed_robustness": ("seed_trials", "n_seed_trials", "seeds_passed_gates"),
    "inference_parity_replay": ("inference_parity", "inference_reload_validation"),
    "promotion_proposal": (
        "development_promotion_metadata",
        "promotion_allowed",
        "promotion_consistency_report",
        "promotion_decision",
        "promotion_metadata",
        "promotion_preview_ready",
        "promotion_scope",
        "scoped_promotion_metadata",
    ),
}


# Phases that advance on presence of an accepted permissive key with NO
# _phase_has_genuine_dwell gate (see _completed_phase_ids: _adaptive_phase_
# completed is called directly, unlike tsfm_sweeps et al.). Evidence for these
# can be config-invariant (e.g. adaptive_features_unavailable on an instrument
# where adaptive features simply do not apply), so a dedup re-run of the only
# config that produces it must INHERIT that evidence rather than be rejected
# with an evidence-stripped marker. Keep this a strict subset — never add a
# phase that is dwell-gated in _completed_phase_ids(), or a single dedup
# re-run could skip genuine multi-iteration work.
NOOP_INHERITABLE_PHASES: frozenset[str] = frozenset({"adaptive_feature_sweeps"})


def _completed_phase_ids(
    iterations: List[Dict[str, Any]],
    hpo_studies: List[Dict[str, Any]],
    promotions: List[Dict[str, Any]],
    model_type: Optional[str],
) -> set[str]:
    """Mark phases complete using a hybrid contract:

    1. Any phase listed in ``_PHASE_ADVANCEMENT_KEYS`` is complete iff at least
       one iteration emitted that evidence key (in metrics or config).
    2. Phases without evidence keys (baseline_capture, hpo_screening,
       validation) fall back to cardinality with a stricter minimum than the
       legacy `>=2` rule. Baseline still completes on the first attempt;
       validation requires at least two attempts.
    3. F3 fix: `tabular_sweeps` no longer auto-completes after 2 iterations.
       It now requires either an explicit sweep variant key or the
       per-phase ``min_iterations`` floor matched by attempts that explicitly
       tagged ``search_phase == "tabular_sweeps"``. This prevents the phase
       plan from racing ahead of the LLM's actual exploration.
    """

    completed: set[str] = set()
    if iterations:
        completed.add("baseline_capture")
    if hpo_studies:
        completed.add("hpo_screening")
    if len(iterations) >= 2:
        completed.add("validation")

    # Tabular sweeps: evidence key OR phase-tagged minimum effort.
    tabular_iters = _iterations_in_phase(iterations, "tabular_sweeps")
    if any(_has_metric(it, *_PHASE_ADVANCEMENT_KEYS["tabular_sweeps"]) for it in iterations):
        completed.add("tabular_sweeps")
    elif len(tabular_iters) >= 6:
        completed.add("tabular_sweeps")

    # Volatility phases: evidence key OR phase-tagged minimum effort.
    atr_iters = _iterations_in_phase(iterations, "atr_sweep")
    if any(_has_metric(it, *_PHASE_ADVANCEMENT_KEYS["atr_sweep"]) for it in iterations):
        completed.add("atr_sweep")
    elif len(atr_iters) >= 4:
        completed.add("atr_sweep")

    threshold_iters = _iterations_in_phase(iterations, "threshold_calibration")
    if any(_has_metric(it, *_PHASE_ADVANCEMENT_KEYS["threshold_calibration"]) for it in iterations):
        completed.add("threshold_calibration")
    elif len(threshold_iters) >= 2:
        completed.add("threshold_calibration")

    temporal_iters = _iterations_in_phase(iterations, "temporal_ensemble")
    if any(_has_metric(it, *_PHASE_ADVANCEMENT_KEYS["temporal_ensemble"]) for it in iterations):
        completed.add("temporal_ensemble")
    elif len(temporal_iters) >= 2:
        completed.add("temporal_ensemble")

    if _adaptive_phase_completed(iterations):
        completed.add("adaptive_feature_sweeps")
    tsfm_iters = _iterations_in_phase(iterations, "tsfm_sweeps")
    if (
        any(_has_metric(it, *_PHASE_ADVANCEMENT_KEYS["tsfm_sweeps"]) for it in iterations)
        and _phase_has_genuine_dwell(iterations, "tsfm_sweeps", min_iterations=2)
    ):
        completed.add("tsfm_sweeps")
    elif len(tsfm_iters) >= 2:
        # Sibling-consistent cardinality net (cf. tabular_sweeps >=6,
        # atr_sweep >=4). tsfm_fallback_validation is a permissive key, so a
        # legitimately tabular-only instrument that dwells in tsfm_sweeps must
        # still advance even if the genuine-dwell path does not trip. N=2 is
        # the phase's own min_iterations.
        completed.add("tsfm_sweeps")
    # AR-5: gate promotion-family phases behind artifact validation.
    # AR-6: also gate behind synthetic-iteration detection.
    _prior_best = _prior_best_metrics(iterations)
    if (
        any(
            _has_metric(it, *_PHASE_ADVANCEMENT_KEYS["calibration_replay_gates"])
            and not check_evidence_artifact(_metrics_of(it), "calibration_replay_gates")
            and not _is_synthetic_promotion_iteration(
                _metrics_of(it), _prior_best, "calibration_replay_gates"
            )
            for it in iterations
        )
        and _phase_has_genuine_dwell(iterations, "calibration_replay_gates", min_iterations=1)
    ):
        completed.add("calibration_replay_gates")
    if (
        any(
            _has_metric(it, *_PHASE_ADVANCEMENT_KEYS["multi_seed_robustness"])
            and not check_evidence_artifact(_metrics_of(it), "multi_seed_robustness")
            and not _is_synthetic_promotion_iteration(
                _metrics_of(it), _prior_best, "multi_seed_robustness"
            )
            for it in iterations
        )
        and _phase_has_genuine_dwell(iterations, "multi_seed_robustness", min_iterations=1)
    ):
        completed.add("multi_seed_robustness")
    _inference_prior_run_ids = _prior_run_ids_for_phase(iterations, "inference_parity_replay")
    if (
        any(
            _has_metric(it, *_PHASE_ADVANCEMENT_KEYS["inference_parity_replay"])
            and not check_evidence_artifact(
                _metrics_of(it),
                "inference_parity_replay",
                prior_run_ids=_inference_prior_run_ids,
            )
            and not _is_synthetic_promotion_iteration(
                _metrics_of(it), _prior_best, "inference_parity_replay"
            )
            for it in iterations
        )
        and _phase_has_genuine_dwell(iterations, "inference_parity_replay", min_iterations=1)
    ):
        completed.add("inference_parity_replay")
    if _has_promotion_evidence(iterations, promotions, prior_best=_prior_best):
        completed.add("promotion_proposal")
    return completed


def _iterations_in_phase(
    iterations: List[Dict[str, Any]],
    phase_id: str,
) -> List[Dict[str, Any]]:
    """Return iterations whose ``search_phase`` column matches ``phase_id``.

    Iterations without a phase tag are ignored. The orchestrator started
    stamping ``search_phase`` on every record in F2; older sessions will
    return empty lists here and fall through to evidence-key checks.
    """
    return [it for it in iterations if (it.get("search_phase") or "") == phase_id]


def _phase_has_genuine_dwell(
    iterations: List[Dict[str, Any]],
    phase_id: str,
    *,
    min_iterations: int,
) -> bool:
    """Return True when the agent dwelt in ``phase_id`` for ``min_iterations``.

    Fix 8: ``auto_phase_evidence: True`` is set on every prepare.py run, so the
    presence of a permissive evidence key alone (e.g. ``tsfm_fallback_validation``
    or ``adaptive_feature_noop_reason``) is not enough to advance a phase. The
    agent must also produce at least ``min_iterations`` phase-tagged
    iterations. After Fix 4, only training-derived iterations are recorded,
    so this counts real prepare.py runs in the phase.

    Iterations that carry an explicit, agent-emitted phase key beyond the
    permissive fallback (e.g. ``tsfm_adapter``) always count as genuine
    regardless of phase tag, mirroring the legacy contract for agents that
    forget to set ``search_phase``.

    Issue 7: artifact-validated tail phases (calibration_replay_gates,
    multi_seed_robustness, inference_parity_replay) require BOTH the
    explicit evidence key AND an in-phase iteration tag. prepare.py emits
    those keys on every run, so without the tag requirement the very first
    tabular_sweeps iteration paper-completes phases 5–7 before the agent
    has ever deliberated on them. Validity remains enforced by
    check_evidence_artifact in _completed_phase_ids; this gate adds
    DELIBERATION (the agent must at least once tag an iteration in-phase).
    """
    explicit_keys = _PHASE_EXPLICIT_AGENT_KEYS.get(phase_id, ())
    in_phase_count = len(_iterations_in_phase(iterations, phase_id))
    if explicit_keys and any(
        _has_metric(it, *explicit_keys) for it in iterations
    ):
        if phase_id in _PHASE_REQUIRES_IN_PHASE_TAG:
            return in_phase_count >= min_iterations
        return True
    return in_phase_count >= min_iterations


# Issue 7: tail phases whose evidence prepare.py emits on every run. Without
# the in-phase tag requirement above, they paper-complete from any iteration
# carrying the key (typically iter 3 of tabular_sweeps), bypassing per-phase
# deliberation. Validity is unchanged — check_evidence_artifact still vets the
# structured artifact. This set documents *which* phases need the agent to at
# least once mark themselves in-phase. Keep tsfm_sweeps OUT (G-A's cardinality
# net handles it; the tabular fallback is genuine evidence on any run).
_PHASE_REQUIRES_IN_PHASE_TAG: frozenset[str] = frozenset(
    {
        "calibration_replay_gates",
        "multi_seed_robustness",
        "inference_parity_replay",
    },
)


# Fix 8 — phase-specific keys whose presence proves the agent did real work
# in the phase, even when ``auto_phase_evidence: True`` is also set. These
# are a strict subset of ``_PHASE_ADVANCEMENT_KEYS`` excluding permissive
# fallback keys.
_PHASE_EXPLICIT_AGENT_KEYS: Dict[str, tuple] = {
    "tsfm_sweeps": ("tsfm", "tsfm_adapter"),
    "calibration_replay_gates": (
        "calibration_full_validation",
        "economic_replay",
    ),
    "multi_seed_robustness": (
        "seed_trials",
        "n_seed_trials",
        "seeds_passed_gates",
    ),
    "inference_parity_replay": (
        "inference_parity",
        "inference_reload_validation",
    ),
}


def _adaptive_phase_completed(iterations: List[Dict[str, Any]]) -> bool:
    for idx, row in enumerate(iterations):
        if (row.get("search_phase") or "") != "adaptive_feature_sweeps" and not _has_metric(
            row,
            *_PHASE_ADVANCEMENT_KEYS["adaptive_feature_sweeps"],
        ):
            continue

        metrics = _metrics_of(row)
        if check_adaptive_feature_sweep(metrics) is not None:
            continue

        noop_reason = str(
            _first_non_none(
                metrics.get("adaptive_feature_noop_reason"),
                _dict_at(metrics, "adaptive_features").get("noop_reason"),
                _dict_at(_dict_at(metrics, "feature_schema"), "adaptive_levels").get(
                    "noop_reason"
                ),
            )
            or ""
        ).strip()
        if noop_reason in ACCEPTED_ADAPTIVE_NOOP_REASONS:
            return True

        evidence = _feature_schema_evidence(metrics)
        if not (
            _adaptive_enabled(metrics)
            and _int_value(evidence.get("adaptive_selected_count")) > 0
        ):
            continue

        baseline = _latest_feature_schema_baseline(iterations[:idx])
        if _feature_schema_changed(evidence, baseline):
            return True

    return False


def _latest_feature_schema_baseline(
    iterations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    for row in reversed(iterations):
        if (row.get("search_phase") or "") == "adaptive_feature_sweeps":
            continue
        evidence = _feature_schema_evidence(_metrics_of(row))
        if evidence.get("feature_schema_hash") or evidence.get("n_features") is not None:
            return evidence
    return {}


def _feature_schema_changed(
    evidence: Dict[str, Any],
    baseline: Dict[str, Any],
) -> bool:
    current_hash = evidence.get("feature_schema_hash")
    baseline_hash = baseline.get("feature_schema_hash")
    if current_hash and baseline_hash and current_hash != baseline_hash:
        return True
    current_count = evidence.get("n_features")
    baseline_count = baseline.get("n_features")
    return (
        current_count is not None
        and baseline_count is not None
        and int(current_count) != int(baseline_count)
    )


def _feature_schema_evidence(metrics: Dict[str, Any]) -> Dict[str, Any]:
    feature_schema = _dict_at(metrics, "feature_schema")
    adaptive = _dict_at(metrics, "adaptive_features")
    schema_adaptive = _dict_at(feature_schema, "adaptive_levels")
    return {
        "feature_schema_hash": _first_non_none(
            metrics.get("feature_schema_hash"),
            feature_schema.get("feature_schema_hash"),
            adaptive.get("feature_schema_hash"),
        ),
        "n_features": _int_or_none(
            _first_non_none(
                metrics.get("n_features"),
                feature_schema.get("n_features"),
                adaptive.get("n_features"),
            )
        ),
        "adaptive_selected_count": _int_value(
            _first_non_none(
                adaptive.get("selected_count"),
                schema_adaptive.get("selected_count"),
            )
        ),
    }


def _adaptive_enabled(metrics: Dict[str, Any]) -> bool:
    config = _dict_at(metrics, "config")
    feature_schema = _dict_at(metrics, "feature_schema")
    adaptive = _dict_at(metrics, "adaptive_features")
    schema_adaptive = _dict_at(feature_schema, "adaptive_levels")
    return _truthy(
        _first_non_none(
            adaptive.get("enabled"),
            schema_adaptive.get("enabled"),
            config.get("adaptive_levels_enabled"),
            metrics.get("adaptive_levels_enabled"),
        )
    )


def _has_promotion_evidence(
    iterations: List[Dict[str, Any]],
    promotions: List[Dict[str, Any]],
    *,
    prior_best: Optional[Dict[str, Any]] = None,
) -> bool:
    if promotions:
        return True  # actual promotion record — artifact is real
    evidence_keys = (
        "development_promotion_metadata",
        "promotion_allowed",
        "promotion_consistency_report",
        "promotion_decision",
        "promotion_metadata",
        "promotion_preview_ready",
        "promotion_scope",
        "scoped_promotion_metadata",
    )
    _pb = prior_best if prior_best is not None else {}
    # AR-5: gate evidence-key path behind artifact validation.
    # AR-6: also gate behind synthetic-iteration detection.
    return any(
        _has_metric(row, *evidence_keys)
        and not check_evidence_artifact(_metrics_of(row), "promotion_proposal")
        and not _is_synthetic_promotion_iteration(_metrics_of(row), _pb, "promotion_proposal")
        for row in iterations
    )


def _select_current_phase(
    phases: List[Dict[str, Any]],
    completed: set[str],
    blocked: Optional[str],
) -> str:
    # Always select the first incomplete phase, regardless of any consistency
    # blocker on the last iteration.  Blockers are surfaced in next_action as
    # advisory context rather than overriding the phase pointer, so the LLM
    # always receives forward-looking phase guidance.
    for phase in phases:
        if phase["id"] not in completed:
            return phase["id"]
    return phases[-1]["id"]


def _phase_status(
    phase_id: str,
    current_phase: str,
    completed: set[str],
    blocked: Optional[str],
    phases: List[Dict[str, Any]],
) -> str:
    if phase_id in completed and phase_id != current_phase:
        return "completed"
    if phase_id == current_phase:
        # Mark "blocked" only when we are at the terminal promotion phase and
        # consistency gates are preventing promotion.  Mid-pipeline phases
        # stay "in_progress" so the agent receives forward-looking guidance
        # rather than a dead-end blocked status.
        is_terminal = bool(phases) and phase_id == phases[-1]["id"]
        if blocked and is_terminal:
            return "blocked"
        return "in_progress"
    return "pending"


def _next_action(
    phases: List[Dict[str, Any]],
    current_phase: str,
    blocked: Optional[str],
) -> str:
    is_terminal = bool(phases) and current_phase == phases[-1]["id"]
    base = next(
        (p["next_action"] for p in phases if p["id"] == current_phase),
        "Inspect session state.",
    )
    if not blocked:
        return base
    if is_terminal:
        # At the final phase the blocker IS the primary concern — promotion
        # cannot proceed until it is resolved.
        return f"{base} Resolve consistency blockers first: {blocked}"
    # Mid-pipeline: append as an advisory note.  The phase's own action
    # takes priority so the agent knows WHAT to run next.
    return f"{base} (Advisory — last attempt has consistency notes: {blocked})"


def _count_stalled_iterations(
    rows: List[Dict[str, Any]],
    phases: List[Dict[str, Any]],
    current_phase: str,
) -> int:
    """Return how many consecutive trailing iterations produced no later-phase evidence.

    When this count is high the agent is stuck: it keeps running experiments
    for the current phase without producing the metrics keys that would advance
    the phase plan forward.  Callers can surface this as a stall warning in the
    iteration context digest.
    """
    current_idx = next(
        (i for i, p in enumerate(phases) if p["id"] == current_phase),
        len(phases) - 1,
    )
    # Collect all advancement keys for phases strictly AFTER the current one.
    later_keys: tuple = tuple(
        key
        for phase in phases[current_idx + 1 :]
        for key in _PHASE_ADVANCEMENT_KEYS.get(phase["id"], ())
    )
    if not later_keys:
        # Already at the terminal phase — every iteration contributed here.
        return len(rows)

    count = 0
    for row in reversed(rows):
        if _has_metric(row, *later_keys):
            break
        count += 1
    return count


def _blocked_reason(iterations: List[Dict[str, Any]]) -> Optional[str]:
    if not iterations:
        return None
    latest = iterations[-1]
    report = _parse_json(latest.get("consistency_report_json"))
    if isinstance(report, dict) and report.get("passed") is False:
        blockers = report.get("blockers") or []
        if blockers:
            return "Consistency gate failed: " + ", ".join(str(b) for b in blockers[:4])
    return None


def _has_metric(iteration: Dict[str, Any], *keys: str) -> bool:
    payload = _parse_json(iteration.get("metrics_json"))
    if not isinstance(payload, dict):
        return False
    containers = [payload]
    config = payload.get("config")
    if isinstance(config, dict):
        containers.append(config)
    return any(any(key in container for key in keys) for container in containers)


def _dict_at(root: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = root.get(key)
    return value if isinstance(value, dict) else {}


def _first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_value(value: Any, *, default: int = 0) -> int:
    parsed = _int_or_none(value)
    return default if parsed is None else parsed


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "used"}
    return bool(value)


def _parse_json(raw: Any) -> Any:
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


# AR-5 helpers ------------------------------------------------------------------


def _metrics_of(it: Dict[str, Any]) -> Dict[str, Any]:
    """Return the parsed metrics_json dict for an iteration row, or {}."""
    parsed = _parse_json(it.get("metrics_json"))
    return parsed if isinstance(parsed, dict) else {}


def _prior_run_ids_for_phase(
    iterations: List[Dict[str, Any]],
    phase_id: str,
) -> frozenset:
    """Collect mlflow_run_ids from iterations that do NOT carry phase evidence.

    Used by _completed_phase_ids to detect recycled run_ids in
    inference_parity_replay (where the LLM re-emits a prior training run's
    run_id as the parity run_id). Computed once per call for O(n) performance.
    """
    evidence_keys = _PHASE_ADVANCEMENT_KEYS.get(phase_id, ())
    ids: set[str] = set()
    for it in iterations:
        if evidence_keys and _has_metric(it, *evidence_keys):
            continue
        run_id = normalize_optional_artifact_ref(_metrics_of(it).get("mlflow_run_id"))
        if run_id:
            ids.add(run_id)
    return frozenset(ids)


def _prior_best_metrics(iterations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return metrics of the best non-promotion-family iteration.

    Excludes ``EVIDENCE_ARTIFACT_PHASES`` iterations so the prior best reflects
    real training work, not phase-family reporting iterations.  Autoresearch
    phase metrics are treated as higher-is-better here; lower-is-better metric
    families need an explicit metric-direction contract before sharing this
    helper.

    Returns ``{}`` when no qualifying iteration is found (conservative — callers
    must treat an empty dict as "unable to compare" and avoid blocking).
    """
    best_metrics: Dict[str, Any] = {}
    best_value: Optional[float] = None

    for it in iterations:
        phase = it.get("search_phase") or ""
        if phase in EVIDENCE_ARTIFACT_PHASES:
            continue
        decision = it.get("decision")
        if decision is not None and decision not in {"keep", "improve"}:
            continue
        m = _metrics_of(it)
        raw_metric = m.get("primary_metric")
        if raw_metric is None:
            continue
        try:
            metric = float(raw_metric)
        except (TypeError, ValueError):
            continue
        if best_value is None or metric > best_value:
            best_value = metric
            best_metrics = m
    return best_metrics
