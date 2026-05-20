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
    """Same valid evidence, but the agent tagged the iteration in-phase →
    phase completes (the phase-tag gate is satisfied)."""
    iterations = [
        _iteration(
            metrics={**_valid_calibration_evidence(), "auto_phase_evidence": True},
            search_phase="calibration_replay_gates",
        ),
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
    iterations = [
        _iteration(
            metrics={**_valid_seed_evidence(), "auto_phase_evidence": True},
            search_phase="multi_seed_robustness",
        ),
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
