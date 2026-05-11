"""AR-5: Tests for artifact-bound evidence-key validation for promotion-family phases.

Defect D3 (part 1): ``_completed_phase_ids`` in ``research_phase_plan.py``
marked phases like ``multi_seed_robustness`` and ``inference_parity_replay``
complete purely on the presence of an evidence key in ``metrics_json`` — WITHOUT
verifying that the evidence actually pointed to real, distinct artifacts. This
allowed the LLM to "advance" phases by emitting:

  * ``seed_trials`` entries that all share the same ``mlflow_run_id``,
  * ``inference_parity`` payload whose ``mlflow_run_id`` is identical to a
    prior training iteration's run_id, or
  * ``calibration_full_validation`` without a ``selected.run_id`` or
    ``economic_replay.gates`` dict.

Fix (two-part):

1. New function ``check_evidence_artifact(metrics, phase_id, *, prior_run_ids)``
   in ``consistency_validator.py`` performs the artifact validation check and
   returns the blocker string ``"evidence_artifact_missing_for_<phase_id>"`` on
   failure (or ``None`` on success).

2. ``_completed_phase_ids`` in ``research_phase_plan.py`` gates each
   promotion-family phase evidence-key acceptance behind
   ``check_evidence_artifact``.  A phase is only marked complete when BOTH the
   evidence key IS present AND the artifact check PASSES.
"""

from __future__ import annotations

import json

import pytest

from src.core.consistency_validator import (
    EVIDENCE_ARTIFACT_PHASES,
    check_evidence_artifact,
)
from src.core.research_phase_plan import build_phase_state


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_seed_trial(run_id: str) -> dict:
    return {"mlflow_run_id": run_id, "seed": int(run_id[-1], 16) % 10}


def _seed_trials_metrics(run_ids: list[str], n_seed_trials: int | None = None) -> dict:
    """Build a metrics dict that carries a ``seed_trials`` list."""
    payload: dict = {
        "primary_metric": 0.71,
        "all_gates_passed": True,
        "seed_trials": [_make_seed_trial(rid) for rid in run_ids],
    }
    if n_seed_trials is not None:
        payload["n_seed_trials"] = n_seed_trials
    return payload


def _inference_parity_metrics(
    run_id: str,
    feature_count_alignment_passed: bool = True,
) -> dict:
    return {
        "primary_metric": 0.71,
        "all_gates_passed": True,
        "mlflow_run_id": run_id,
        "inference_parity": {
            "feature_name_alignment_passed": True,
            "feature_count_alignment_passed": feature_count_alignment_passed,
            "model_roster_parity_passed": True,
            "mlflow_run_id": run_id,
        },
    }


def _calibration_gates_metrics(*, selected_run_id: str | None, has_gates: bool) -> dict:
    payload: dict = {
        "primary_metric": 0.71,
        "all_gates_passed": True,
        "calibration_full_validation": {
            "selected": {"run_id": selected_run_id, "metrics": {"ece": 0.02}},
        },
    }
    if has_gates:
        payload["economic_replay"] = {
            "gates": {"all_gates_passed": True, "replay_sharpe": 1.2}
        }
    return payload


def _iteration_row(
    *,
    iteration: int,
    metrics: dict,
    search_phase: str | None = None,
    mlflow_run_id: str | None = None,
) -> dict:
    """Minimal iteration row shape matching what the ResultsStore returns."""
    m = dict(metrics)
    if search_phase:
        m["search_phase"] = search_phase
    if mlflow_run_id and "mlflow_run_id" not in m:
        m["mlflow_run_id"] = mlflow_run_id
    return {
        "iteration": iteration,
        "metrics_json": json.dumps(m),
        "search_phase": search_phase,
        "config_snapshot": None,
        "consistency_report_json": None,
        "all_gates_passed": int(metrics.get("all_gates_passed", False)),
        "decision": "keep",
        "primary_metric": metrics.get("primary_metric", 0.70),
    }


