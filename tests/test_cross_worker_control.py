"""ARC-011 implementation review C5 (2026-08-15) — cross-worker control at
the SessionManager entry point (P6-004 / H3).

The review found ``stop_session`` / ``pause_session`` / ``resume_session`` /
``stop_pipeline`` all began with an ``_active``-registry early return BEFORE
writing any DB intent. Under ``WEB_CONCURRENCY > 1`` with a non-sticky load
balancer, a control request routed to a worker that does not own the session
returned False and wrote nothing — the owning worker's DB-side polls (the H3
machinery) never fired, contradicting ADR §6.2's own design ("worker B writes
the transition"). The fencing tests bypassed ``SessionManager`` entirely, so
the gap was untested.

These tests pin the fixed contract: DB intent is recorded regardless of
local ownership; local ownership only adds the fast path (in-process flag +
task drain). Plus the orchestrator-side pause observation (``_wait_while_paused``
now reads the authoritative DB status — a DB-side ``paused`` is observed by a
non-paused owner, and a cross-worker resume unsticks a locally-paused owner).
"""
from __future__ import annotations

import asyncio
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    sys.modules["anthropic"] = types.SimpleNamespace(
        AsyncAnthropic=MagicMock(return_value=MagicMock()),
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

import src.core.session_manager as session_manager_module
from src.core.orchestrator import AgentOrchestrator
from src.core.results_store import ResultsStore
from src.core.session_manager import ActiveSession, SessionManager
from src.core.state_machine import IllegalTransitionError, SessionEvent


class ControlFakeOrchestrator:
    """Records control requests; never actually runs anything."""

    def __init__(self) -> None:
        self.stops: List[str] = []
        self.pauses: List[str] = []
        self.resumes: List[str] = []

    def request_stop(self, research_id: str) -> None:
        self.stops.append(research_id)

    def request_pause(self, research_id: str) -> None:
        self.pauses.append(research_id)

    def request_resume(self, research_id: str) -> None:
        self.resumes.append(research_id)

    async def run(self, config: Any) -> None:  # pragma: no cover — unused
        await asyncio.sleep(0)



async def _seed_running_session(store: ResultsStore, research_id: str) -> None:
    await store.create_session(
        session_id=research_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="c5",
        quick_mode=False,
        max_iterations=5,
        max_budget_usd=5.0,
        focus_hint=None,
        workspace_path="/tmp/c5",
    )


def _manager_with_fake_orchestrator(
    monkeypatch: pytest.MonkeyPatch, store: ResultsStore,
) -> tuple[SessionManager, ControlFakeOrchestrator]:
    fake_orch = ControlFakeOrchestrator()
    monkeypatch.setattr(
        session_manager_module, "AgentOrchestrator",
        lambda store, state_machine=None: fake_orch,
    )
    manager = SessionManager(store)
    # The session-manager flow under test never awaits the run task here.
    return manager, fake_orch


# ============================================================================
# stop/pause/resume on a NON-owning worker — DB intent is recorded
# ============================================================================


@pytest.mark.asyncio
async def test_stop_on_non_owning_worker_records_db_intent(monkeypatch, tmp_path):
    """The C5 headline: worker B (empty ``_active``) stops a session owned by
    worker A — the ``stopping`` intent must land in the shared DB so A's
    ``_should_stop_cross_worker`` poll observes it (previously: silent
    no-op, H3 unreachable)."""
    store = ResultsStore(str(tmp_path / "c5.sqlite"))
    await store.initialize()
    await _seed_running_session(store, "res_c5_stop01")
    manager, fake_orch = _manager_with_fake_orchestrator(monkeypatch, store)

    assert manager.is_running("res_c5_stop01") is False  # non-owning worker
    assert await manager.stop_session("res_c5_stop01") is True

    session = await store.get_session("res_c5_stop01")
    assert session["status"] == "stopping"
    # Non-owner: no in-process flag request was made (the owner finalizes).
    assert fake_orch.stops == []

    # …and the owning worker's poll now sees it (the H3 loop, closed).
    orch = AgentOrchestrator(store)  # type: ignore[arg-type]
    assert await orch._should_stop_cross_worker("res_c5_stop01") is True  # noqa: SLF001


@pytest.mark.asyncio
async def test_stop_unknown_session_returns_false(monkeypatch, tmp_path):
    store = ResultsStore(str(tmp_path / "c5.sqlite"))
    await store.initialize()
    manager, _ = _manager_with_fake_orchestrator(monkeypatch, store)
    assert await manager.stop_session("res_no_such") is False


@pytest.mark.asyncio
async def test_stop_terminal_session_is_idempotent_no_op(monkeypatch, tmp_path):
    store = ResultsStore(str(tmp_path / "c5.sqlite"))
    await store.initialize()
    await _seed_running_session(store, "res_c5_term01")
    manager, _ = _manager_with_fake_orchestrator(monkeypatch, store)
    # Drive to terminal via the state machine.
    await manager._sm.transition("res_c5_term01", SessionEvent.COMPLETE)  # noqa: SLF001

    assert await manager.stop_session("res_c5_term01") is False
    session = await store.get_session("res_c5_term01")
    assert session["status"] == "completed"  # not clobbered


@pytest.mark.asyncio
async def test_pause_and_resume_on_non_owning_worker(monkeypatch, tmp_path):
    store = ResultsStore(str(tmp_path / "c5.sqlite"))
    await store.initialize()
    await _seed_running_session(store, "res_c5_pause1")
    manager, fake_orch = _manager_with_fake_orchestrator(monkeypatch, store)

    assert await manager.pause_session("res_c5_pause1") is True
    session = await store.get_session("res_c5_pause1")
    assert session["status"] == "paused"
    assert fake_orch.pauses == []  # non-owner: no local flag

    assert await manager.resume_session("res_c5_pause1") is True
    session = await store.get_session("res_c5_pause1")
    assert session["status"] == "running"
    assert fake_orch.resumes == []

    # Pause against a winding-down session is still refused (sibling-of-W8).
    assert await manager.stop_session("res_c5_pause1") is True  # → stopping
    assert await manager.pause_session("res_c5_pause1") is False


@pytest.mark.asyncio
async def test_local_owner_fast_path_unchanged(monkeypatch, tmp_path):
    """Owning worker: the DB intent is still written AND the in-process flag
    + task drain run (the pre-C5 fast path — no poll latency)."""
    store = ResultsStore(str(tmp_path / "c5.sqlite"))
    await store.initialize()
    await _seed_running_session(store, "res_c5_own001")
    manager, fake_orch = _manager_with_fake_orchestrator(monkeypatch, store)

    task = asyncio.get_running_loop().create_task(asyncio.sleep(0.05))
    manager._active["res_c5_own001"] = ActiveSession(  # noqa: SLF001
        research_id="res_c5_own001",
        task=task,
        config=MagicMock(),
        started_at=datetime.now(timezone.utc),
    )
    assert await manager.stop_session("res_c5_own001") is True
    assert fake_orch.stops == ["res_c5_own001"]
    session = await store.get_session("res_c5_own001")
    assert session["status"] == "stopping"
    # The drain ran without error (the entry itself is popped by the run
    # task's own finally in production — a bare sleep task has none).


# ============================================================================
# Orchestrator-side pause observation (the other half of cross-worker pause)
# ============================================================================


@pytest.mark.asyncio
async def test_wait_while_paused_observes_db_side_pause(tmp_path):
    """A non-paused owner (local flag clear) must still wait while the shared
    DB says ``paused`` — previously only the local flag was consulted, so a
    cross-worker pause was invisible."""
    store = ResultsStore(str(tmp_path / "c5.sqlite"))
    await store.initialize()
    await _seed_running_session(store, "res_c5_wait01")
    orch = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orch._sm.transition("res_c5_wait01", SessionEvent.PAUSE)  # noqa: SLF001

    waiting = asyncio.get_running_loop().create_task(
        orch._wait_while_paused("res_c5_wait01"),  # noqa: SLF001
    )
    await asyncio.sleep(0.2)  # a poll interval passes
    assert not waiting.done(), "must keep waiting while the DB says paused"

    await orch._sm.transition("res_c5_wait01", SessionEvent.RESUME)  # noqa: SLF001
    await asyncio.wait_for(waiting, timeout=10)
    # The epoch was refreshed after the observed pause/resume (P6-004).
    assert "res_c5_wait01" in orch._session_epochs  # noqa: SLF001


@pytest.mark.asyncio
async def test_wait_while_paused_honors_cross_worker_resume(tmp_path):
    """A locally-paused owner (flag set) unsticks when the DB says ``running``
    — a resume recorded by another worker is authoritative."""
    store = ResultsStore(str(tmp_path / "c5.sqlite"))
    await store.initialize()
    await _seed_running_session(store, "res_c5_wait02")
    orch = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orch._sm.transition("res_c5_wait02", SessionEvent.PAUSE)  # noqa: SLF001
    orch._pause_flags["res_c5_wait02"] = True  # local pause, DB still paused  # noqa: SLF001

    # Cross-worker resume: DB → running, local flag NOT cleared by us.
    await orch._sm.transition("res_c5_wait02", SessionEvent.RESUME)  # noqa: SLF001

    await asyncio.wait_for(
        orch._wait_while_paused("res_c5_wait02"), timeout=10,  # noqa: SLF001
    )  # returns promptly — no stuck-forever local flag


# ============================================================================
# Pipeline cross-worker stop (ADR §6.2 lists pipelines for the same fix)
# ============================================================================


async def _seed_running_pipeline(store: ResultsStore, pipeline_id: str) -> None:
    await store.create_pipeline(
        pipeline_id=pipeline_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        tag="c5",
        max_iterations=5,
        max_budget_usd=5.0,
        quick_mode=False,
        timeout_s=600,
        focus_hint=None,
        phase_budgets=None,
        trading_mode=None,
        agent_strategy=None,
        initial_balance=None,
        enable_hpo=False,
        hpo_trials=20,
        hpo_timesteps=50000,
    )


