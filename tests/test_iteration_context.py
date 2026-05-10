from __future__ import annotations

import json

from src.core.iteration_context import (
    ITERATION_CONTEXT_DIGEST_MARKER,
    build_iteration_context_digest,
)


def test_iteration_context_digest_summarizes_best_recent_blockers_and_duplicates():
    session = {
        "id": "res_context",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": "direction",
        "max_iterations": 10,
        "max_budget_usd": 2.0,
        "total_api_cost_usd": 0.25,
    }
    iterations = [
        {
            "iteration": 1,
            "primary_metric": 0.52,
            "metric_name": "score",
            "all_gates_passed": 0,
            "decision": "discard",
            "description": "baseline failed calibration",
            "metrics_json": json.dumps({"gate_failures": ["auc_low"]}),
        },
        {
            "iteration": 2,
            "primary_metric": 0.64,
            "metric_name": "score",
            "all_gates_passed": 1,
            "decision": "keep",
            "description": "wider dead-zone improved score",
            "trial_identity_hash": "identity-2",
        },
        {
            "iteration": 3,
            "primary_metric": None,
            "metric_name": None,
            "all_gates_passed": 0,
            "decision": "discard",
            "duplicate_reason": "same config already ran",
            "duplicate_of_research_id": "res_context",
            "duplicate_of_iteration": 2,
            "consistency_report_json": json.dumps(
                {"passed": False, "blockers": ["missing_inference_parity"]}
            ),
            "metrics_json": json.dumps({"status": "rejected_duplicate"}),
        },
    ]

    digest = build_iteration_context_digest(
        session=session,
        iterations=iterations,
        planned_trials=[{"status": "completed"}, {"status": "planned"}],
        hpo_studies=[{"study_id": "hpo_res_context", "status": "planned", "completed_trials": 1, "max_trials": 3}],
    )

    assert ITERATION_CONTEXT_DIGEST_MARKER in digest
    assert "Best so far: iteration 2 score=0.6400" in digest
    assert "#3" in digest
    assert "missing_inference_parity" in digest
    assert "same config already ran" in digest
    assert "trials completed=1, planned=1" in digest


def test_iteration_context_digest_respects_cap():
    session = {"id": "res_cap", "model_type": "direction"}
    iterations = [
        {
            "iteration": index,
            "primary_metric": 0.5 + index / 100,
            "metric_name": "score",
            "all_gates_passed": index % 2 == 0,
            "decision": "keep",
            "description": "x" * 300,
        }
        for index in range(1, 20)
    ]

    digest = build_iteration_context_digest(
        session=session,
        iterations=iterations,
        max_chars=600,
        recent_attempts=10,
    )

    assert len(digest) <= 600
    assert digest.endswith("[truncated]")


def test_iteration_context_digest_handles_empty_iterations():
    digest = build_iteration_context_digest(
        session={"id": "res_empty", "model_type": "direction"},
        iterations=[],
    )

    assert "Best so far: none yet" in digest
    assert "none recorded yet" in digest
