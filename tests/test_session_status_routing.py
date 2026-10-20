
"""Routing tests for ARC-011 P0-003 / P0-004.

Verifies that ``SessionManager`` and the orchestrator exit path now drive
session-status changes *through* ``SessionStateMachine.transition`` (the sole
legal writer) and that the W8 contract holds at the routing layer:

  * pause / resume return ``False`` (not raise) against a winding-down or
    terminal session — the pause sibling-of-W8 (ARC-011 §5).
  * ``stop_session`` records the transitional ``stopping`` intent under the
    per-session lock; the orchestrator owns the ``stopping → stopped``
    finalize.
  * a racing ``complete`` against an in-flight stop is refused and the session
    resolves to ``stopped`` with no auto-promote (W8-A).
  * a late stop against terminal ``completed`` is a no-op — it can neither
    overwrite the status nor revoke a promotion (W8-B).

The exhaustive transition table + concurrency stress is P0-005's job
(``tests/test_state_machine.py``); these tests pin the *routing*.
"""

from __future__ import annotations

import asyncio
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import cast
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    class _FakeAsyncAnthropic:
        def __init__(self, *args, **kwargs) -> None:
            pass

    sys.modules["anthropic"] = cast(ModuleType, types.SimpleNamespace(
        AsyncAnthropic=_FakeAsyncAnthropic,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("_FakeAPIStatusError", (Exception,), {"status_code": 500}),
    ))

from src.core.results_store import ResultsStore
from src.core.session_manager import ActiveSession, SessionManager
from src.core.state_machine import IllegalTransitionError, SessionEvent


async def _init_store(tmp_path: Path) -> ResultsStore:
    store = ResultsStore(str(tmp_path / "routing.sqlite"))
    await store.initialize()
    return store


async def _seed_running(store: ResultsStore, session_id: str) -> str:
    await store.create_session(
        session_id=session_id,
        instrument="DOGE_UST",
        timeframe="15m",
        model_type="direction",
        tag=session_id,
        quick_mode=True,
        max_iterations=3,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path="/ws",
    )
    return session_id


async def _done_task() -> None:
    return None


