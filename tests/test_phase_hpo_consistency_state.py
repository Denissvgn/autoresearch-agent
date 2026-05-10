from __future__ import annotations

import json

import pytest
import yaml

from src.core.consistency_validator import build_consistency_report
from src.core.research_phase_plan import build_phase_state
from src.core.research_state import build_research_state
from src.core.structured_hpo import (
    build_structured_hpo_plan,
    materialize_planned_trials,
    validate_config_patch,
)


def _phase_status(state: dict, phase_id: str) -> str:
    return next(
        phase["status"]
        for phase in state["phases"]
        if phase["id"] == phase_id
    )


def _passing_metrics() -> dict:
    return {
        "all_gates_passed": True,
        "config": {
            "calibration_full_validation": {
                "selected": {"metrics": {"ece": 0.02}},
            }
        },
        "economic_replay": {"gates": {"all_gates_passed": True}},
        "inference_parity": {
            "feature_name_alignment_passed": True,
            "feature_count_alignment_passed": True,
            "model_roster_parity_passed": True,
        },
        "artifact_uri": "mlflow://runs/run-1/model",
        "mlflow_run_id": "run-1",
        "rollback_target": "direction_model:1",
        "smoke_validation": {"passed": True},
    }


def test_direction_phase_state_advances_past_tabular_sweeps():
    session = {
        "id": "res_phase",
        "model_type": "direction",
    }
    iterations = [
        {
            "iteration": 1,
            "metrics_json": json.dumps({"config": {}}),
            "all_gates_passed": 0,
        },
        {
            "iteration": 2,
            "metrics_json": json.dumps(_passing_metrics()),
            "all_gates_passed": 1,
        },
    ]

    state = build_phase_state(session=session, iterations=iterations)

    assert state["schema_version"] == "autoresearch_phase_state.v1"
    assert state["current_phase"] == "adaptive_feature_sweeps"
    assert state["phases"][0]["status"] == "completed"
    assert state["phases"][1]["status"] == "completed"
    assert _phase_status(state, "promotion_proposal") == "pending"


def test_promotion_proposal_requires_preview_or_promotion_evidence():
    session = {
        "id": "res_phase_promotion",
        "model_type": "direction",
    }
    iterations = [
        {
            "iteration": 1,
            "metrics_json": json.dumps(_passing_metrics()),
            "all_gates_passed": 1,
        },
    ]

    state = build_phase_state(session=session, iterations=iterations)

    assert _phase_status(state, "promotion_proposal") == "pending"

    iterations[0]["metrics_json"] = json.dumps(
        {
            **_passing_metrics(),
            "development_promotion_metadata": {
                "promotion_allowed": True,
                "rollback_target": "direction_model:1",
            },
        }
    )

    state = build_phase_state(session=session, iterations=iterations)

    assert _phase_status(state, "promotion_proposal") == "completed"


def test_research_state_marks_iteration_budget_exhausted_when_phases_pending():
    session = {
        "id": "res_phase_budget",
        "model_type": "direction",
        "status": "completed",
        "max_iterations": 2,
        "max_budget_usd": 1.0,
        "total_api_cost_usd": 0.4,
    }
    iterations = [
        {
            "iteration": 1,
            "metrics_json": json.dumps({"config": {}}),
            "all_gates_passed": 0,
            "primary_metric": 0.52,
            "metric_name": "score",
            "decision": "keep",
        },
        {
            "iteration": 2,
            "metrics_json": json.dumps({"all_gates_passed": True}),
            "all_gates_passed": 1,
            "primary_metric": 0.57,
            "metric_name": "score",
            "decision": "keep",
        },
    ]

    state = build_research_state(
        session=session,
        iterations=iterations,
        hpo_studies=[],
        promotions=[],
    )

    assert state["research_outcome"] == "iteration_budget_exhausted"
    assert state["terminal_reason"] == "max_iterations"
    assert _phase_status(state["phase_state"], "promotion_proposal") == "pending"


def test_structured_direction_hpo_plan_is_bounded_by_iterations():
    plan = build_structured_hpo_plan(
        research_id="res_hpo",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        quick_mode=True,
        max_iterations=6,
        max_budget_usd=2.0,
        timeout_s=3600,
        enable_hpo=True,
        hpo_trials=50,
        hpo_timesteps=50000,
    )

    assert plan["enabled"] is True
    assert plan["study_id"] == "hpo_res_hpo_direction"
    assert plan["max_trials"] == 6
    assert len(plan["trials"]) == 6
    assert "deadzone_width" in plan["search_space"]
    assert "direction_pct_threshold" in plan["search_space"]
    assert plan["budget"]["max_budget_usd"] == 2.0
    assert all(trial["config_hash"] for trial in plan["trials"])
    assert all("expected_command" in trial for trial in plan["trials"])
    assert all("planned_trials" in trial["expected_command"] for trial in plan["trials"])