# ---------------------------------------------------------------------------
# 1. check_evidence_artifact — multi_seed_robustness
# ---------------------------------------------------------------------------


def test_evidence_artifact_check_passes_for_real_seed_trials() -> None:
    """AR-5: 5 seed_trials with distinct mlflow_run_ids → None (pass).

    Real seed trials must each record a unique mlflow_run_id so the validator
    can confirm that 5 separate training runs were executed.
    """
    metrics = _seed_trials_metrics(
        run_ids=["run-A1", "run-B2", "run-C3", "run-D4", "run-E5"],
        n_seed_trials=5,
    )
    result = check_evidence_artifact(metrics, "multi_seed_robustness")
    assert result is None, (
        "5 distinct run_ids should pass the multi_seed_robustness artifact check"
    )


def test_evidence_artifact_check_blocks_synthetic_seed_trials() -> None:
    """AR-5: 5 seed_trials but all share the same mlflow_run_id → blocker.

    This is the synthetic-emission pattern from session res_a1ba6cbd520f
    (iters 95, 97, 99): the LLM emitted a seed_trials list whose entries were
    all copies of the same run.
    """
    metrics = _seed_trials_metrics(
        run_ids=["run-SAME"] * 5,
        n_seed_trials=5,
    )
    result = check_evidence_artifact(metrics, "multi_seed_robustness")
    assert result == "evidence_artifact_missing_for_multi_seed_robustness", (
        "Duplicate run_ids must produce the expected blocker string"
    )


def test_evidence_artifact_check_blocks_when_seed_trials_too_few() -> None:
    """Fewer seed_trial entries than n_seed_trials → blocker."""
    metrics = _seed_trials_metrics(
        run_ids=["run-A", "run-B"],  # only 2
        n_seed_trials=5,
    )
    result = check_evidence_artifact(metrics, "multi_seed_robustness")
    assert result == "evidence_artifact_missing_for_multi_seed_robustness"


def test_evidence_artifact_check_blocks_when_seed_trials_missing() -> None:
    """No seed_trials key at all → blocker."""
    metrics = {"primary_metric": 0.70, "all_gates_passed": True}
    result = check_evidence_artifact(metrics, "multi_seed_robustness")
    assert result == "evidence_artifact_missing_for_multi_seed_robustness"


def test_evidence_artifact_check_default_n_required_is_two() -> None:
    """When n_seed_trials is absent, default minimum is 2 unique ids."""
    # 1 unique id < 2 → blocker
    metrics = _seed_trials_metrics(run_ids=["run-A"])
    assert check_evidence_artifact(metrics, "multi_seed_robustness") is not None

    # 2 unique ids ≥ 2 → pass
    metrics2 = _seed_trials_metrics(run_ids=["run-A", "run-B"])
    assert check_evidence_artifact(metrics2, "multi_seed_robustness") is None


def test_evidence_artifact_check_accepts_artifact_hash_in_seed_trials() -> None:
    """artifact_hash is an acceptable substitute for mlflow_run_id."""
    metrics = {
        "seed_trials": [
            {"artifact_hash": "hash-1"},
            {"artifact_hash": "hash-2"},
        ]
    }
    result = check_evidence_artifact(metrics, "multi_seed_robustness")
    assert result is None


def test_evidence_artifact_force_evidence_acceptance_bypasses_check() -> None:
    """force_evidence_acceptance: True skips validation with a warning."""
    metrics = {
        "force_evidence_acceptance": True,
        "seed_trials": [{"mlflow_run_id": "dup"}] * 5,
        "n_seed_trials": 5,
    }
    result = check_evidence_artifact(metrics, "multi_seed_robustness")
    assert result is None, "force_evidence_acceptance must bypass the artifact gate"


# ---------------------------------------------------------------------------
# 2. check_evidence_artifact — inference_parity_replay
# ---------------------------------------------------------------------------


