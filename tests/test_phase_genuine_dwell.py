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
