from __future__ import annotations

import json
import sys
import types
from typing import Any, Dict, List, Optional

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
    sys.modules["anthropic"] = _stub

from src.core import config_promoter
from src.core import orchestrator as orchestrator_module
from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.research_phase_plan import phases_for_model


class FakeAgentLog:
    def __init__(self) -> None:
        self.entries: List[tuple[str, str]] = []

    async def append(self, level: str, message: str) -> None:
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
    ) -> None:
        self.session = {
            "id": "res_auto",
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "model_type": "direction",
            "workspace_path": "/tmp/autoresearch",
            "best_iteration": 4,
            "terminal_reason": terminal_reason,
            "phase_state_json": json.dumps(phase_state),
        }
        self.iterations = [
            {
                "iteration": 4,
                "all_gates_passed": True,
                "decision": "keep",
                "primary_metric": 0.635563,
                "metrics_json": "{}",
            }
        ]
        self.audit_events: List[Dict[str, Any]] = []

    async def get_session(self, research_id: str) -> Dict[str, Any]:
        assert research_id == "res_auto"
        return dict(self.session)

    async def get_iterations(self, research_id: str) -> List[Dict[str, Any]]:
        assert research_id == "res_auto"
        return [dict(row) for row in self.iterations]

    async def get_hpo_studies(self, research_id: str) -> List[Dict[str, Any]]:
        assert research_id == "res_auto"
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
        tag="auto-promotion-readiness",
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


def _complete_until_promotion_state() -> Dict[str, Any]:
    statuses = {
        phase["id"]: "completed"
        for phase in phases_for_model("direction")
    }
    statuses["promotion_proposal"] = "pending"
    return _phase_state(statuses)


def _incomplete_adaptive_state() -> Dict[str, Any]:
    return _phase_state({
        "baseline_capture": "completed",
        "tabular_sweeps": "completed",
        "adaptive_feature_sweeps": "in_progress",
    })


def _install_promoter(
    monkeypatch: pytest.MonkeyPatch,
    *,
    preview_payload: Optional[Dict[str, Any]] = None,
    preview_exc: Optional[Exception] = None,
) -> Dict[str, List[str]]:
    calls: Dict[str, List[str]] = {"preview": [], "confirm": []}

    class FakePromoter:
        def __init__(self, store: Any) -> None:
            self.store = store

        async def preview(self, research_id: str) -> Dict[str, Any]:
            calls["preview"].append(research_id)
            if preview_exc is not None:
                raise preview_exc
            return dict(preview_payload or {})

        async def confirm(self, research_id: str) -> Dict[str, Any]:
            calls["confirm"].append(research_id)
            return {"status": "promoted", "research_id": research_id}

    monkeypatch.setattr(config_promoter, "ConfigPromoter", FakePromoter)
    return calls


def _install_broadcaster(
    monkeypatch: pytest.MonkeyPatch,
) -> FakeBroadcaster:
    fake = FakeBroadcaster()
    monkeypatch.setattr(orchestrator_module, "broadcaster", fake)
    return fake


@pytest.mark.asyncio
async def test_auto_promote_skips_when_pre_promotion_phases_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(
        phase_state=_incomplete_adaptive_state(),
        terminal_reason="agent_self_terminated_during_phase:adaptive_feature_sweeps",
    )
    calls = _install_promoter(
        monkeypatch,
        preview_payload={"promotion_allowed": True},
    )
    broadcaster = _install_broadcaster(monkeypatch)
    agent_log = FakeAgentLog()

    orchestrator = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orchestrator._try_auto_promote("res_auto", _config(), agent_log)  # noqa: SLF001

    assert calls["preview"] == []
    assert calls["confirm"] == []
    assert store.audit_events[-1]["action"] == "promotion.auto_skip"
    metadata = store.audit_events[-1]["request_metadata"]
    assert metadata["reason"] == "incomplete_research_phases"
    assert "adaptive_feature_sweeps" in metadata["incomplete_phases"]
    assert broadcaster.events[-1]["event"] == "auto_promotion_skipped"
    assert broadcaster.events[-1]["reason"] == "incomplete_research_phases"
    assert agent_log.entries[-1] == (
        "system",
        "Auto-promotion skipped: incomplete_research_phases",
    )