def test_structured_hpo_plan_never_inflates_requested_trials():
    direction_plan = build_structured_hpo_plan(
        research_id="res_hpo_small",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        quick_mode=False,
        max_iterations=1,
        max_budget_usd=1.0,
        timeout_s=600,
        enable_hpo=True,
        hpo_trials=1,
        hpo_timesteps=50000,
    )
    rl_plan = build_structured_hpo_plan(
        research_id="res_hpo_rl",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        quick_mode=False,
        max_iterations=100,
        max_budget_usd=10.0,
        timeout_s=7200,
        enable_hpo=True,
        hpo_trials=1,
        hpo_timesteps=50000,
    )

    assert direction_plan["max_trials"] == 1
    assert len(direction_plan["trials"]) == 1
    assert rl_plan["max_trials"] == 1
    assert rl_plan["trials"] == []


def test_structured_hpo_plan_bounds_direction_trials_by_budget():
    plan = build_structured_hpo_plan(
        research_id="res_hpo_budget",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        quick_mode=False,
        max_iterations=10,
        max_budget_usd=0.50,
        timeout_s=600,
        enable_hpo=True,
        hpo_trials=10,
        hpo_timesteps=50000,
    )

    assert plan["budget"]["per_trial_budget_usd"] == 0.25
    assert plan["max_trials"] == 2
    assert len(plan["trials"]) == 2


def test_direction_structured_trials_include_deadzone_horizon_calibration_controls():
    plan = build_structured_hpo_plan(
        research_id="res_hpo_controls",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        quick_mode=True,
        max_iterations=8,
        max_budget_usd=2.0,
        timeout_s=3600,
        enable_hpo=True,
        hpo_trials=8,
        hpo_timesteps=50000,
    )

    patches = [trial["config_patch"] for trial in plan["trials"]]
    thresholds = {patch["direction_pct_threshold"] for patch in patches}
    rosters = {patch["roster_preset"] for patch in patches}
    calibrations = {patch["stacking_calibration_method"] for patch in patches}

    assert {0.020, 0.025}.issubset(thresholds)
    assert "scoped_tabular" in rosters
    assert "full_tabular" in rosters
    assert "sigmoid" in calibrations
    assert any(
        patch.get("stacking_calibration_fallback_min_samples")
        for patch in patches
    )
    assert all(patch["auto_select_horizon"] is True for patch in patches)
    assert all("horizon_candidates" in patch for patch in patches)
    assert {patch["feature_library_version"] for patch in patches} == {"2.3.0"}
    assert all(patch["log_feature_provenance"] is True for patch in patches)
    assert all(patch["validate_feature_consistency"] is True for patch in patches)
    assert all("max_signal_rate" in patch for patch in patches)


def test_structured_volatility_hpo_uses_current_feature_library_version():
    plan = build_structured_hpo_plan(
        research_id="res_hpo_volatility",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="volatility",
        quick_mode=True,
        max_iterations=4,
        max_budget_usd=2.0,
        timeout_s=3600,
        enable_hpo=True,
        hpo_trials=4,
        hpo_timesteps=50000,
    )

    assert {trial["config_patch"]["feature_library_version"] for trial in plan["trials"]} == {
        "2.3.0"
    }


def test_structured_hpo_invalid_knobs_are_rejected():
    with pytest.raises(ValueError, match="unsupported_knob"):
        validate_config_patch("direction", {"unsupported_knob": 1})


