"""Fix 8 — phases gated by ``auto_phase_evidence`` must still require
``min_iterations`` of phase-tagged iterations (or an explicit agent key).

Before this fix, prepare.py's permissive fallback keys (e.g.
``tsfm_fallback_validation: True``) auto-completed phases 4–7 on the very
first iteration, regardless of whether the agent did real work.
"""
from __future__ import annotations

import json

import pytest

from src.core.research_phase_plan import _completed_phase_ids


def _iteration(
    *,
    metrics: dict,
    search_phase: str,
    iteration: int = 1,
) -> dict:
    return {
        "iteration": iteration,
        "search_phase": search_phase,
        "metrics_json": json.dumps(metrics),
        "decision": "keep",
        "primary_metric": 0.5,
        "metric_name": "composite_direction_score",
    }


def test_tsfm_single_auto_evidence_iteration_does_not_complete_phase() -> None:
    iterations = [
        _iteration(
            metrics={
                "tsfm_fallback_validation": True,
                "auto_phase_evidence": True,
            },
            search_phase="tsfm_sweeps",
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "tsfm_sweeps" not in completed


def test_tsfm_two_auto_evidence_iterations_complete_phase() -> None:
    iterations = [
        _iteration(
            metrics={
                "tsfm_fallback_validation": True,
                "auto_phase_evidence": True,
            },
            search_phase="tsfm_sweeps",
            iteration=1,
        ),
        _iteration(
            metrics={
                "tsfm_fallback_validation": True,
                "auto_phase_evidence": True,
            },
            search_phase="tsfm_sweeps",
            iteration=2,
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "tsfm_sweeps" in completed


def test_ga_tsfm_cardinality_fallback_completes_without_evidence_key() -> None:
    """G-A: sibling-consistent net (cf. tabular_sweeps >=6, atr_sweep >=4).
    Two tsfm-tagged iterations carrying NO tsfm evidence key still complete
    the phase via the cardinality fallback, so a tabular-only instrument
    cannot wedge here.
    """
    iterations = [
        _iteration(metrics={}, search_phase="tsfm_sweeps", iteration=1),
        _iteration(metrics={}, search_phase="tsfm_sweeps", iteration=2),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "tsfm_sweeps" in completed


def test_ga_tsfm_cardinality_fallback_needs_two_iterations() -> None:
    """G-A net floor is 2 (the phase's own min_iterations); a single
    keyless tsfm-tagged iteration must NOT complete the phase.
    """
    iterations = [
        _iteration(metrics={}, search_phase="tsfm_sweeps", iteration=1),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "tsfm_sweeps" not in completed


def test_tsfm_with_explicit_adapter_key_completes_immediately() -> None:
    iterations = [
        _iteration(
            metrics={
                "tsfm_adapter": "moirai",
                "auto_phase_evidence": True,
            },
            search_phase="tsfm_sweeps",
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "tsfm_sweeps" in completed


def test_calibration_replay_requires_phase_tag_when_auto_only() -> None:
    """calibration_replay_gates has min_iterations=1; an auto-evidence
    iteration must be phase-tagged to count.
    """
    iterations = [
        _iteration(
            metrics={
                "calibration_full_validation": {"passed": True},
                "auto_phase_evidence": True,
            },
            search_phase="tabular_sweeps",  # wrong phase tag
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "calibration_replay_gates" not in completed


def _valid_calibration_evidence() -> dict:
    """A calibration_full_validation/economic_replay block that *passes*
    check_evidence_artifact (selected.artifact_hash present, economic_replay
    .gates is a dict). Mirrors prepare.py's emitted shape."""
    return {
        "calibration_full_validation": {
            "version": 1,
            "selected": {"artifact_hash": "c3fac7bb6c133e5d"},
        },
        "economic_replay": {
            "source": "training_gates_proxy",
            "gates": {"all_gates_passed": True, "source": "training_gates_proxy"},
        },
    }


def _valid_seed_evidence(run_id: str = "run-A") -> dict:
    return {
        "seed_trials": [{"mlflow_run_id": run_id, "primary_metric": 0.61}],
        "n_seed_trials": 1,
        "seeds_passed_gates": 1,
    }


def _valid_parity_evidence(run_id: str = "run-A") -> dict:
    return {
        "inference_parity": {
            "feature_count_alignment_passed": True,
            "feature_name_alignment_passed": True,
            "model_roster_parity_passed": True,
            "mlflow_run_id": run_id,
        },
    }


def test_issue7_calibration_with_valid_evidence_off_phase_does_not_complete() -> None:
    """Issue 7: VALID server-emitted calibration evidence on a tabular_sweeps
    iteration must NOT auto-complete calibration_replay_gates. The agent has
    to at least once tag an iteration in-phase (deliberation requirement).
    """
    iterations = [
        _iteration(
            metrics={**_valid_calibration_evidence(), "auto_phase_evidence": True},
            search_phase="tabular_sweeps",  # not calibration_replay_gates
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "calibration_replay_gates" not in completed


def test_issue7_calibration_with_in_phase_tag_does_complete() -> None:
    """Same valid evidence, agent tagged the iterations in-phase, AND enough
    of them to satisfy Gap 2's raised floor (calibration_replay_gates=2)
    → phase completes."""
    iterations = [
        _iteration(
            metrics={**_valid_calibration_evidence(), "auto_phase_evidence": True},
            search_phase="calibration_replay_gates",
            iteration=i,
        )
        for i in range(1, 3)  # 2 in-phase iters
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "calibration_replay_gates" in completed


def test_issue7_multi_seed_with_valid_evidence_off_phase_does_not_complete() -> None:
    iterations = [
        _iteration(
            metrics={**_valid_seed_evidence(), "auto_phase_evidence": True},
            search_phase="tabular_sweeps",
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "multi_seed_robustness" not in completed


def test_issue7_multi_seed_with_in_phase_tag_completes() -> None:
    """Gap 2 floor: multi_seed_robustness=3 in-phase iters required."""
    iterations = [
        _iteration(
            metrics={**_valid_seed_evidence(), "auto_phase_evidence": True},
            search_phase="multi_seed_robustness",
            iteration=i,
        )
        for i in range(1, 4)  # 3 in-phase iters
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "multi_seed_robustness" in completed


def test_issue7_inference_parity_with_valid_evidence_off_phase_does_not_complete() -> None:
    iterations = [
        _iteration(
            metrics={
                **_valid_parity_evidence("run-A"),
                **_valid_seed_evidence("run-A"),  # parity uses prior_run_ids; this is the only iter
                "mlflow_run_id": "run-A",
                "auto_phase_evidence": True,
            },
            search_phase="tabular_sweeps",
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "inference_parity_replay" not in completed


def test_issue7_inference_parity_with_in_phase_tag_completes() -> None:
    """Gap 2 floor: inference_parity_replay=2 in-phase iters required."""
    iterations = [
        _iteration(
            metrics={
                **_valid_parity_evidence(f"run-{idx}"),
                "mlflow_run_id": f"run-{idx}",
                "auto_phase_evidence": True,
            },
            search_phase="inference_parity_replay",
            iteration=idx,
        )
        for idx in range(1, 3)  # 2 in-phase iters
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "inference_parity_replay" in completed


def test_issue7_tsfm_sweeps_still_completes_off_phase_via_explicit_key() -> None:
    """tsfm_sweeps is deliberately OUT of _PHASE_REQUIRES_IN_PHASE_TAG — its
    permissive fallback key is genuine evidence regardless of tag. G-A's
    cardinality net handles the late-bound case; Issue-7 must not regress
    tsfm completion via the explicit-adapter shortcut.
    """
    iterations = [
        _iteration(
            metrics={"tsfm_adapter": "moirai", "auto_phase_evidence": True},
            search_phase="tabular_sweeps",  # wrong tag — should still complete
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "tsfm_sweeps" in completed


def test_inference_parity_dwell_gate_blocks_off_phase_iteration() -> None:
    """Iteration tagged ``tabular_sweeps`` cannot complete
    ``inference_parity_replay`` even if the evidence key is present.
    (The dwell helper only counts iterations whose search_phase matches.)
    """
    iterations = [
        _iteration(
            metrics={
                "inference_parity": {"passed": True},
                "auto_phase_evidence": True,
            },
            search_phase="tabular_sweeps",
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "inference_parity_replay" not in completed


# --- Issue 10A: tabular-family advancement-key narrowing ---------------- #
#
# Live evidence (`res_dd666f273f99`, `res_97bb030dcf05`): the baseline
# iteration's `metrics_json.config.direction_pct_threshold` (and several
# sibling config defaults) auto-completed `tabular_sweeps`,
# `threshold_calibration`, `temporal_ensemble`, and `atr_sweep` from a
# single non-exploratory run. After narrowing, only deliberate
# exploration markers satisfy the key check; cardinality fallbacks
# (>=6 tabular, >=4 atr, >=2 threshold/temporal) provide the safety net.


def _baseline_iteration(config: dict) -> dict:
    """Baseline-shape iteration: knobs live under ``metrics_json.config``,
    no exploration markers, ``search_phase: baseline_capture``."""
    return _iteration(metrics={"config": config}, search_phase="baseline_capture")


def test_issue10a_tabular_baseline_only_does_not_complete_tabular() -> None:
    """Baseline carrying `direction_pct_threshold` + `roster_preset` no
    longer satisfies tabular_sweeps' advancement key (10A fix).
    """
    iterations = [
        _baseline_iteration(
            {"direction_pct_threshold": 0.03, "roster_preset": "custom"},
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "tabular_sweeps" not in completed


def test_issue10a_tabular_with_variant_completes() -> None:
    """A single iteration emitting the deliberate `tabular_sweep_variant`
    key still completes the phase via the explicit-key path."""
    iterations = [
        _iteration(
            metrics={"tabular_sweep_variant": "roster_v1"},
            search_phase="tabular_sweeps",
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "tabular_sweeps" in completed


def test_issue10a_tabular_six_in_phase_iters_completes_via_cardinality() -> None:
    """Six phase-tagged iterations with NO `tabular_sweep_variant` still
    complete the phase via the >=6 cardinality fallback at line 402.
    """
    iterations = [
        _iteration(metrics={}, search_phase="tabular_sweeps", iteration=i)
        for i in range(1, 7)
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "tabular_sweeps" in completed


def test_issue10a_atr_sweep_baseline_only_does_not_complete() -> None:
    """`volatility_atr_mult` and `atr_multiplier` are baseline config
    defaults; presence must not auto-complete `atr_sweep` (10A fix).
    """
    iterations = [
        _baseline_iteration({"volatility_atr_mult": 2.0, "atr_multiplier": 1.5}),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "atr_sweep" not in completed


def test_issue10a_atr_sweep_with_enabled_flag_completes() -> None:
    """`atr_mult_sweep_enabled` (already emitted by structured_hpo.py when
    the sweep runs deliberately) is the retained explicit key."""
    iterations = [
        _iteration(
            metrics={"atr_mult_sweep_enabled": True},
            search_phase="atr_sweep",
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "atr_sweep" in completed


def test_issue10a_threshold_calibration_baseline_only_does_not_complete() -> None:
    """`threshold_strategy` and `calibration_method` are baseline defaults
    and must no longer auto-complete `threshold_calibration` (10A fix)."""
    iterations = [
        _baseline_iteration(
            {"threshold_strategy": "fixed", "calibration_method": "isotonic"},
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "threshold_calibration" not in completed


def test_issue10a_threshold_calibration_two_in_phase_iters_completes() -> None:
    """Two phase-tagged iterations with no explicit key still complete
    `threshold_calibration` via the >=2 cardinality fallback."""
    iterations = [
        _iteration(metrics={}, search_phase="threshold_calibration", iteration=1),
        _iteration(metrics={}, search_phase="threshold_calibration", iteration=2),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "threshold_calibration" in completed


def test_issue10a_temporal_ensemble_baseline_only_does_not_complete() -> None:
    """Baseline halflife / horizon / pruning config knobs must no longer
    auto-complete `temporal_ensemble` (10A fix)."""
    iterations = [
        _baseline_iteration(
            {
                "sample_weight_halflife": 6000,
                "prediction_horizon": 6,
                "ensemble_pruning": True,
            },
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "temporal_ensemble" not in completed


def test_issue10a_temporal_ensemble_two_in_phase_iters_completes() -> None:
    iterations = [
        _iteration(metrics={}, search_phase="temporal_ensemble", iteration=1),
        _iteration(metrics={}, search_phase="temporal_ensemble", iteration=2),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "temporal_ensemble" in completed


# --- Gap 2: tail-phase floors (2 / 3 / 2) ------------------------------- #
#
# Live evidence (`res_baf6605ce94f`): each tail phase completed with a
# single in-phase iteration because Issue 7's gate used `min_iterations=1`.
# Gap 2 raises the floors from the phase plan: calibration_replay_gates=2,
# multi_seed_robustness=3, inference_parity_replay=2. The dwell-gate now
# reads these from DIRECTION_PHASES / VOLATILITY_PHASES via `_min_iter`.


def test_gap2_calibration_one_in_phase_iter_does_not_complete() -> None:
    """A single in-phase calibration iter is no longer enough; floor=2."""
    iterations = [
        _iteration(
            metrics={**_valid_calibration_evidence(), "auto_phase_evidence": True},
            search_phase="calibration_replay_gates",
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "calibration_replay_gates" not in completed


def test_gap2_calibration_two_in_phase_iters_completes() -> None:
    iterations = [
        _iteration(
            metrics={**_valid_calibration_evidence(), "auto_phase_evidence": True},
            search_phase="calibration_replay_gates",
            iteration=i,
        )
        for i in range(1, 3)
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "calibration_replay_gates" in completed


def test_gap2_multi_seed_two_in_phase_iters_does_not_complete() -> None:
    """Two in-phase seed iters insufficient; floor=3 (need ≥3 seeds for
    stability statistics)."""
    iterations = [
        _iteration(
            metrics={**_valid_seed_evidence(), "auto_phase_evidence": True},
            search_phase="multi_seed_robustness",
            iteration=i,
        )
        for i in range(1, 3)
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "multi_seed_robustness" not in completed


def test_gap2_multi_seed_three_in_phase_iters_completes() -> None:
    iterations = [
        _iteration(
            metrics={**_valid_seed_evidence(), "auto_phase_evidence": True},
            search_phase="multi_seed_robustness",
            iteration=i,
        )
        for i in range(1, 4)
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "multi_seed_robustness" in completed


def test_gap2_inference_parity_one_in_phase_iter_does_not_complete() -> None:
    """A single in-phase parity iter is no longer enough; floor=2."""
    iterations = [
        _iteration(
            metrics={
                **_valid_parity_evidence("run-A"),
                "mlflow_run_id": "run-A",
                "auto_phase_evidence": True,
            },
            search_phase="inference_parity_replay",
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "inference_parity_replay" not in completed


def test_gap2_inference_parity_two_in_phase_iters_completes() -> None:
    iterations = [
        _iteration(
            metrics={
                **_valid_parity_evidence(f"run-{idx}"),
                "mlflow_run_id": f"run-{idx}",
                "auto_phase_evidence": True,
            },
            search_phase="inference_parity_replay",
            iteration=idx,
        )
        for idx in range(1, 3)
    ]
    completed = _completed_phase_ids(iterations, [], [], "direction")
    assert "inference_parity_replay" in completed


def test_gap2_volatility_floors_match_direction() -> None:
    """Same Gap-2 floors apply to volatility phases."""
    iterations = [
        _iteration(
            metrics={**_valid_calibration_evidence(), "auto_phase_evidence": True},
            search_phase="calibration_replay_gates",
        ),
    ]
    completed = _completed_phase_ids(iterations, [], [], "volatility")
    assert "calibration_replay_gates" not in completed  # floor=2, only 1 iter
