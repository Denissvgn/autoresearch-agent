"""Gap 3 — auto-promotion skip diagnostics include collection errors.

Live evidence (``res_baf6605ce94f``, ``res_dd666f273f99``) shows that
``Auto-promotion skipped: reason=promotion_preview_blocked`` was logged
with high-level blocker codes only (``inference_adapter_load_failure``,
``inference_reload_failed``, etc.). The underlying error reason from
``PromotionEvidenceCollector`` (e.g. ``adapter_preflight_failed: ConnectTimeout``,
``reload_dry_run_status_502``) was already persisted in the iteration's
``promotion_evidence_collection_errors`` map but NOT surfaced to operators.

Gap 3 wires that map into the auto-promotion-skipped audit event, log line,
and broadcast payload so operators can distinguish infrastructure failures
(retry / fix downstream) from genuine validation failures.
"""
from __future__ import annotations

import json
import sys
import types
from typing import Any, Dict, List, Optional

try:  # pragma: no cover — defensive for environments without anthropic SDK
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

import pytest

from src.core import orchestrator as orchestrator_module
from src.core.orchestrator import AgentOrchestrator, ResearchConfig


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
    def __init__(self) -> None:
        self.audit_events: List[Dict[str, Any]] = []

    async def record_audit_event(self, **kwargs: Any) -> Dict[str, Any]:
        self.audit_events.append(kwargs)
        return kwargs


def _config() -> ResearchConfig:
    return ResearchConfig(
        id="res_diag",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="gap3-diagnostics",
        workspace_path="/tmp/autoresearch",
    )


def _orchestrator(store: FakeStore) -> AgentOrchestrator:
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch._store = store  # type: ignore[attr-defined]
    return orch


@pytest.fixture(autouse=True)
def _patch_broadcaster(monkeypatch: pytest.MonkeyPatch) -> FakeBroadcaster:
    fake = FakeBroadcaster()
    monkeypatch.setattr(orchestrator_module, "broadcaster", fake)
    return fake


@pytest.mark.asyncio
async def test_skip_without_errors_omits_collection_errors_key(
    _patch_broadcaster: FakeBroadcaster,
) -> None:
    """Backwards compatible: when no collection_errors are supplied, none
    of the three sinks (audit / log / broadcast) include the key.
    """
    store = FakeStore()
    orch = _orchestrator(store)
    agent_log = FakeAgentLog()

    await orch._emit_auto_promotion_skipped(
        research_id="res_diag",
        config=_config(),
        agent_log=agent_log,
        reason="promotion_preview_blocked",
        iteration=20,
        terminal_reason=None,
        incomplete_phases=[],
        promotion_allowed=False,
        blockers=["signal_saturation"],
    )

    # Audit event payload — no collection_errors entry
    assert len(store.audit_events) == 1
    metadata = store.audit_events[0]["request_metadata"]
    assert "collection_errors" not in metadata

    # Broadcast payload — no collection_errors entry
    assert len(_patch_broadcaster.events) == 1
    assert "collection_errors" not in _patch_broadcaster.events[0]

    # Agent log entry — plain message
    assert len(agent_log.entries) == 1
    assert agent_log.entries[0][1] == "Auto-promotion skipped: promotion_preview_blocked"


@pytest.mark.asyncio
async def test_skip_with_errors_surfaces_them_to_all_sinks(
    _patch_broadcaster: FakeBroadcaster,
) -> None:
    """Gap 3 path: when collection_errors are provided, they appear in
    audit metadata, broadcast payload, AND the agent_log message text.
    """
    store = FakeStore()
    orch = _orchestrator(store)
    agent_log = FakeAgentLog()
    errors = {
        "inference_preflight": "adapter_preflight_failed: ConnectTimeout",
        "inference_reload": "reload_dry_run_status_502",
        "smoke_validation": "smoke_validation_pipeline_not_configured",
    }

    await orch._emit_auto_promotion_skipped(
        research_id="res_diag",
        config=_config(),
        agent_log=agent_log,
        reason="promotion_preview_blocked",
        iteration=20,
        terminal_reason=None,
        incomplete_phases=[],
        promotion_allowed=False,
        blockers=[
            "inference_adapter_load_failure",
            "inference_reload_failed",
            "failed_smoke_validation",
        ],
        collection_errors=errors,
    )

    # Audit event payload — collection_errors keyed in
    assert len(store.audit_events) == 1
    metadata = store.audit_events[0]["request_metadata"]
    assert metadata["collection_errors"] == errors

    # Broadcast payload includes the errors
    assert len(_patch_broadcaster.events) == 1
    assert _patch_broadcaster.events[0]["collection_errors"] == errors

    # Agent log message text mentions the errors so the LLM and operator
    # see the underlying cause, not just the high-level blocker code
    assert len(agent_log.entries) == 1
    level, message = agent_log.entries[0]
    assert level == "system"
    assert "collection_errors" in message
    assert "adapter_preflight_failed" in message
    assert "reload_dry_run_status_502" in message


@pytest.mark.asyncio
async def test_skip_with_empty_errors_dict_treated_as_no_errors(
    _patch_broadcaster: FakeBroadcaster,
) -> None:
    """Defensive: an empty dict (no errors collected, but the kwarg was
    passed) should not surface a noisy ``collection_errors: {}`` to the
    operator. Behaves identically to the no-kwarg path.
    """
    store = FakeStore()
    orch = _orchestrator(store)
    agent_log = FakeAgentLog()

    await orch._emit_auto_promotion_skipped(
        research_id="res_diag",
        config=_config(),
        agent_log=agent_log,
        reason="promotion_preview_blocked",
        iteration=20,
        terminal_reason=None,
        incomplete_phases=[],
        promotion_allowed=False,
        blockers=["signal_saturation"],
        collection_errors={},
    )

    metadata = store.audit_events[0]["request_metadata"]
    assert "collection_errors" not in metadata
    assert "collection_errors" not in _patch_broadcaster.events[0]
    assert agent_log.entries[0][1] == "Auto-promotion skipped: promotion_preview_blocked"
