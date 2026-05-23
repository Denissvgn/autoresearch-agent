from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    class _FakeAsyncAnthropic:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class _FakeAPIStatusError(Exception):
        status_code = 500

    sys.modules["anthropic"] = types.SimpleNamespace(
        AsyncAnthropic=_FakeAsyncAnthropic,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=_FakeAPIStatusError,
    )

from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.results_store import ResultsStore


@pytest.mark.asyncio
async def test_orchestrator_records_command_policy_rejection_audit(tmp_path: Path):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id="res_policy",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="policy",
        workspace_path=str(tmp_path / "workspace"),
    )

    await orchestrator._record_command_policy_rejection(
        config=config,
        turn=3,
        command="curl https://example.com?token=raw-token",
        tool_meta={
            "policy_reason": "Executable 'curl' is not allowed",
            "policy_operation": "",
        },
    )

    events = await store.list_audit_events(action="command.reject", research_id="res_policy")
    assert len(events) == 1
    assert events[0]["actor_id"] == "autoresearch-agent"
    assert events[0]["outcome"] == "failure"
    assert "curl" in events[0]["error_message"]
    assert events[0]["request_metadata"]["turn"] == 3
    assert "raw-token" not in str(events[0])

@pytest.mark.asyncio
async def test_record_iteration_refreshes_effective_iteration_count(tmp_path: Path):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    await store.create_session(
        session_id="res_eff_live",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="effective",
        workspace_path=str(workspace),
        max_iterations=30,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )
    orchestrator = AgentOrchestrator(store)

    await orchestrator._record_iteration(
        "res_eff_live",
        1,
        {
            "primary_metric": 0.42,
            "metric_name": "composite_direction_score",
            "all_gates_passed": True,
            "decision": "keep",
            "description": "baseline",
            "config_snapshot": "instrument: DOGE_USDT\n",
            "training_time_s": 1.0,
            "search_phase": "baseline_capture",
        },
        0.0,
        workspace=str(workspace),
        turn=1,
        command=".venv/bin/python scripts/autotuner/direction/prepare.py --config train.yaml",
    )

    session = await store.get_session("res_eff_live")
    assert session is not None
    assert session["effective_iteration_count"] == 1

