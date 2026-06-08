"""RL progress-tracing fixes (issue #3 from RL-TRAINING-ISSUES-ANALYSIS).

Regression coverage for the live defect on res_76d405b8caf9, where an RL
session whose iterations had FAILED still fast-forwarded its reported stage to
``promotion_proposal`` with a phantom ``composite_rl_score=0.0`` metric.

Three independent fixes are exercised:
  3a-i   failed iterations do not count toward phase-advancement cardinality
  3a-ii  ``hpo_screening`` requires a genuinely completed (or disabled) HPO
         study, not a merely ``planned`` one
  3a-iii RL ``validation`` requires real RL-OOS evidence on two attempts
  3b-i   a failed run's placeholder ``primary_metric: 0.0`` is nulled by the
         parser so it cannot masquerade as a result
"""
from __future__ import annotations

import json

from src.core.experiment_parser import parse_prepare_output
from src.core.research_phase_plan import build_phase_state


def _phase_status(state: dict, phase_id: str) -> str:
    return next(
        phase["status"] for phase in state["phases"] if phase["id"] == phase_id
    )


def _failed_rl_iter(iteration: int, phase: str) -> dict:
    """An RL iteration recorded after a failed prepare.py run.

    Mirrors the crash-marker shape the orchestrator persists: the failure
    status lives in metrics_json and the placeholder 0.0 metric is present.
    """
    return {
        "iteration": iteration,
        "search_phase": phase,
        "decision": "discard",
        "metrics_json": json.dumps(
            {
                "status": "failed",
                "primary_metric": 0.0,
                "metric_name": "composite_rl_score",
                "all_gates_passed": False,
            }
        ),
    }


def _ok_rl_iter(iteration: int, phase: str, sharpe: float = 0.12) -> dict:
    """A successful RL walk-forward iteration carrying OOS evidence keys."""
    return {
        "iteration": iteration,
        "search_phase": phase,
        "decision": "keep",
        "metrics_json": json.dumps(
            {
                "status": "completed",
                "primary_metric": sharpe,
                "metric_name": "composite_rl_score",
                "all_gates_passed": True,
                "mean_oos_sharpe": sharpe,
                "mean_oos_return": 0.03,
                "folds_passed": "2/2",
                "trading_score": 0.2,
            }
        ),
    }


def _planned_study() -> dict:
    return {"status": "planned", "completed_trials": 0}


def _completed_study() -> dict:
    return {"status": "completed", "completed_trials": 12}


# ---------------------------------------------------------------------------
# 3a-i — failed iterations must not advance phases
# ---------------------------------------------------------------------------


def test_failed_rl_iterations_do_not_complete_baseline_or_validation() -> None:
    session = {"id": "res_rl_failed", "model_type": "rl"}
    iterations = [
        _failed_rl_iter(1, "baseline_capture"),
        _failed_rl_iter(2, "validation"),
    ]
    state = build_phase_state(
        session=session, iterations=iterations, hpo_studies=[_planned_study()]
    )
    # Two failed runs produced no model — the session is still at the very
    # first phase, NOT fast-forwarded to promotion_proposal.
    assert state["current_phase"] == "baseline_capture"
    assert _phase_status(state, "baseline_capture") == "in_progress"
    assert _phase_status(state, "validation") == "pending"
    assert _phase_status(state, "promotion_proposal") == "pending"


def test_live_repro_two_failed_plus_one_success_is_not_promotion_proposal() -> None:
    """The res_76d405b8caf9 shape: 2 failed + 1 successful RL iter + a planned
    (never-run) HPO study. The reported stage must NOT be promotion_proposal."""
    session = {"id": "res_rl_repro", "model_type": "rl"}
    iterations = [
        _failed_rl_iter(1, "baseline_capture"),
        _failed_rl_iter(2, "validation"),
        _ok_rl_iter(3, "validation", sharpe=-0.4),  # one genuine (poor) run
    ]
    state = build_phase_state(
        session=session, iterations=iterations, hpo_studies=[_planned_study()]
    )
    # One success completes baseline_capture; HPO never ran (planned) so
    # hpo_screening is the honest current phase — not promotion_proposal.
    assert _phase_status(state, "baseline_capture") == "completed"
    assert state["current_phase"] == "hpo_screening"
    assert state["current_phase"] != "promotion_proposal"
    assert _phase_status(state, "validation") == "pending"


# ---------------------------------------------------------------------------
# 3a-ii — hpo_screening requires a real (completed/disabled) study
# ---------------------------------------------------------------------------


def test_planned_hpo_study_does_not_complete_hpo_screening() -> None:
    session = {"id": "res_rl_hpo_planned", "model_type": "rl"}
    iterations = [_ok_rl_iter(1, "baseline_capture")]
    state = build_phase_state(
        session=session, iterations=iterations, hpo_studies=[_planned_study()]
    )
    assert _phase_status(state, "hpo_screening") != "completed"
    assert state["current_phase"] == "hpo_screening"


def test_completed_hpo_study_completes_hpo_screening() -> None:
    session = {"id": "res_rl_hpo_done", "model_type": "rl"}
    iterations = [_ok_rl_iter(1, "baseline_capture")]
    state = build_phase_state(
        session=session, iterations=iterations, hpo_studies=[_completed_study()]
    )
    assert _phase_status(state, "hpo_screening") == "completed"


def test_disabled_hpo_study_does_not_block_hpo_screening() -> None:
    session = {"id": "res_rl_hpo_off", "model_type": "rl"}
    iterations = [_ok_rl_iter(1, "baseline_capture")]
    state = build_phase_state(
        session=session,
        iterations=iterations,
        hpo_studies=[{"status": "disabled", "completed_trials": 0}],
    )
    assert _phase_status(state, "hpo_screening") == "completed"