def test_evidence_artifact_check_passes_for_inference_parity_with_new_run() -> None:
    """AR-5: inference_parity with feature_count_alignment_passed + new run_id → pass.

    The inference parity iteration has a different mlflow_run_id than the
    prior training iterations — it ran a real (new) validation replay.
    """
    metrics = _inference_parity_metrics("run-NEW-parity")
    prior_run_ids = {"run-train-1", "run-train-2"}  # prior training runs

    result = check_evidence_artifact(
        metrics, "inference_parity_replay", prior_run_ids=prior_run_ids
    )
    assert result is None, (
        "A parity iteration with a distinct run_id should pass the artifact check"
    )


def test_evidence_artifact_check_blocks_inference_parity_when_run_id_unchanged() -> None:
    """AR-5: inference_parity with same run_id as a prior training run → blocker.

    The LLM re-emitted the parity evidence using a run_id that appeared in an
    earlier tabular-sweep iteration — the parity validation was never actually
    re-run.
    """
    metrics = _inference_parity_metrics("run-SAME")
    prior_run_ids = {"run-SAME", "run-other"}  # run-SAME already in prior set

    result = check_evidence_artifact(
        metrics, "inference_parity_replay", prior_run_ids=prior_run_ids
    )
    assert result == "evidence_artifact_missing_for_inference_parity_replay", (
        "Same run_id as a prior training iteration must produce the blocker"
    )


def test_evidence_artifact_check_blocks_inference_parity_when_feature_check_failed() -> None:
    """feature_count_alignment_passed=False → blocker regardless of run_id."""
    metrics = _inference_parity_metrics("run-NEW", feature_count_alignment_passed=False)
    result = check_evidence_artifact(
        metrics, "inference_parity_replay", prior_run_ids={"run-OLD"}
    )
    assert result == "evidence_artifact_missing_for_inference_parity_replay"


def test_evidence_artifact_check_blocks_inference_parity_when_parity_missing() -> None:
    """No inference_parity key at all → blocker."""
    metrics = {"primary_metric": 0.70, "mlflow_run_id": "run-X"}
    result = check_evidence_artifact(metrics, "inference_parity_replay")
    assert result == "evidence_artifact_missing_for_inference_parity_replay"


def test_evidence_artifact_check_skips_run_id_comparison_when_prior_not_provided() -> None:
    """When prior_run_ids is not passed, the run_id uniqueness check is skipped.

    Callers that do not have cross-session context still benefit from the
    feature_count_alignment_passed check.
    """
    # Same run_id as hypothetical prior — but prior_run_ids NOT passed.
    metrics = _inference_parity_metrics("run-REPEATED")
    result = check_evidence_artifact(metrics, "inference_parity_replay")
    # Should pass because prior_run_ids=None (no comparison possible)
    assert result is None


# ---------------------------------------------------------------------------
# 3. check_evidence_artifact — calibration_replay_gates
# ---------------------------------------------------------------------------


def test_evidence_artifact_check_passes_for_valid_calibration_gates() -> None:
    """selected.run_id present AND economic_replay.gates dict present → pass."""
    metrics = _calibration_gates_metrics(
        selected_run_id="run-cal-1",
        has_gates=True,
    )
    result = check_evidence_artifact(metrics, "calibration_replay_gates")
    assert result is None


def test_evidence_artifact_check_blocks_calibration_when_run_id_missing() -> None:
    """calibration_full_validation.selected.run_id is None → blocker."""
    metrics = _calibration_gates_metrics(selected_run_id=None, has_gates=True)
    result = check_evidence_artifact(metrics, "calibration_replay_gates")
    assert result == "evidence_artifact_missing_for_calibration_replay_gates"


def test_evidence_artifact_check_blocks_calibration_when_gates_missing() -> None:
    """economic_replay.gates dict absent → blocker."""
    metrics = _calibration_gates_metrics(selected_run_id="run-cal-2", has_gates=False)
    result = check_evidence_artifact(metrics, "calibration_replay_gates")
    assert result == "evidence_artifact_missing_for_calibration_replay_gates"


# ---------------------------------------------------------------------------
# 4. Non-scoped phases pass through
# ---------------------------------------------------------------------------


