from __future__ import annotations

import pytest

import src.core.orchestrator as orchestrator_module
from src.core.orchestrator import AgentOrchestrator
from src.core.results_store import ResultsStore


class FakeBroadcaster:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def broadcast(self, event: dict) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_refresh_phase_state_broadcasts_updated_state(tmp_path, monkeypatch):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    await store.create_session(
        session_id="res_phase_ws",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="phase-ws",
        quick_mode=True,
        max_iterations=3,
        max_budget_usd=10.0,
        focus_hint=None,
        workspace_path=str(tmp_path / "workspace"),
    )
    fake = FakeBroadcaster()
    monkeypatch.setattr(orchestrator_module, "broadcaster", fake)
    orchestrator = AgentOrchestrator.__new__(AgentOrchestrator)
    orchestrator._store = store

    await orchestrator._refresh_phase_state("res_phase_ws")

    assert fake.events
    event = fake.events[-1]
    assert event["event"] == "phase_state_updated"
    assert event["research_id"] == "res_phase_ws"
    assert event["phase_state"]["current_phase"] == "baseline_capture"
    assert event["current_phase"] == "baseline_capture"