def test_manual_screening_completes_hpo_screening_with_only_planned_study() -> None:
    """enable_hpo=true persists a ``planned`` study, but the agent may do manual
    screening iterations instead of the structured Optuna study (res_74d62adc7c43).
    Two non-failed in-phase hpo_screening iterations must complete the phase so
    it does not park — while a bare planned study with no in-phase work still
    does not (covered by test_planned_hpo_study_does_not_complete_hpo_screening)."""
    session = {"id": "res_rl_manual_screen", "model_type": "rl"}
    iterations = [
        _ok_rl_iter(1, "baseline_capture"),
        _ok_rl_iter(2, "hpo_screening"),
        _ok_rl_iter(3, "hpo_screening"),
    ]
    state = build_phase_state(
        session=session, iterations=iterations, hpo_studies=[_planned_study()]
    )
    assert _phase_status(state, "hpo_screening") == "completed"


def test_planned_study_with_failed_screening_iters_does_not_complete() -> None:
    """Guard against re-opening the false-advance bug: a planned study plus only
    FAILED hpo_screening iterations (the res_76d405b8caf9 shape) must NOT
    complete the phase — failed iterations are filtered before the cardinality
    check."""
    session = {"id": "res_rl_failed_screen", "model_type": "rl"}
    iterations = [
        _ok_rl_iter(1, "baseline_capture"),
        _failed_rl_iter(2, "hpo_screening"),
        _failed_rl_iter(3, "hpo_screening"),
    ]
    state = build_phase_state(
        session=session, iterations=iterations, hpo_studies=[_planned_study()]
    )
    assert _phase_status(state, "hpo_screening") != "completed"
    assert state["current_phase"] == "hpo_screening"


def test_no_hpo_study_does_not_park_at_hpo_screening() -> None:
    """A no-HPO RL session persists NO study row (orchestrator only plans HPO
    when enable_hpo). hpo_screening must treat "nothing planned" as nothing to
    screen and not block — otherwise the session parks there until timeout
    (observed on res_6461c902f6c7), even though validation has completed."""
    session = {"id": "res_rl_nohpo", "model_type": "rl"}
    iterations = [
        _ok_rl_iter(1, "baseline_capture"),
        _ok_rl_iter(2, "validation"),
        _ok_rl_iter(3, "validation"),
    ]
    state = build_phase_state(session=session, iterations=iterations, hpo_studies=[])
    assert _phase_status(state, "hpo_screening") == "completed"
    # baseline + hpo_screening + validation all done → the session advances to
    # the terminal promotion phase instead of spinning in hpo_screening.
    assert state["current_phase"] == "promotion_proposal"


# ---------------------------------------------------------------------------
# 3a-iii — RL validation needs genuine OOS evidence on two attempts
# ---------------------------------------------------------------------------


def test_rl_validation_completes_with_two_oos_iterations() -> None:
    session = {"id": "res_rl_valid", "model_type": "rl"}
    iterations = [
        _ok_rl_iter(1, "baseline_capture"),
        _ok_rl_iter(2, "validation"),
        _ok_rl_iter(3, "validation"),
    ]
    state = build_phase_state(
        session=session, iterations=iterations, hpo_studies=[_completed_study()]
    )
    assert _phase_status(state, "validation") == "completed"


def test_rl_validation_blocks_without_oos_evidence() -> None:
    """Two successful-but-contentless iterations (no RL OOS keys) must not
    complete RL validation, even though a generic fallback would accept the
    cardinality."""
    session = {"id": "res_rl_no_oos", "model_type": "rl"}
    contentless = {
        "iteration": 2,
        "search_phase": "validation",
        "decision": "keep",
        "metrics_json": json.dumps(
            {"status": "completed", "primary_metric": 0.1, "all_gates_passed": True}
        ),
    }
    iterations = [
        _ok_rl_iter(1, "baseline_capture"),
        contentless,
        {**contentless, "iteration": 3},
    ]
    state = build_phase_state(
        session=session, iterations=iterations, hpo_studies=[_completed_study()]
    )
    assert _phase_status(state, "validation") != "completed"


# ---------------------------------------------------------------------------
# 3b-i — the parser nulls the placeholder failure metric
# ---------------------------------------------------------------------------


def test_parser_nulls_primary_metric_on_failure_status() -> None:
    block = (
        "---\n"
        "status:             failed\n"
        "primary_metric:     0.000000\n"
        "metric_name:        composite_rl_score\n"
        "all_gates_passed:   False\n"
        "---\n"
    )
    metrics = parse_prepare_output(block)
    assert metrics.status == "failed"
    assert metrics.primary_metric is None


def test_parser_keeps_primary_metric_on_success() -> None:
    block = (
        "---\n"
        "status:             completed\n"
        "primary_metric:     0.430025\n"
        "metric_name:        composite_rl_score\n"
        "all_gates_passed:   true\n"
        "---\n"
    )
    metrics = parse_prepare_output(block)
    assert metrics.status == "completed"
    assert metrics.primary_metric == 0.430025


def test_parser_nulls_metric_for_each_failure_status() -> None:
    for status in ("crash", "timeout", "auth_failed", "gpu_busy", "error", "pruned"):
        block = (
            "---\n"
            f"status:             {status}\n"
            "primary_metric:     0.000000\n"
            "metric_name:        composite_rl_score\n"
            "---\n"
        )
        assert parse_prepare_output(block).primary_metric is None, status
