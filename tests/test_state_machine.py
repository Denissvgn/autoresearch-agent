"""Unit tests for ``SessionStateMachine`` (ARC-011 P0-002).

Exercises the full §4.1 transition table, the §5 guards, the §4.2 severity
overrides (the W8 fix), §7.2 idempotency, the per-session lock serialization,
and the broadcast/status-field parity merges. Uses a real ``ResultsStore`` on a
tmp SQLite file plus a capturing broadcaster; the orchestrator / promoter are
not involved (those are P0-003 / P0-004 / P0-005).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.results_store import ResultsStore
from src.core.state_machine import (
    IllegalTransitionError,
    SessionEvent,
    SessionLockRegistry,
    SessionState,
    SessionStateMachine,
    TransitionResult,
)
from src.ws.events import EventBroadcaster


class _CapturingBroadcaster(EventBroadcaster):
    """An ``EventBroadcaster`` that records broadcasts instead of sending them."""

    def __init__(self) -> None:
        super().__init__()
        self.events: List[Dict[str, Any]] = []

    async def broadcast(self, event: Dict[str, Any]) -> None:
        self.events.append(dict(event))


async def _make_store(tmp_path: Path) -> ResultsStore:
    store = ResultsStore(str(tmp_path / "sm.sqlite"))
    await store.initialize()
    return store


async def _seed(
    store: ResultsStore,
    *,
    session_id: str = "sess-1",
    status: str = "running",
) -> str:
    """Insert a session row (always as ``running``) then move it to ``status``."""
    await store.create_session(
        session_id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag=session_id,
        quick_mode=True,
        max_iterations=3,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path="/ws",
    )
    if status != "running":
        await store.update_session(session_id, status=status)
    return session_id


async def _audit_count(store: ResultsStore, session_id: str) -> int:
    rows = await store.list_audit_events(research_id=session_id, limit=500)
    return sum(1 for r in rows if r["action"] == "session.transition")


def _status_of(session: Dict[str, Any]) -> SessionState:
    return SessionState(session["status"])


# ---------------------------------------------------------------------------
# 1. Every legal base transition
# ---------------------------------------------------------------------------

_LEGAL_CASES: List[Tuple[str, SessionEvent, SessionState, Any, bool]] = [
    ("pending", SessionEvent.START, SessionState.RUNNING, "research_started", False),
    ("running", SessionEvent.PAUSE, SessionState.PAUSED, "research_paused", False),
    ("paused", SessionEvent.RESUME, SessionState.RUNNING, "research_resumed", False),
    ("running", SessionEvent.STOP_REQUESTED, SessionState.STOPPING, None, False),
    ("paused", SessionEvent.STOP_REQUESTED, SessionState.STOPPING, None, False),
    ("stopping", SessionEvent.FINALIZE_STOP, SessionState.STOPPED, "research_stopped", False),
    ("running", SessionEvent.COMPLETE, SessionState.COMPLETED, "research_completed", True),
    ("running", SessionEvent.TIMEOUT, SessionState.TIMED_OUT, "research_timed_out", False),
    ("running", SessionEvent.HARD_TIMEOUT, SessionState.TIMED_OUT, "research_timed_out", False),
    ("running", SessionEvent.FAIL, SessionState.FAILED, "research_failed", False),
    ("running", SessionEvent.RESTART_RECOVER, SessionState.RESUMABLE, None, False),
    ("paused", SessionEvent.RESTART_RECOVER, SessionState.RESUMABLE, None, False),
]


@pytest.mark.parametrize(
    "initial, event, expected_state, broadcast, promote",
    _LEGAL_CASES,
    ids=[c[1].value for c in _LEGAL_CASES],
)
async def test_legal_transition(
    tmp_path: Path,
    initial: str,
    event: SessionEvent,
    expected_state: SessionState,
    broadcast: Any,
    promote: bool,
) -> None:
    store = await _make_store(tmp_path)
    sid = await _seed(store, status=initial)
    bcaster = _CapturingBroadcaster()
    sm = SessionStateMachine(store, bcaster)

    result = await sm.transition(sid, event)

    assert result.changed is True
    assert result.new_state is expected_state
    assert result.event is event
    assert result.from_state is SessionState(initial)
    assert result.should_auto_promote is promote
    assert result.broadcast_event == broadcast

    session = await store.get_session(sid)
    assert _status_of(session) is expected_state

    # exactly one machine-level audit row per real transition
    assert await _audit_count(store, sid) == 1

    if broadcast is None:
        assert bcaster.events == []
    else:
        assert len(bcaster.events) == 1
        emitted = bcaster.events[0]
        assert emitted["event"] == broadcast
        assert emitted["research_id"] == sid
        if expected_state in (
            SessionState.STOPPED,
            SessionState.COMPLETED,
            SessionState.TIMED_OUT,
            SessionState.FAILED,
        ):
            assert emitted["status"] == expected_state.value


# ---------------------------------------------------------------------------
# 2. Every illegal transition raises and writes nothing
# ---------------------------------------------------------------------------

_ILLEGAL_CASES: List[Tuple[str, SessionEvent]] = [
    ("running", SessionEvent.RESUME),
    ("paused", SessionEvent.START),
    ("paused", SessionEvent.COMPLETE),
    ("paused", SessionEvent.TIMEOUT),
    ("paused", SessionEvent.HARD_TIMEOUT),
    ("paused", SessionEvent.FAIL),
    ("pending", SessionEvent.PAUSE),
    ("pending", SessionEvent.COMPLETE),
    ("stopping", SessionEvent.COMPLETE),  # less-severe refused (the W8 guard)
    ("stopping", SessionEvent.PAUSE),
    ("stopping", SessionEvent.RESUME),
    ("completing", SessionEvent.PAUSE),
    ("completing", SessionEvent.RESUME),
    ("timing_out", SessionEvent.STOP_REQUESTED),
    ("timing_out", SessionEvent.COMPLETE),
    ("failing", SessionEvent.STOP_REQUESTED),
    ("failing", SessionEvent.COMPLETE),
]


@pytest.mark.parametrize(
    "initial, event", _ILLEGAL_CASES, ids=[f"{i}-{e.value}" for i, e in _ILLEGAL_CASES]
)
async def test_illegal_transition_raises_and_writes_nothing(
    tmp_path: Path, initial: str, event: SessionEvent
) -> None:
    store = await _make_store(tmp_path)
    sid = await _seed(store, status=initial)
    bcaster = _CapturingBroadcaster()
    sm = SessionStateMachine(store, bcaster)

    with pytest.raises(IllegalTransitionError) as exc_info:
        await sm.transition(sid, event)

    assert exc_info.value.from_state is SessionState(initial)
    assert exc_info.value.event is event

    # no partial writes, no audit, no broadcast
    session = await store.get_session(sid)
    assert _status_of(session) is SessionState(initial)
    assert await _audit_count(store, sid) == 0
    assert bcaster.events == []


# ---------------------------------------------------------------------------
# 3. Idempotent no-ops emit no audit and no broadcast
# ---------------------------------------------------------------------------

_NOOP_CASES: List[Tuple[str, SessionEvent]] = [
    ("completed", SessionEvent.STOP_REQUESTED),
    ("completed", SessionEvent.COMPLETE),
    ("stopped", SessionEvent.STOP_REQUESTED),
    ("stopped", SessionEvent.FINALIZE_STOP),
    ("stopped", SessionEvent.COMPLETE),
    ("timed_out", SessionEvent.HARD_TIMEOUT),
    ("timed_out", SessionEvent.TIMEOUT),
    ("failed", SessionEvent.FAIL),
    ("resumable", SessionEvent.STOP_REQUESTED),
    ("interrupted", SessionEvent.COMPLETE),
    ("paused", SessionEvent.PAUSE),  # explicit idempotency rule
    ("stopping", SessionEvent.STOP_REQUESTED),  # equal-rank re-assert
]


@pytest.mark.parametrize(
    "initial, event", _NOOP_CASES, ids=[f"{i}-{e.value}" for i, e in _NOOP_CASES]
)
async def test_noop_transition_writes_nothing(
    tmp_path: Path, initial: str, event: SessionEvent
) -> None:
    store = await _make_store(tmp_path)
    sid = await _seed(store, status=initial)
    bcaster = _CapturingBroadcaster()
    sm = SessionStateMachine(store, bcaster)

    result = await sm.transition(sid, event)

    assert result.changed is False
    assert result.new_state is SessionState(initial)
    assert result.should_auto_promote is False
    session = await store.get_session(sid)
    assert _status_of(session) is SessionState(initial)
    assert await _audit_count(store, sid) == 0
    assert bcaster.events == []


# ---------------------------------------------------------------------------
# 4. Severity overrides (ARC-011 §4.2 — the W8 mechanics)
# ---------------------------------------------------------------------------


async def test_completing_plus_stop_redirects_to_stopping_no_autopromote(
    tmp_path: Path,
) -> None:
    """The headline W8 fix: a racing stop discards the completion intent."""
    store = await _make_store(tmp_path)
    sid = await _seed(store, status="completing")
    sm = SessionStateMachine(store, _CapturingBroadcaster())

    result = await sm.transition(sid, SessionEvent.STOP_REQUESTED)

    assert result.changed is True
    assert result.new_state is SessionState.STOPPING
    assert result.severity_redirected is True
    assert result.should_auto_promote is False
    assert result.broadcast_event is None  # transitional, not broadcast
    assert _status_of(await store.get_session(sid)) is SessionState.STOPPING
    assert await _audit_count(store, sid) == 1


@pytest.mark.parametrize(
    "event, expected",
    [
        (SessionEvent.TIMEOUT, SessionState.TIMED_OUT),
        (SessionEvent.HARD_TIMEOUT, SessionState.TIMED_OUT),
        (SessionEvent.FAIL, SessionState.FAILED),
    ],
)
async def test_completing_outranked_by_more_severe(
    tmp_path: Path, event: SessionEvent, expected: SessionState
) -> None:
    store = await _make_store(tmp_path)
    sid = await _seed(store, status="completing")
    sm = SessionStateMachine(store, _CapturingBroadcaster())

    result = await sm.transition(sid, event)

    assert result.changed is True
    assert result.new_state is expected
    assert result.severity_redirected is True
    assert result.should_auto_promote is False
    assert _status_of(await store.get_session(sid)) is expected


@pytest.mark.parametrize(
    "initial, event, expected",
    [
        ("stopping", SessionEvent.TIMEOUT, SessionState.TIMED_OUT),
        ("stopping", SessionEvent.HARD_TIMEOUT, SessionState.TIMED_OUT),
        ("stopping", SessionEvent.FAIL, SessionState.FAILED),
        ("timing_out", SessionEvent.FAIL, SessionState.FAILED),
    ],
)
async def test_severity_redirects_from_other_transitional(
    tmp_path: Path, initial: str, event: SessionEvent, expected: SessionState
) -> None:
    store = await _make_store(tmp_path)
    sid = await _seed(store, status=initial)
    sm = SessionStateMachine(store, _CapturingBroadcaster())

    result = await sm.transition(sid, event)

    assert result.changed is True
    assert result.new_state is expected
    assert result.severity_redirected is True
    assert _status_of(await store.get_session(sid)) is expected


async def test_stopped_hard_timeout_reclassifies_to_timed_out(tmp_path: Path) -> None:
    """The one documented terminal exit (interleaving C)."""
    store = await _make_store(tmp_path)
    sid = await _seed(store, status="stopped")
    bcaster = _CapturingBroadcaster()
    sm = SessionStateMachine(store, bcaster)

    result = await sm.transition(sid, SessionEvent.HARD_TIMEOUT)

    assert result.changed is True
    assert result.new_state is SessionState.TIMED_OUT
    assert result.severity_redirected is False
    assert _status_of(await store.get_session(sid)) is SessionState.TIMED_OUT
    assert len(bcaster.events) == 1
    assert bcaster.events[0]["event"] == "research_timed_out"


# ---------------------------------------------------------------------------
# 5. Atomic two-phase: transitional value is written before the terminal
# ---------------------------------------------------------------------------


async def test_complete_writes_completing_then_completed(tmp_path: Path) -> None:
    store = await _make_store(tmp_path)
    sid = await _seed(store, status="running")
    sm = SessionStateMachine(store, _CapturingBroadcaster())

    calls: List[Tuple[str, Dict[str, Any]]] = []
    orig_update = store.update_session

    async def _record(session_id: str, **fields: Any) -> Any:
        calls.append((session_id, dict(fields)))
        return await orig_update(session_id, **fields)

    store.update_session = _record  # type: ignore[method-assign]

    result = await sm.transition(sid, SessionEvent.COMPLETE)

    statuses = [c[1].get("status") for c in calls if "status" in c[1]]
    assert statuses == ["completing", "completed"]
    assert result.path == (SessionState.COMPLETING, SessionState.COMPLETED)
    assert _status_of(await store.get_session(sid)) is SessionState.COMPLETED


# ---------------------------------------------------------------------------
# 6. Side-effect channels: status_fields (terminal write) and broadcast_fields
# ---------------------------------------------------------------------------


async def test_fail_persists_status_fields_on_terminal_write(tmp_path: Path) -> None:
    store = await _make_store(tmp_path)
    sid = await _seed(store, status="running")
    sm = SessionStateMachine(store, _CapturingBroadcaster())

    await sm.transition(
        sid,
        SessionEvent.FAIL,
        status_fields={
            "error_message": "boom",
            "terminal_reason": "error_unrecoverable:ValueError",
        },
    )

    session = await store.get_session(sid)
    assert session["status"] == "failed"
    assert session["error_message"] == "boom"
    assert session["terminal_reason"] == "error_unrecoverable:ValueError"


async def test_complete_broadcast_merges_domain_fields(tmp_path: Path) -> None:
    store = await _make_store(tmp_path)
    sid = await _seed(store, status="running")
    bcaster = _CapturingBroadcaster()
    sm = SessionStateMachine(store, bcaster)

    await sm.transition(
        sid,
        SessionEvent.COMPLETE,
        broadcast_fields={
            "iterations": 5,
            "total_cost_usd": 1.23,
            "elapsed_s": 99.0,
        },
    )

    assert bcaster.events == [
        {
            "event": "research_completed",
            "research_id": sid,
            "status": "completed",
            "iterations": 5,
            "total_cost_usd": 1.23,
            "elapsed_s": 99.0,
        }
    ]


async def test_recovery_target_interrupted(tmp_path: Path) -> None:
    store = await _make_store(tmp_path)
    sid = await _seed(store, status="running")
    sm = SessionStateMachine(store, _CapturingBroadcaster())

    result = await sm.transition(
        sid, SessionEvent.RESTART_RECOVER, recovery_target=SessionState.INTERRUPTED
    )

    assert result.new_state is SessionState.INTERRUPTED
    assert _status_of(await store.get_session(sid)) is SessionState.INTERRUPTED


async def test_invalid_recovery_target_raises(tmp_path: Path) -> None:
    store = await _make_store(tmp_path)
    sid = await _seed(store, status="running")
    sm = SessionStateMachine(store, _CapturingBroadcaster())

    with pytest.raises(ValueError):
        await sm.transition(
            sid,
            SessionEvent.RESTART_RECOVER,
            recovery_target=SessionState.COMPLETED,
        )


# ---------------------------------------------------------------------------
# 7. Per-session lock serialization (logic-level W8 mutual exclusion)
# ---------------------------------------------------------------------------


async def test_concurrent_complete_and_stop_never_corrupts(tmp_path: Path) -> None:
    """Concurrent complete + stop on one session: exactly one intent wins and
    auto-promotion is never eligible while the session ends up stopping."""
    store = await _make_store(tmp_path)
    sid = await _seed(store, status="running")
    sm = SessionStateMachine(store, _CapturingBroadcaster())

    results = await asyncio.gather(
        sm.transition(sid, SessionEvent.COMPLETE),
        sm.transition(sid, SessionEvent.STOP_REQUESTED),
        return_exceptions=True,
    )

    final = _status_of(await store.get_session(sid))
    # Only one of the two interleavings is possible; both leave a consistent
    # state with exactly one machine-level audit row.
    assert final in (SessionState.COMPLETED, SessionState.STOPPING)
    assert await _audit_count(store, sid) == 1

    trs = [r for r in results if isinstance(r, TransitionResult)]
    excs = [r for r in results if isinstance(r, IllegalTransitionError)]
    if final is SessionState.COMPLETED:
        # complete won; the late stop is a no-op against terminal completed.
        assert len(trs) == 2 and excs == []
        assert sum(t.should_auto_promote for t in trs) == 1
    else:
        # stop won; the exit path's complete is refused (illegal) -> no promote.
        assert len(excs) == 1 and len(trs) == 1
        assert all(not t.should_auto_promote for t in trs)


# ---------------------------------------------------------------------------
# 8. Missing session
# ---------------------------------------------------------------------------


async def test_missing_session_raises_lookup_error(tmp_path: Path) -> None:
    store = await _make_store(tmp_path)
    sm = SessionStateMachine(store, _CapturingBroadcaster())

    with pytest.raises(LookupError):
        await sm.transition("nope", SessionEvent.START)


# ---------------------------------------------------------------------------
# 9. Lock registry eviction on terminal
# ---------------------------------------------------------------------------


async def test_lock_evicted_on_terminal(tmp_path: Path) -> None:
    store = await _make_store(tmp_path)
    sid = await _seed(store, status="running")
    locks = SessionLockRegistry()
    sm = SessionStateMachine(store, _CapturingBroadcaster(), lock_registry=locks)

    assert locks.size == 0
    await sm.transition(sid, SessionEvent.PAUSE)
    assert locks.size == 1  # paused is not terminal
    await sm.transition(sid, SessionEvent.RESUME)
    assert locks.size == 1
    await sm.transition(sid, SessionEvent.COMPLETE)
    assert locks.size == 0  # completed is terminal -> evicted
