from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from src.core.observability import format_prometheus
from src.core.results_store import ResultsStore


async def _create_rl_session(store: ResultsStore, tmp_path: Path) -> None:
    await store.create_session(
        session_id="res_obs",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        tag="observability",
        quick_mode=True,
        max_iterations=3,
        max_budget_usd=25.0,
        focus_hint=None,
        workspace_path=str(tmp_path / "workspace"),
    )


@pytest.mark.asyncio
async def test_observability_snapshot_exports_prometheus_metrics(tmp_path: Path):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    await _create_rl_session(store, tmp_path)
    await store.update_session("res_obs", total_api_cost_usd=12.5)
    await store.record_planned_trials(
        research_id="res_obs",
        study_id="study_obs",
        trials=[
            {
                "trial_id": "trial_001",
                "trial_index": 1,
                "search_phase": "hpo_screening",
                "config_patch": {"agent_strategy": "BALA"},
                "config_hash": "config-sha",
                "expected_command": "run trial 001",
            }
        ],
    )
    await store.add_iteration(
        research_id="res_obs",
        iteration=1,
        primary_metric=0.42,
        metric_name="rl_profit_score",
        all_gates_passed=True,
        decision="keep",
        description="passing replay",
        config_snapshot="agent_strategy: BALA\n",
        metrics_json=json.dumps(
            {
                "status": "completed",
                "search_phase": "hpo_screening",
                "trial_id": "trial_001",
                "rl_economic_replay": {
                    "gates": {"all_gates_passed": True},
                    "artifact_hash": "replay-sha",
                },
            }
        ),
        training_time_s=42.0,
    )
    await store.create_pipeline(
        pipeline_id="pipe_obs",
        instrument="DOGE_USDT",
        timeframe="15m",
        tag="observability",
        max_iterations=9,
        max_budget_usd=30.0,
        quick_mode=True,
        timeout_s=3600,
        focus_hint=None,
        phase_budgets=None,
        trading_mode=None,
        agent_strategy=None,
        initial_balance=None,
        enable_hpo=True,
        hpo_trials=5,
        hpo_timesteps=50_000,
    )
    await store.update_pipeline(
        "pipe_obs",
        status="promotion_blocked",
        current_phase="rl",
        promotion_blockers_json=json.dumps(["missing_rl_economic_replay"]),
    )
    await store.record_audit_event(
        actor_id="autoresearch-agent",
        action="command.reject",
        outcome="failure",
        research_id="res_obs",
        pipeline_id="pipe_obs",
        request_metadata={"operation": "duplicate_attempt.reject", "phase": "rl"},
        error_message="duplicate attempt",
    )
    await store.record_audit_event(
        actor_id="operator",
        action="promotion.confirm",
        outcome="failure",
        research_id="res_obs",
        request_metadata={"scope": "production"},
        error_message="missing_rl_economic_replay",
    )

    snapshot = await store.collect_observability_metrics(active_sessions=2)
    text = format_prometheus(snapshot)

    assert snapshot["schema_version"] == "autoresearch_observability.v1"
    assert "python_info" in text
    assert "autoresearch_active_sessions 2" in text
    assert "autoresearch_api_cost_usd_total 12.5" in text
    assert (
        'autoresearch_planned_trials{search_phase="hpo_screening",status="planned"} 1'
        in text
    )
    assert (
        'autoresearch_attempts_total{model_type="rl",outcome="completed"} 1'
        in text
    )
    assert 'autoresearch_rl_replay_total{model_type="rl",status="passed"} 1' in text
    assert (
        'autoresearch_promotion_blocked_total{reason="missing_rl_economic_replay",'
        'scope="production"} 1'
    ) in text
    assert (
        'autoresearch_command_policy_rejections_total{operation="duplicate_attempt.reject"} 1'
        in text
    )
    assert any(
        alert["name"] == "AutoresearchBlockedProductionPromotions"
        for alert in snapshot["alert_suggestions"]
    )


@pytest.mark.asyncio
async def test_structured_logs_include_research_trace_context(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    await _create_rl_session(store, tmp_path)

    caplog.set_level(logging.INFO, logger="src.core.results_store")
    await store.add_iteration(
        research_id="res_obs",
        iteration=1,
        primary_metric=0.31,
        metric_name="rl_profit_score",
        all_gates_passed=True,
        decision="keep",
        description="trace context",
        config_snapshot="agent_strategy: BALA\n",
        metrics_json=json.dumps(
            {
                "status": "completed",
                "search_phase": "hpo_screening",
                "trial_id": "trial_trace",
            }
        ),
        training_time_s=7.0,
    )
    promotion = await store.record_promotion(
        research_id="res_obs",
        iteration=1,
        model_type="rl",
        instrument="DOGE_USDT",
        timeframe="15m",
        target_path=str(tmp_path / "rl.yaml"),
        config_yaml="agent_strategy: BALA\n",
        previous_yaml=None,
        scope="production",
        promotion_metadata={"promotion_allowed": True},
    )

    payloads = []
    for record in caplog.records:
        message = record.getMessage()
        if "autoresearch_event " not in message:
            continue
        payloads.append(json.loads(message.split("autoresearch_event ", 1)[1]))

    iteration_payload = next(
        payload for payload in payloads
        if payload["event"] == "iteration.recorded"
    )
    promotion_payload = next(
        payload for payload in payloads
        if payload["event"] == "promotion.recorded"
    )
    assert iteration_payload["research_id"] == "res_obs"
    assert iteration_payload["phase"] == "hpo_screening"
    assert iteration_payload["trial_id"] == "trial_trace"
    assert promotion_payload["promotion_id"] == promotion["id"]
    assert promotion_payload["research_id"] == "res_obs"

    promotion_record = next(
        record for record in caplog.records
        if getattr(record, "autoresearch_event", None) == "promotion.recorded"
    )
    assert promotion_record.research_id == "res_obs"
    assert promotion_record.promotion_id == promotion["id"]