def test_evidence_artifact_check_returns_none_for_non_scoped_phase() -> None:
    """Phases not in EVIDENCE_ARTIFACT_PHASES return None unconditionally."""
    metrics = {"primary_metric": 0.70}
    for phase_id in ("tabular_sweeps", "baseline_capture", "atr_sweep"):
        assert check_evidence_artifact(metrics, phase_id) is None, (
            f"Phase '{phase_id}' should not be gated by artifact check"
        )


def test_evidence_artifact_phases_constant_covers_expected_phases() -> None:
    """EVIDENCE_ARTIFACT_PHASES must cover all promotion-family phases."""
    assert "multi_seed_robustness" in EVIDENCE_ARTIFACT_PHASES
    assert "inference_parity_replay" in EVIDENCE_ARTIFACT_PHASES
    assert "calibration_replay_gates" in EVIDENCE_ARTIFACT_PHASES
    assert "promotion_proposal" in EVIDENCE_ARTIFACT_PHASES


# ---------------------------------------------------------------------------
# 5. _completed_phase_ids integration via build_phase_state
# ---------------------------------------------------------------------------


def _session_row(model_type: str = "direction") -> dict:
    return {"id": "res_ar5_test", "model_type": model_type}


def _all_prior_phases_completed_iters() -> list:
    """Realistic prior iterations that mark baseline_capture+tabular_sweeps done."""
    return [
        _iteration_row(
            iteration=i,
            metrics={
                "primary_metric": 0.62 + i * 0.01,
                "all_gates_passed": True,
                "config": {
                    "direction_pct_threshold": 0.55,
                    "tabular_sweep_variant": f"v{i}",
                    "calibration_full_validation": {
                        "selected": {"run_id": f"run-cal-{i}", "metrics": {"ece": 0.02}}
                    },
                },
                "economic_replay": {
                    "gates": {"all_gates_passed": True}
                },
            },
            search_phase="tabular_sweeps",
        )
        for i in range(1, 7)  # 6 iterations → tabular_sweeps completed
    ]


def test_phase_not_marked_complete_when_evidence_artifact_blocker_active() -> None:
    """AR-5 core: multi_seed_robustness NOT completed when seed_trials are synthetic.

    Seeds a session with enough iterations to complete all earlier phases plus
    one ``multi_seed_robustness`` iteration with duplicate run_ids.  The phase
    plan must stay at ``multi_seed_robustness`` (or a later phase) without
    advancing past it.

    The critical assertion is that ``multi_seed_robustness`` does NOT appear
    in the completed phase ids — it remains ``in_progress`` or ``pending``
    rather than ``completed``.
    """
    session = _session_row()
    iterations = _all_prior_phases_completed_iters()

    # Add a synthetic multi_seed_robustness iteration (all same run_id).
    synthetic_seed_iter = _iteration_row(
        iteration=7,
        metrics={
            "primary_metric": 0.71,
            "all_gates_passed": True,
            "seed_trials": [{"mlflow_run_id": "run-SAME"}] * 5,
            "n_seed_trials": 5,
            "seeds_passed_gates": True,  # evidence key present
        },
        search_phase="multi_seed_robustness",
    )
    iterations.append(synthetic_seed_iter)

    state = build_phase_state(session=session, iterations=iterations)
    phase_statuses = {p["id"]: p["status"] for p in state["phases"]}

    assert phase_statuses["multi_seed_robustness"] != "completed", (
        "Synthetic seed trials (duplicate run_ids) must NOT advance "
        "multi_seed_robustness to 'completed'"
    )
    # Earlier phases should still be completed.
    assert phase_statuses["tabular_sweeps"] == "completed"