@pytest.mark.asyncio
async def test_auto_promote_uses_preview_before_confirm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(phase_state=_complete_until_promotion_state())
    calls = _install_promoter(
        monkeypatch,
        preview_payload={
            "promotion_allowed": False,
            "gate_bundle_evaluation": {"blockers": ["weak_calibration"]},
            "consistency_report": {
                "blockers": ["inference_feature_schema_mismatch"]
            },
        },
    )
    broadcaster = _install_broadcaster(monkeypatch)
    agent_log = FakeAgentLog()

    orchestrator = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orchestrator._try_auto_promote("res_auto", _config(), agent_log)  # noqa: SLF001

    assert calls["preview"] == ["res_auto"]
    assert calls["confirm"] == []
    event = broadcaster.events[-1]
    assert event["reason"] == "promotion_preview_blocked"
    assert event["blockers"] == [
        "weak_calibration",
        "inference_feature_schema_mismatch",
    ]
    assert store.audit_events[-1]["request_metadata"]["blockers"] == event["blockers"]


@pytest.mark.asyncio
async def test_auto_promote_reports_quality_baseline_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(phase_state=_complete_until_promotion_state())
    calls = _install_promoter(
        monkeypatch,
        preview_payload={
            "promotion_allowed": False,
            "quality_baseline_evaluation": {
                "blockers": ["best_metric_below_development_baseline"]
            },
        },
    )
    broadcaster = _install_broadcaster(monkeypatch)
    agent_log = FakeAgentLog()

    orchestrator = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orchestrator._try_auto_promote("res_auto", _config(), agent_log)  # noqa: SLF001

    assert calls["preview"] == ["res_auto"]
    assert calls["confirm"] == []
    event = broadcaster.events[-1]
    assert event["reason"] == "promotion_preview_blocked"
    assert event["blockers"] == ["best_metric_below_development_baseline"]
    assert store.audit_events[-1]["request_metadata"]["blockers"] == event["blockers"]


@pytest.mark.asyncio
async def test_auto_promote_uses_training_gate_alias_before_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(phase_state=_complete_until_promotion_state())
    store.iterations[0]["all_gates_passed"] = True
    store.iterations[0]["metrics_json"] = json.dumps(
        {"training_gates_passed": False, "all_gates_passed": True}
    )
    calls = _install_promoter(
        monkeypatch,
        preview_payload={"promotion_allowed": True},
    )
    _install_broadcaster(monkeypatch)
    agent_log = FakeAgentLog()

    orchestrator = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orchestrator._try_auto_promote("res_auto", _config(), agent_log)  # noqa: SLF001

    assert calls["preview"] == []
    assert calls["confirm"] == []
    assert store.audit_events == []
    assert agent_log.entries == []


@pytest.mark.asyncio
async def test_auto_promote_confirms_only_when_preview_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(phase_state=_complete_until_promotion_state())
    calls = _install_promoter(
        monkeypatch,
        preview_payload={"promotion_allowed": True},
    )
    broadcaster = _install_broadcaster(monkeypatch)
    agent_log = FakeAgentLog()

    orchestrator = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orchestrator._try_auto_promote("res_auto", _config(), agent_log)  # noqa: SLF001

    assert calls["preview"] == ["res_auto"]
    assert calls["confirm"] == ["res_auto"]
    assert store.audit_events == []
    assert broadcaster.events[-1]["event"] == "auto_promoted"
    assert broadcaster.events[-1]["iteration"] == 4
    assert agent_log.entries[-1] == (
        "system",
        "Auto-promoted best iteration 4 to development config",
    )


@pytest.mark.asyncio
async def test_auto_promote_treats_preview_value_error_as_skip(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = FakeStore(phase_state=_complete_until_promotion_state())
    calls = _install_promoter(
        monkeypatch,
        preview_exc=ValueError("Iteration has no stored config snapshot"),
    )
    broadcaster = _install_broadcaster(monkeypatch)
    agent_log = FakeAgentLog()

    orchestrator = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orchestrator._try_auto_promote("res_auto", _config(), agent_log)  # noqa: SLF001

    assert calls["preview"] == ["res_auto"]
    assert calls["confirm"] == []
    event = broadcaster.events[-1]
    assert event["reason"] == "promotion_preview_failed"
    assert event["blockers"] == ["Iteration has no stored config snapshot"]
    assert agent_log.entries[-1] == (
        "system",
        "Auto-promotion skipped: promotion_preview_failed",
    )
    assert "Auto-promotion failed" not in caplog.text