def test_materialize_planned_trials_writes_concrete_train_yamls(tmp_path):
    workspace = tmp_path / "direction"
    workspace.mkdir()
    (workspace / "train.yaml").write_text(
        yaml.safe_dump(
            {
                "instrument": "DOGE_USDT",
                "timeframe": "15m",
                "direction_pct_threshold": 0.020,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    plan = build_structured_hpo_plan(
        research_id="res_hpo_materialize",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        quick_mode=True,
        max_iterations=1,
        max_budget_usd=2.0,
        timeout_s=3600,
        enable_hpo=True,
        hpo_trials=1,
        hpo_timesteps=50000,
    )

    written = materialize_planned_trials(plan, workspace)

    assert len(written) == 1
    trial = plan["trials"][0]
    trial_config = workspace / "planned_trials" / trial["trial_id"] / "train.yaml"
    assert trial_config.exists()
    text = trial_config.read_text(encoding="utf-8")
    assert f"# config_hash: {trial['config_hash']}" in text
    payload = yaml.safe_load(text)
    assert payload["direction_pct_threshold"] == (
        trial["config_patch"]["direction_pct_threshold"]
    )
    assert (workspace / "server_hpo_plan.json").exists()


def test_consistency_report_passes_for_complete_direction_candidate():
    report = build_consistency_report(
        research_id="res_consistency",
        iteration=2,
        model_type="direction",
        config_snapshot="agent_strategy: BALA\n",
        metrics_payload=_passing_metrics(),
        attempt_snapshot={"artifact_hash": "artifact-sha"},
    )

    assert report["passed"] is True
    assert report["blockers"] == []


def test_consistency_report_blocks_missing_inference_parity_for_candidate():
    metrics = _passing_metrics()
    metrics.pop("inference_parity")

    report = build_consistency_report(
        research_id="res_consistency",
        iteration=3,
        model_type="direction",
        config_snapshot="agent_strategy: BALA\n",
        metrics_payload=metrics,
        attempt_snapshot={"artifact_hash": "artifact-sha"},
    )

    assert report["passed"] is False
    assert "missing_inference_parity" in report["blockers"]


def test_consistency_report_warns_for_missing_artifact_on_non_candidate():
    report = build_consistency_report(
        research_id="res_consistency",
        iteration=1,
        model_type="direction",
        config_snapshot="agent_strategy: BALA\n",
        metrics_payload={"status": "failed"},
        attempt_snapshot={},
    )

    assert report["passed"] is True
    assert report["blockers"] == []
    artifact_check = next(
        check
        for check in report["checks"]
        if check["name"] == "artifact_reference_present"
    )
    assert artifact_check["status"] == "warning"


def test_research_state_summarizes_candidates_failures_and_budget():
    session = {
        "id": "res_state",
        "model_type": "direction",
        "status": "running",
        "max_budget_usd": 5.0,
        "total_api_cost_usd": 1.25,
        "max_iterations": 4,
    }
    report = build_consistency_report(
        research_id="res_state",
        iteration=1,
        model_type="direction",
        config_snapshot="agent_strategy: BALA\n",
        metrics_payload=_passing_metrics(),
        attempt_snapshot={"artifact_hash": "artifact-sha"},
    )
    iterations = [
        {
            "id": 1,
            "research_id": "res_state",
            "iteration": 1,
            "primary_metric": 0.62,
            "metric_name": "auc",
            "decision": "keep",
            "all_gates_passed": 1,
            "metrics_json": json.dumps(_passing_metrics()),
            "attempt_snapshot_json": json.dumps({"artifact_hash": "artifact-sha"}),
            "attempt_snapshot_hash": "attempt-sha",
            "consistency_report_json": json.dumps(report),
        },
        {
            "id": 2,
            "research_id": "res_state",
            "iteration": 2,
            "primary_metric": None,
            "metric_name": None,
            "decision": "discard",
            "all_gates_passed": 0,
            "metrics_json": json.dumps({"status": "timeout"}),
        },
        {
            "id": 3,
            "research_id": "res_state",
            "iteration": 3,
            "primary_metric": None,
            "metric_name": None,
            "decision": "discard",
            "all_gates_passed": 0,
            "canonical_config_hash": "config-sha",
            "trial_identity_hash": "identity-sha",
            "trial_identity_json": json.dumps(
                {
                    "seed": 42,
                    "validation_mode": "quick",
                    "data_split_id": "split-a",
                }
            ),
            "duplicate_of_research_id": "res_state",
            "duplicate_of_iteration": 1,
            "duplicate_reason": "same config already ran",
            "metrics_json": json.dumps({"status": "rejected_duplicate"}),
        },
    ]

    state = build_research_state(
        session=session,
        iterations=iterations,
        hpo_studies=[],
        promotions=[],
    )

    assert state["budget_usage"]["iterations_used"] == 2
    assert state["top_candidates"][0]["artifact_hash"] == "artifact-sha"
    assert state["failed_pruned_configs"][0]["status"] == "timeout"
    assert len(state["failed_pruned_configs"]) == 1
    assert state["duplicate_rejections"][0]["trial_identity_hash"] == "identity-sha"
    assert state["duplicate_rejections"][0]["duplicate_of"]["iteration"] == 1
    assert state["artifact_hashes"][0]["artifact_hash"] == "artifact-sha"


def test_research_state_exposes_planned_trials_and_manual_review():
    session = {
        "id": "res_state_plan",
        "model_type": "direction",
        "status": "running",
        "max_budget_usd": 5.0,
        "total_api_cost_usd": 0.0,
        "max_iterations": 4,
    }

    state = build_research_state(
        session=session,
        iterations=[],
        hpo_studies=[
            {
                "id": 1,
                "study_id": "hpo_res_state_plan_direction",
                "search_space_json": json.dumps(
                    {"direction_pct_threshold": [0.020, 0.025]}
                ),
                "budget_json": json.dumps({"max_iterations": 4}),
            }
        ],
        planned_trials=[
            {
                "trial_id": "trial_001",
                "trial_index": 1,
                "status": "planned",
                "config_patch_json": json.dumps(
                    {"direction_pct_threshold": 0.020}
                ),
                "config_hash": "hash-1",
            },
            {
                "trial_id": "manual_review_1",
                "trial_index": -1,
                "status": "manual_review",
                "config_patch_json": json.dumps({"proposed_command": "bad"}),
                "config_hash": "hash-2",
            },
        ],
        promotions=[],
    )

    assert state["planned_trials"][0]["config_patch"]["direction_pct_threshold"] == 0.020
    assert state["search_plan"]["planned_trial_count"] == 1
    assert state["search_plan"]["manual_review_count"] == 1
    assert state["search_plan"]["search_spaces"][0]["search_space"][
        "direction_pct_threshold"
    ] == [0.020, 0.025]
