from __future__ import annotations

import json

from server.core.consistency_validator import build_consistency_report
from server.core.research_phase_plan import build_phase_state
from server.core.research_state import build_research_state
from server.core.structured_hpo import build_structured_hpo_plan


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


def test_structured_direction_hpo_plan_is_bounded_by_iterations():
    plan = build_structured_hpo_plan(
        research_id="res_hpo",
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
    assert "deadzone_width" in plan["search_space"]
    assert plan["budget"]["max_budget_usd"] == 2.0


def test_structured_hpo_plan_never_inflates_requested_trials():
    direction_plan = build_structured_hpo_plan(
        research_id="res_hpo_small",
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
    assert rl_plan["max_trials"] == 1


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
    assert state["artifact_hashes"][0]["artifact_hash"] == "artifact-sha"