def test_phase_marked_complete_when_real_seed_trials_present() -> None:
    """Multi-seed phase advances when seed_trials carry distinct run_ids."""
    session = _session_row()
    iterations = _all_prior_phases_completed_iters()

    real_seed_iter = _iteration_row(
        iteration=7,
        metrics={
            "primary_metric": 0.73,
            "all_gates_passed": True,
            "seed_trials": [
                {"mlflow_run_id": f"run-seed-{i}"} for i in range(5)
            ],
            "n_seed_trials": 5,
            "seeds_passed_gates": True,
        },
        search_phase="multi_seed_robustness",
    )
    iterations.append(real_seed_iter)

    state = build_phase_state(session=session, iterations=iterations)
    phase_statuses = {p["id"]: p["status"] for p in state["phases"]}

    assert phase_statuses["multi_seed_robustness"] == "completed", (
        "Distinct run_ids must advance multi_seed_robustness to 'completed'"
    )


def test_inference_parity_not_completed_when_run_id_from_prior_phase() -> None:
    """Inference parity phase not completed when run_id matches a training iteration.

    The LLM copied a tabular_sweeps iteration's mlflow_run_id into the
    inference_parity evidence — the phase should stay in_progress.
    """
    session = _session_row()
    iterations = _all_prior_phases_completed_iters()

    # Prior training run_id that will be reused:
    prior_run_id = "run-training-baseline"
    # Inject a prior non-inference iteration with this run_id.
    prior_iter = _iteration_row(
        iteration=7,
        metrics={
            "primary_metric": 0.72,
            "mlflow_run_id": prior_run_id,
            "all_gates_passed": True,
        },
        search_phase="multi_seed_robustness",
    )
    iterations.append(prior_iter)

    # Inference parity iteration reuses the same run_id.
    parity_iter = _iteration_row(
        iteration=8,
        metrics={
            "primary_metric": 0.72,
            "mlflow_run_id": prior_run_id,
            "all_gates_passed": True,
            "inference_parity": {
                "feature_name_alignment_passed": True,
                "feature_count_alignment_passed": True,
                "model_roster_parity_passed": True,
                "mlflow_run_id": prior_run_id,
            },
        },
        search_phase="inference_parity_replay",
    )
    iterations.append(parity_iter)

    state = build_phase_state(session=session, iterations=iterations)
    phase_statuses = {p["id"]: p["status"] for p in state["phases"]}

    assert phase_statuses["inference_parity_replay"] != "completed", (
        "Inference parity reusing a prior run_id must NOT advance the phase"
    )


# ---------------------------------------------------------------------------
# AR-6: _is_synthetic_promotion_iteration unit tests
# ---------------------------------------------------------------------------

from src.core.consistency_validator import _is_synthetic_promotion_iteration  # noqa: E402
from src.core.research_phase_plan import _prior_best_metrics  # noqa: E402


# Shared prior-best fixture for AR-6 unit tests.
_PRIOR_BEST = {
    "primary_metric": 0.6394,
    "mlflow_run_id": "run-train-prior-001",
    "training_time_s": 123.4,
}


def test_synthetic_promotion_iteration_blocked() -> None:
    """AR-6: training_time_s=None + metric matches prior + no new run_id → blocker.

    The LLM emits a multi_seed_robustness evidence payload without running
    any training.  All three synthetic conditions hold, so the blocker must be
    returned.
    """
    metrics = {
        "training_time_s": None,
        "primary_metric": 0.6394,          # exact match (4dp) to prior
        "mlflow_run_id": None,             # no new run recorded
        "seed_trials": [{"mlflow_run_id": f"run-s-{i}"} for i in range(5)],
        "n_seed_trials": 5,
        "seeds_passed_gates": True,
    }
    result = _is_synthetic_promotion_iteration(metrics, _PRIOR_BEST, "multi_seed_robustness")
    assert result == "synthetic_phase_iteration_multi_seed_robustness", (
        "All three synthetic conditions met → blocker must be emitted"
    )


