"""Historical trading-skill phase tables (moved to src/compat — P1-2).

The DIRECTION / VOLATILITY / FALLBACK phase plans, the legacy ``model_type``
lookup (``phases_for_model``), the historical RL OOS evidence keys, and the
DM-14 per-phase primary-sweep knob table. Kept verbatim from
``src/core/research_phase_plan.py`` so pre-migration database rows still
render and legacy sessions keep their phase plan; new skills declare their
own ``phase_plan`` in ``SKILL.yaml``. Nothing here may grow new features —
the domain-coupling guard exempts (and thereby documents) this file.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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
        # DM-12: explicitly call out direction_pct_threshold and
        # sample_weight_halflife so the agent's free-form exploration
        # touches them (both stayed at defaults across all 12 iterations
        # of res_be66790e192e).
        "next_action": (
            "Sweep bounded tabular roster, horizon, dead-zone, "
            "calibration, and threshold settings — including "
            "direction_pct_threshold (try 0.015 / 0.040 / 0.050) and "
            "sample_weight_halflife (try 1000 / 1500 / 2000). Emit "
            "metrics.tabular_sweep_variant on each attempt so the phase "
            "advances."
        ),
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
        "next_action": "Evaluate allowed TS-FM probability adapter candidates with tabular fallback preserved. Emit metrics.tsfm_adapter_json or metrics.tsfm_fallback_validation_json so the phase advances.",
        "min_iterations": 2,
        "max_iterations": 15,
    },
    {
        "id": "calibration_replay_gates",
        "label": "Calibration/Replay Gates",
        # Option A (2026-05-26): serving ships the single best BASE learner —
        # meta_model / stacking_calibration_* control the never-served
        # meta-stacker and are SCORE-INERT (observed: full-mode iterations
        # varying them reproduce the parent metric bit-identically). The
        # phase's calibration lever is the SERVED model's calibration_method.
        "next_action": (
            "Run full calibration diagnostics and post-cost replay gates "
            "on finalists. Vary calibration_method (isotonic / sigmoid / "
            "temperature / beta — calibrates the SERVED best-base model) "
            "as the primary search dimension for this phase. Do NOT vary "
            "meta_model, stacking_calibration_*, horizon_ensemble_*, "
            "meta_label_*, min_cal_samples / cal_fraction (score-inert "
            "under Option A serving), or threshold_strategy (the econ "
            "replay applies its own gating policy — threshold changes are "
            "score-inert too). Emit metrics.calibration_full_validation "
            "and metrics.economic_replay."
        ),
        "min_iterations": 2,
        "max_iterations": 8,
    },
    {
        "id": "multi_seed_robustness",
        "label": "Multi-Seed Robustness",
        # 2026-06-11: this pipeline is DETERMINISTIC — varying training.seed
        # or n_seed_trials is an INERT change (bit-identical metric). The
        # stability evidence is fold stability, emitted on every run.
        "next_action": (
            "Confirm finalist stability via the walk-forward fold metrics "
            "(walkforward_auc_cv, fold gates) the best config's run already "
            "emitted — this pipeline is deterministic, so do NOT vary seeds "
            "or n_seed_trials (inert). An unchanged re-run is admitted only as "
            "a declared repeat (evaluation-policy planned_repeats; each "
            "authorized observation is charged), and an undeclared identical "
            "re-submission is rejected as a duplicate. A robustness probe that "
            "IS meaningful here: one small data-window or fold-count "
            "perturbation, judged on fold-stability metrics."
        ),
        "min_iterations": 3,
        "max_iterations": 6,
    },
    {
        "id": "inference_parity_replay",
        "label": "Inference Parity Replay",
        "next_action": "Validate feature parity, adapter loading, composite reload, latency, and rollback readiness. Emit metrics.inference_parity or inference_reload_validation.",
        "min_iterations": 2,
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
        "min_iterations": 2,
        "max_iterations": 8,
    },
    {
        "id": "multi_seed_robustness",
        "label": "Multi-Seed Robustness",
        # 2026-06-11: this pipeline is DETERMINISTIC — varying training.seed
        # or n_seed_trials is an INERT change (bit-identical metric). The
        # stability evidence is fold stability, emitted on every run.
        "next_action": (
            "Confirm finalist stability via the walk-forward fold metrics "
            "(walkforward_auc_cv, fold gates) the best config's run already "
            "emitted — this pipeline is deterministic, so do NOT vary seeds "
            "or n_seed_trials (inert). An unchanged re-run is admitted only as "
            "a declared repeat (evaluation-policy planned_repeats; each "
            "authorized observation is charged), and an undeclared identical "
            "re-submission is rejected as a duplicate. A robustness probe that "
            "IS meaningful here: one small data-window or fold-count "
            "perturbation, judged on fold-stability metrics."
        ),
        "min_iterations": 3,
        "max_iterations": 6,
    },
    {
        "id": "inference_parity_replay",
        "label": "Inference Parity Replay",
        "next_action": "Validate feature parity, adapter loading, composite reload, latency, and rollback readiness. Emit metrics.inference_parity or inference_reload_validation.",
        "min_iterations": 2,
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


def phases_for_model(model_type: Optional[str]) -> List[Dict[str, Any]]:
    """Return the canonical phase list for the given model_type."""
    if model_type == "direction":
        return DIRECTION_PHASES
    if model_type == "volatility":
        return VOLATILITY_PHASES
    return FALLBACK_PHASES


# Evidence keys a SUCCESSFUL RL walk-forward run emits (prepare.py print_summary
# / the orchestrator results.json synthesis). Their presence proves an iteration
# produced genuine RL OOS metrics — used to gate the RL ``validation`` phase so
# it cannot complete on non-RL or contentless iterations.
# NOTE: historical metric names retained for pre-migration DB-row rendering;
# new skills declare their own evidence keys via the manifest.
RL_OOS_EVIDENCE_KEYS: tuple[str, ...] = (
    "mean_oos_sharpe",
    "rl_profit_score",
    "folds_passed",
    "oos_sharpe",
    "mean_oos_return",
)


# DM-14: per-phase primary sweep keys. Used by ``_phase_headroom_hint`` to
# decide whether the active phase still has untried levers. The lists are
# intentionally small — only the dimensions DM-12 / DM-13 wired into the
# seed roster (so an iteration touching one of these keys is a real probe,
# not just a parameter the trainer touched as a side-effect).
_PHASE_PRIMARY_SWEEP_KEYS: Dict[str, tuple[str, ...]] = {
    "tabular_sweeps": (
        "direction_pct_threshold",
        "sample_weight_halflife",
        "roster_preset",
        # MQ-HPO: tuned base-learner candidates — a real discrimination lever
        # (bases otherwise train on fixed defaults). threshold_strategy is
        # NOT here: the econ replay applies its own gating policy, making
        # the operating threshold score-inert.
        "base_hpo_enabled",
    ),
    "calibration_replay_gates": (
        # Option A: meta_model / stacking_calibration_* removed — they probe
        # the never-served meta-stacker (score-inert). horizon_ensemble_*
        # removed for the same reason (feeds only the meta-stacker).
        # threshold_strategy removed too: the econ replay applies its own
        # gating policy, so the operating threshold is score-inert. The
        # served model's calibrator is the real lever.
        "calibration_method",
    ),
}


__all__ = [
    "DIRECTION_PHASES",
    "FALLBACK_PHASES",
    "VOLATILITY_PHASES",
    "phases_for_model",
    "RL_OOS_EVIDENCE_KEYS",
    "_PHASE_PRIMARY_SWEEP_KEYS",
]
