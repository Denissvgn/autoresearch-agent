"""Tests for the TERMINATE_REQUEST promotion waiver.

When the agent emits an explicit `TERMINATE_REQUEST:` line, the orchestrator
sets `terminate_request_received=True` on the session. `_try_auto_promote`
treats that as a "the agent concluded baseline is best" signal and waives
incomplete iteration-count phases for promotion — hard gates (training,
calibration, parity) still run via `promoter.preview()`.

Silent end_turn / crash / timeout sessions do NOT get this waiver and still
block promotion when phases are incomplete.
"""
from __future__ import annotations

import json
import sys
import types
from types import ModuleType
from typing import Any, Dict, List, Optional, cast

import pytest

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    _stub = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = cast(ModuleType, _stub)
from src.core import config_promoter
from src.core import orchestrator as orchestrator_module
from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.research_phase_plan import phases_for_model


class FakeAgentLog:
    def __init__(self) -> None:
        self.entries: List[tuple[str, str]] = []

    async def append(self, level: str, message: str, **_: Any) -> None:
        self.entries.append((level, message))


class FakeBroadcaster:
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        self.events.append(payload)


class FakeStore:
    def __init__(
        self,
        *,
        phase_state: Dict[str, Any],
        terminal_reason: Optional[str] = None,
        terminate_request_received: bool = False,
    ) -> None:
        self.session = {
            "id": "res_auto",
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "model_type": "direction",
            "workspace_path": "/tmp/autoresearch",
            "best_iteration": 4,
            "terminal_reason": terminal_reason,
            "terminate_request_received": 1 if terminate_request_received else 0,
            "phase_state_json": json.dumps(phase_state),
        }
        self.iterations = [
            {
                "iteration": 4,
                "all_gates_passed": True,
                "decision": "keep",
                "primary_metric": 0.6355,
                "metrics_json": "{}",
            }
        ]
        self.audit_events: List[Dict[str, Any]] = []

    async def get_session(self, research_id: str) -> Dict[str, Any]:
        return dict(self.session)

    async def get_iterations(self, research_id: str) -> List[Dict[str, Any]]:
        return [dict(row) for row in self.iterations]

    async def get_hpo_studies(self, research_id: str) -> List[Dict[str, Any]]:
        return []

    async def list_promotions(self) -> List[Dict[str, Any]]:
        return []

    async def record_audit_event(self, **kwargs: Any) -> Dict[str, Any]:
        self.audit_events.append(kwargs)
        return kwargs


def _config() -> ResearchConfig:
    return ResearchConfig(
        id="res_auto",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="terminate-waiver",
        workspace_path="/tmp/autoresearch",
    )


def _phase_state(status_by_phase: Dict[str, str]) -> Dict[str, Any]:
    phases = []
    current_phase = "promotion_proposal"
    for phase in phases_for_model("direction"):
        status = status_by_phase.get(phase["id"], "pending")
        phases.append({**phase, "status": status})
        if status in {"in_progress", "blocked"}:
            current_phase = phase["id"]
    return {
        "schema_version": "autoresearch_phase_state.v1",
        "research_id": "res_auto",
        "model_type": "direction",
        "current_phase": current_phase,
        "next_action": "test",
        "blocked": False,
        "block_reason": None,
        "phases": phases,
    }


def _baseline_complete_tabular_incomplete() -> Dict[str, Any]:
    """Baseline done, agent gave up after exploring 5 tabular sweeps (needs 6+)."""
    return _phase_state({
        "baseline_capture": "completed",
        "tabular_sweeps": "in_progress",
    })


def _baseline_incomplete() -> Dict[str, Any]:
    """Crash mid-baseline — nothing legitimately validated."""
    return _phase_state({
        "baseline_capture": "in_progress",
    })


def _install_promoter(
    monkeypatch: pytest.MonkeyPatch,
    *,
    preview_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[str]]:
    calls: Dict[str, List[str]] = {"preview": [], "confirm": []}

    class FakePromoter:
        def __init__(self, store: Any) -> None:
            self.store = store

        async def preview(self, research_id: str) -> Dict[str, Any]:
            calls["preview"].append(research_id)
            return dict(preview_payload or {})

        async def confirm(self, research_id: str) -> Dict[str, Any]:
            calls["confirm"].append(research_id)
            return {"status": "promoted", "research_id": research_id}

    monkeypatch.setattr(config_promoter, "ConfigPromoter", FakePromoter)
    return calls


def _install_broadcaster(monkeypatch: pytest.MonkeyPatch) -> FakeBroadcaster:
    fake = FakeBroadcaster()
    monkeypatch.setattr(orchestrator_module, "broadcaster", fake)
    return fake


@pytest.mark.asyncio
async def test_terminate_request_waives_incomplete_phases_with_baseline_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent explicitly TERMINATE_REQUESTed; baseline complete; tabular_sweeps short."""
    store = FakeStore(
        phase_state=_baseline_complete_tabular_incomplete(),
        terminal_reason="agent_self_terminated_during_phase:tabular_sweeps",
        terminate_request_received=True,
    )
    calls = _install_promoter(
        monkeypatch,
        preview_payload={"promotion_allowed": True},
    )
    _install_broadcaster(monkeypatch)
    agent_log = FakeAgentLog()

    orchestrator = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orchestrator._try_auto_promote("res_auto", _config(), agent_log)  # noqa: SLF001

    assert calls["preview"] == ["res_auto"], (
        "preview should run despite tabular_sweeps being incomplete"
    )
    waiver_logs = [
        entry for entry in agent_log.entries
        if "waived by TERMINATE_REQUEST" in entry[1]
    ]
    assert waiver_logs, f"waiver log entry missing; got: {agent_log.entries}"


@pytest.mark.asyncio
async def test_terminate_request_still_blocks_when_baseline_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TERMINATE_REQUEST without baseline_capture complete should NOT waive."""
    store = FakeStore(
        phase_state=_baseline_incomplete(),
        terminal_reason="agent_self_terminated_during_phase:baseline_capture",
        terminate_request_received=True,
    )
    calls = _install_promoter(monkeypatch, preview_payload={"promotion_allowed": True})
    _install_broadcaster(monkeypatch)
    agent_log = FakeAgentLog()

    orchestrator = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orchestrator._try_auto_promote("res_auto", _config(), agent_log)  # noqa: SLF001

    assert calls["preview"] == [], (
        "preview should NOT run when baseline is incomplete, regardless of waiver flag"
    )
    assert store.audit_events[-1]["request_metadata"]["reason"] == "incomplete_research_phases"


@pytest.mark.asyncio
async def test_silent_end_turn_still_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without explicit TERMINATE_REQUEST, incomplete phases block (existing behavior)."""
    store = FakeStore(
        phase_state=_baseline_complete_tabular_incomplete(),
        terminal_reason="agent_self_terminated_during_phase:tabular_sweeps",
        terminate_request_received=False,
    )
    calls = _install_promoter(monkeypatch, preview_payload={"promotion_allowed": True})
    _install_broadcaster(monkeypatch)
    agent_log = FakeAgentLog()

    orchestrator = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orchestrator._try_auto_promote("res_auto", _config(), agent_log)  # noqa: SLF001

    assert calls["preview"] == [], (
        "preview should NOT run without explicit TERMINATE_REQUEST"
    )
    assert store.audit_events[-1]["request_metadata"]["reason"] == "incomplete_research_phases"