def test_synthetic_check_allows_real_promotion_metadata() -> None:
    """AR-6: server-owned promotion finalisation is NOT synthetic.

    development_promotion_metadata with promotion_decision + rollback_target is
    legitimate — the promotion review process intentionally emits no training run.
    The exception clause must fire and return None regardless of metric/run state.
    """
    metrics = {
        "training_time_s": None,
        "primary_metric": 0.6394,          # same as prior
        "mlflow_run_id": None,
        "development_promotion_metadata": {
            "promotion_decision": "approved",
            "rollback_target": "direction_model_v2.1.0",
            "approved_by": "server",
        },
    }
    result = _is_synthetic_promotion_iteration(metrics, _PRIOR_BEST, "promotion_proposal")
    assert result is None, (
        "Real promotion finalisation with decision+rollback_target must NOT be flagged"
    )


def test_synthetic_check_not_triggered_when_training_time_present() -> None:
    """AR-6: when training_time_s is non-None, never synthetic (condition 1 fails)."""
    metrics = {
        "training_time_s": 0.001,          # tiny but non-None — real training ran
        "primary_metric": 0.6394,
        "mlflow_run_id": None,
    }
    result = _is_synthetic_promotion_iteration(metrics, _PRIOR_BEST, "multi_seed_robustness")
    assert result is None


def test_synthetic_check_not_triggered_when_metric_changed() -> None:
    """AR-6: improved metric breaks condition 2 → not synthetic."""
    metrics = {
        "training_time_s": None,
        "primary_metric": 0.6500,          # differs at 4dp from 0.6394
        "mlflow_run_id": None,
    }
    result = _is_synthetic_promotion_iteration(metrics, _PRIOR_BEST, "multi_seed_robustness")
    assert result is None


def test_synthetic_check_not_triggered_when_metric_within_4dp_tolerance() -> None:
    """AR-6: 0.63940001 rounds to same 4dp as 0.6394 → still synthetic."""
    metrics = {
        "training_time_s": None,
        "primary_metric": 0.63940001,
        "mlflow_run_id": None,
    }
    result = _is_synthetic_promotion_iteration(metrics, _PRIOR_BEST, "multi_seed_robustness")
    assert result == "synthetic_phase_iteration_multi_seed_robustness"


def test_synthetic_check_not_triggered_when_new_run_id() -> None:
    """AR-6: a distinct mlflow_run_id breaks condition 3 → not synthetic."""
    metrics = {
        "training_time_s": None,
        "primary_metric": 0.6394,
        "mlflow_run_id": "run-brand-new-999",
    }
    result = _is_synthetic_promotion_iteration(metrics, _PRIOR_BEST, "multi_seed_robustness")
    assert result is None


def test_synthetic_check_not_triggered_when_prior_best_empty() -> None:
    """AR-6: empty prior_best dict disables comparison conservatively (no block)."""
    metrics = {
        "training_time_s": None,
        "primary_metric": 0.6394,
        "mlflow_run_id": None,
    }
    result = _is_synthetic_promotion_iteration(metrics, {}, "multi_seed_robustness")
    assert result is None, (
        "No prior context → conservative: must not block (avoids false positives)"
    )


def test_synthetic_check_promotion_proposal_blocked_without_promotion_metadata() -> None:
    """AR-6: promotion_proposal iteration without decision/rollback_target is synthetic."""
    metrics = {
        "training_time_s": None,
        "primary_metric": 0.6394,
        "mlflow_run_id": None,
        # development_promotion_metadata present but incomplete — no rollback_target
        "development_promotion_metadata": {
            "promotion_decision": None,
            "rollback_target": None,
        },
        "promotion_allowed": True,
    }
    result = _is_synthetic_promotion_iteration(metrics, _PRIOR_BEST, "promotion_proposal")
    assert result == "synthetic_phase_iteration_promotion_proposal"


# ---------------------------------------------------------------------------
# AR-6: _prior_best_metrics helper unit tests
# ---------------------------------------------------------------------------