async def _inject_active(manager: SessionManager, research_id: str) -> None:
    """Insert a completed task into ``_active`` so the guard checks pass."""
    task = asyncio.create_task(_done_task())
    await asyncio.sleep(0)  # let the scheduler run the task to completion
    manager._active[research_id] = ActiveSession(
        research_id=research_id,
        task=task,
        config=MagicMock(),  # noqa: TID252 — not exercised by pause/resume/stop
        started_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# pause / resume routing + illegal-state handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_resume_route_through_state_machine(tmp_path: Path) -> None:
    store = await _init_store(tmp_path)
    manager = SessionManager(store)
    rid = await _seed_running(store, "res-pause")
    await _inject_active(manager, rid)

    assert await manager.pause_session(rid) is True
    assert (await store.get_session(rid))["status"] == "paused"

    assert await manager.resume_session(rid) is True
    assert (await store.get_session(rid))["status"] == "running"



@pytest.mark.asyncio
async def test_pause_returns_false_when_session_is_winding_down(
    tmp_path: Path,
) -> None:
    store = await _init_store(tmp_path)
    manager = SessionManager(store)
    rid = await _seed_running(store, "res-stop-pause")
    # An operator stop already recorded its intent — the session is `stopping`.
    await manager._sm.transition(rid, SessionEvent.STOP_REQUESTED)
    assert (await store.get_session(rid))["status"] == "stopping"
    await _inject_active(manager, rid)

    # pause must NOT clobber an in-flight terminal (the pause sibling-of-W8).
    assert await manager.pause_session(rid) is False
    # Status is unchanged — the illegal transition wrote nothing.
    assert (await store.get_session(rid))["status"] == "stopping"



@pytest.mark.asyncio
async def test_resume_returns_false_when_not_paused(tmp_path: Path) -> None:
    store = await _init_store(tmp_path)
    manager = SessionManager(store)
    rid = await _seed_running(store, "res-resume-running")
    await _inject_active(manager, rid)

    # (running, resume) is illegal — a running session cannot resume.
    assert await manager.resume_session(rid) is False
    assert (await store.get_session(rid))["status"] == "running"



# ---------------------------------------------------------------------------
# stop_session routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_session_records_stopping_intent(tmp_path: Path) -> None:
    store = await _init_store(tmp_path)
    manager = SessionManager(store)
    rid = await _seed_running(store, "res-stop")
    await _inject_active(manager, rid)

    assert await manager.stop_session(rid) is True
    # stop_session records the transitional intent and returns; the
    # orchestrator exit path owns the `stopping → stopped` finalize.
    assert (await store.get_session(rid))["status"] == "stopping"



@pytest.mark.asyncio
async def test_stop_session_refused_when_higher_severity_in_flight(
    tmp_path: Path,
) -> None:
    store = await _init_store(tmp_path)
    manager = SessionManager(store)
    rid = await _seed_running(store, "res-stop-after-fail")
    # A failure is already in flight (severity 4 > stop's 2) — stop must defer.
    await manager._sm.transition(rid, SessionEvent.FAIL)
    assert (await store.get_session(rid))["status"] == "failed"
    await _inject_active(manager, rid)

    assert await manager.stop_session(rid) is False
    # The failed terminal is untouched.
    assert (await store.get_session(rid))["status"] == "failed"



# ---------------------------------------------------------------------------
# W8 contract — the routing layer relies on these machine guarantees
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_w8_racing_complete_against_stop_is_refused_no_promote(
    tmp_path: Path,
) -> None:
    """Interleaving A: stop already recorded intent → complete refused."""
    store = await _init_store(tmp_path)
    manager = SessionManager(store)
    rid = await _seed_running(store, "res-w8a")
    sm = manager._sm

    # Operator stop records intent first (as stop_session now does).
    await sm.transition(rid, SessionEvent.STOP_REQUESTED)
    assert (await store.get_session(rid))["status"] == "stopping"

    # The orchestrator's racing completion intent is refused under the lock.
    with pytest.raises(IllegalTransitionError):
        await sm.transition(rid, SessionEvent.COMPLETE)

    # The exit path finalizes the stop instead — never completed, never promoted.
    result = await sm.transition(rid, SessionEvent.FINALIZE_STOP)
    assert result.should_auto_promote is False
    assert (await store.get_session(rid))["status"] == "stopped"


@pytest.mark.asyncio
async def test_w8_completed_is_terminal_late_stop_is_noop(
    tmp_path: Path,
) -> None:
    """Interleaving B: a late stop cannot overwrite completed or revoke promote."""
    store = await _init_store(tmp_path)
    manager = SessionManager(store)
    rid = await _seed_running(store, "res-w8b")
    sm = manager._sm

    result = await sm.transition(rid, SessionEvent.COMPLETE)
    assert result.should_auto_promote is True
    assert (await store.get_session(rid))["status"] == "completed"

    # A late cancel/stop arrives — terminal finality makes it a no-op.
    late = await sm.transition(rid, SessionEvent.STOP_REQUESTED)
    assert late.changed is False
    assert (await store.get_session(rid))["status"] == "completed"


@pytest.mark.asyncio
async def test_w8_hard_timeout_reclassifies_stopped_to_timed_out(
    tmp_path: Path,
) -> None:
    """Interleaving C: the documented stopped → timed_out carve-out."""
    store = await _init_store(tmp_path)
    manager = SessionManager(store)
    rid = await _seed_running(store, "res-w8c")
    sm = manager._sm

    # Session finalized as stopped (e.g. a cancel landed just before hard-timeout).
    await sm.transition(rid, SessionEvent.STOP_REQUESTED)
    await sm.transition(rid, SessionEvent.FINALIZE_STOP)
    assert (await store.get_session(rid))["status"] == "stopped"

    # _run_and_cleanup's hard-timeout path reclassifies via HARD_TIMEOUT.
    await sm.transition(rid, SessionEvent.HARD_TIMEOUT)
    assert (await store.get_session(rid))["status"] == "timed_out"