def test_prior_best_metrics_returns_most_recent_non_promotion_family() -> None:
    """_prior_best_metrics returns the last training-phase iteration's metrics."""
    iters = [
        _iteration_row(
            iteration=i,
            metrics={"primary_metric": 0.60 + i * 0.01, "training_time_s": 10.0},
            search_phase="tabular_sweeps",
        )
        for i in range(1, 4)
    ]
    # Add a promotion-family iteration — must be excluded.
    iters.append(
        _iteration_row(
            iteration=4,
            metrics={"primary_metric": 0.99, "training_time_s": None},
            search_phase="multi_seed_robustness",
        )
    )
    result = _prior_best_metrics(iters)
    # Should return iter 3's metrics (most recent non-promotion, i=3 → 0.60 + 3*0.01 = 0.63)
    assert result["primary_metric"] == pytest.approx(0.63)


def test_prior_best_metrics_returns_empty_when_no_qualifying_iteration() -> None:
    """_prior_best_metrics returns {} when all iterations are promotion-family."""
    iters = [
        _iteration_row(
            iteration=i,
            metrics={"primary_metric": 0.70, "training_time_s": None},
            search_phase="multi_seed_robustness",
        )
        for i in range(1, 4)
    ]
    result = _prior_best_metrics(iters)
    assert result == {}


# ---------------------------------------------------------------------------
# AR-6: integration via build_phase_state — synthetic phase gating
# ---------------------------------------------------------------------------


def test_multi_seed_phase_not_advanced_when_all_iterations_are_synthetic() -> None:
    """AR-6 core: multi_seed_robustness stays incomplete when all seed iters are synthetic.

    A session where every multi_seed_robustness iteration has training_time_s=None
    and the same primary_metric as the best prior training iteration must NOT
    advance multi_seed_robustness to 'completed'.
    """
    session = _session_row()
    prior_iters = _all_prior_phases_completed_iters()
    # Prior best metric comes from _all_prior_phases_completed_iters — last one is ~0.68
    prior_metric = max(
        json.loads(it["metrics_json"]).get("primary_metric", 0)
        for it in prior_iters
    )

    # All seed iterations are synthetic: no training, metric copied from prior best.
    synthetic_seed_iters = [
        _iteration_row(
            iteration=7 + i,
            metrics={
                "training_time_s": None,
                "primary_metric": prior_metric,
                "mlflow_run_id": None,
                "seed_trials": [{"mlflow_run_id": f"run-s-{j}"} for j in range(5)],
                "n_seed_trials": 5,
                "seeds_passed_gates": True,
            },
            search_phase="multi_seed_robustness",
        )
        for i in range(3)
    ]
    all_iters = prior_iters + synthetic_seed_iters

    state = build_phase_state(session=session, iterations=all_iters)
    phase_statuses = {p["id"]: p["status"] for p in state["phases"]}

    assert phase_statuses.get("multi_seed_robustness") != "completed", (
        "Synthetic seed iterations (no training, copied metric) must NOT advance "
        "multi_seed_robustness to 'completed'"
    )


def test_multi_seed_phase_advances_when_iteration_has_training_time() -> None:
    """AR-6: multi_seed_robustness advances when training_time_s is present (not synthetic)."""
    session = _session_row()
    prior_iters = _all_prior_phases_completed_iters()
    prior_metric = max(
        json.loads(it["metrics_json"]).get("primary_metric", 0)
        for it in prior_iters
    )

    real_seed_iter = _iteration_row(
        iteration=7,
        metrics={
            "training_time_s": 45.7,   # real training ran
            "primary_metric": prior_metric,  # metric may be same — but training ran
            "mlflow_run_id": None,
            "seed_trials": [{"mlflow_run_id": f"run-s-{i}"} for i in range(5)],
            "n_seed_trials": 5,
            "seeds_passed_gates": True,
        },
        search_phase="multi_seed_robustness",
    )

    state = build_phase_state(
        session=session, iterations=prior_iters + [real_seed_iter]
    )
    phase_statuses = {p["id"]: p["status"] for p in state["phases"]}

    assert phase_statuses.get("multi_seed_robustness") == "completed", (
        "Non-synthetic seed iteration (training_time_s present) must advance the phase"
    )
