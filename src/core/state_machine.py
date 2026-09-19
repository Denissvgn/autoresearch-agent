"""Session state machine — the authoritative session-lifecycle writer.

ARC-011 (P0-002) turns the session lifecycle into *data, not ad-hoc status
writes*. This module defines the 13-state diagram, a ``(from, event)`` base
transition table, the severity-override guards that close the W8 race, and
``SessionStateMachine.transition`` — the single legal status writer. ``transition``
holds a per-session ``asyncio.Lock`` across ``read -> guard -> write (transitional
then terminal) -> audit -> broadcast``, so concurrent ``stop`` / ``complete`` /
``timeout`` / ``fail`` intents are resolved by severity
(``fail > timeout > stop > complete``) rather than racing over an unsynchronized
flag.

Scope (P0-002): this module performs only status / audit / broadcast
side-effects. Domain side-effects — spawning the orchestrator task, setting /
clearing the pause & stop flags, auto-promotion, interrupting runtime commands
— stay with the caller and are signalled via ``TransitionResult``. Routing the
existing direct ``status=`` writers through ``transition()`` is P0-003 / P0-004;
the end-to-end W8 race replay is P0-005. See
ARC-011 P0-002 §3-§7 for the design consumed here (the full diagram and
transition tables are recorded in this module).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Dict, FrozenSet, Optional, Tuple, Union

from src.core.state_store import StateStore
from src.ws.events import EventBroadcaster

logger = logging.getLogger(__name__)

# System actor recorded on machine-driven audit rows. Operator identity for
# pause / resume / stop continues to be recorded by the API layer's existing
# ``research.{pause, resume, stop}`` audit rows; ``session.transition`` is the
# additive machine-level audit action (ARC-011 §9).
_SYSTEM_ACTOR = "autoresearch-agent"


class SessionState(str, Enum):
    """The 13 session lifecycle states (ARC-011 §3)."""

    # initial (new)
    PENDING = "pending"
    # active
    RUNNING = "running"
    PAUSED = "paused"
    # transitional (intent) — ARC-011 §2 D-trans
    STOPPING = "stopping"
    COMPLETING = "completing"
    TIMING_OUT = "timing_out"
    FAILING = "failing"
    # terminal
    STOPPED = "stopped"
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    # recovery-terminal (startup recovery only)
    RESUMABLE = "resumable"
    INTERRUPTED = "interrupted"


class SessionEvent(str, Enum):
    """Events that drive session state transitions (ARC-011 §4.1)."""

    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP_REQUESTED = "stop_requested"
    FINALIZE_STOP = "finalize_stop"
    COMPLETE = "complete"
    TIMEOUT = "timeout"
    HARD_TIMEOUT = "hard_timeout"
    FAIL = "fail"
    RESTART_RECOVER = "restart_recover"


_TRANSITIONAL: FrozenSet[SessionState] = frozenset(
    {
        SessionState.STOPPING,
        SessionState.COMPLETING,
        SessionState.TIMING_OUT,
        SessionState.FAILING,
    }
)
_TERMINAL: FrozenSet[SessionState] = frozenset(
    {
        SessionState.STOPPED,
        SessionState.COMPLETED,
        SessionState.TIMED_OUT,
        SessionState.FAILED,
        SessionState.RESUMABLE,
        SessionState.INTERRUPTED,
    }
)
_RECOVERY_TERMINAL: FrozenSet[SessionState] = frozenset(
    {SessionState.RESUMABLE, SessionState.INTERRUPTED}
)

# Severity ranks (ARC-011 §4.2): higher wins. Only the four terminal-intent
# events carry a severity; the remaining events (start/pause/resume/
# finalize_stop/restart_recover) are resolved by the base table and are
# illegal against an in-flight transitional state.
_SEVERITY_RANK: Dict[SessionEvent, int] = {
    SessionEvent.COMPLETE: 1,
    SessionEvent.STOP_REQUESTED: 2,
    SessionEvent.TIMEOUT: 3,
    SessionEvent.HARD_TIMEOUT: 3,
    SessionEvent.FAIL: 4,
}
# Severity of a transitional (intent) state's own intent.
_INTENT_RANK: Dict[SessionState, int] = {
    SessionState.COMPLETING: 1,
    SessionState.STOPPING: 2,
    SessionState.TIMING_OUT: 3,
    SessionState.FAILING: 4,
}


class IllegalTransitionError(RuntimeError):
    """Raised when an event is not legal from the session's current state.

    Carries the ``(from_state, event)`` pair so callers can react — most
    importantly the orchestrator exit path, which catches a ``complete``
    refused by a racing stop and skips auto-promotion (ARC-011 §5 / §8).
    """

    def __init__(self, from_state: SessionState, event: SessionEvent) -> None:
        self.from_state = from_state
        self.event = event
        super().__init__(
            f"Illegal session transition: event={event.value} "
            f"from state={from_state.value}"
        )


@dataclass(frozen=True)
class TransitionResult:
    """Outcome of a ``transition()`` call.

    ``changed`` is ``False`` for idempotent no-ops (replays against a terminal
    state, ``(paused, pause)``, re-asserting the in-flight intent), which emit
    no audit row and no broadcast (ARC-011 §7.2). ``should_auto_promote`` is
    ``True`` only for the net ``running -> completed`` completion and is the
    caller's signal to fire auto-promotion as a post-commit side-effect (§4.3).
    """

    new_state: SessionState
    changed: bool
    event: SessionEvent
    from_state: SessionState
    path: Tuple[SessionState, ...] = ()
    should_auto_promote: bool = False
    broadcast_event: Optional[str] = None
    severity_redirected: bool = False


@dataclass(frozen=True)
class _TransitionSpec:
    """Declarative description of a transition's writes and side-effects.

    ``transitional`` is the optional intent state written before the terminal
    state under the same lock (e.g. ``complete`` writes ``completing`` then
    ``completed``). ``broadcast_event`` is ``None`` for transitional-only steps
    that must not be broadcast (ARC-011 §9). ``auto_promote`` is ``True`` only
    for the net ``running -> completed`` completion.
    """

    terminal: SessionState
    transitional: Optional[SessionState] = None
    broadcast_event: Optional[str] = None
    auto_promote: bool = False


# Base transitions from active / pending sources. Sources that are already
# transitional are resolved by severity (see ``_resolve_severity``); sources
# that are terminal are resolved by the terminal-finality rule.
_BASE_TRANSITIONS: Dict[Tuple[SessionState, SessionEvent], _TransitionSpec] = {
    (SessionState.PENDING, SessionEvent.START): _TransitionSpec(
        terminal=SessionState.RUNNING, broadcast_event="research_started"
    ),
    (SessionState.RUNNING, SessionEvent.PAUSE): _TransitionSpec(
        terminal=SessionState.PAUSED, broadcast_event="research_paused"
    ),
    (SessionState.PAUSED, SessionEvent.RESUME): _TransitionSpec(
        terminal=SessionState.RUNNING, broadcast_event="research_resumed"
    ),
    # stop intent: transitional only — the caller drives a second
    # ``finalize_stop`` after drain/cancel (ARC-011 §7.1, two acquisitions).
    (SessionState.RUNNING, SessionEvent.STOP_REQUESTED): _TransitionSpec(
        terminal=SessionState.STOPPING
    ),
    (SessionState.PAUSED, SessionEvent.STOP_REQUESTED): _TransitionSpec(
        terminal=SessionState.STOPPING
    ),
    (SessionState.STOPPING, SessionEvent.FINALIZE_STOP): _TransitionSpec(
        terminal=SessionState.STOPPED, broadcast_event="research_stopped"
    ),
    # atomic two-phase terminal transitions (transitional + terminal under one lock)
    (SessionState.RUNNING, SessionEvent.COMPLETE): _TransitionSpec(
        terminal=SessionState.COMPLETED,
        transitional=SessionState.COMPLETING,
        broadcast_event="research_completed",
        auto_promote=True,
    ),
    (SessionState.RUNNING, SessionEvent.TIMEOUT): _TransitionSpec(
        terminal=SessionState.TIMED_OUT,
        transitional=SessionState.TIMING_OUT,
        broadcast_event="research_timed_out",
    ),
    (SessionState.RUNNING, SessionEvent.HARD_TIMEOUT): _TransitionSpec(
        terminal=SessionState.TIMED_OUT,
        transitional=SessionState.TIMING_OUT,
        broadcast_event="research_timed_out",
    ),
    (SessionState.RUNNING, SessionEvent.FAIL): _TransitionSpec(
        terminal=SessionState.FAILED,
        transitional=SessionState.FAILING,
        broadcast_event="research_failed",
    ),
    # ARC-012 P7-009: the runtime task behind a paused session can die (crash
    # in the pause poll, killed wrapper) — a ``paused`` row whose task is gone
    # is unresumable, so FAIL is legal from ``paused`` exactly as from
    # ``running``. Without this edge the crash left the row ``paused`` forever
    # (a zombie indistinguishable from a genuinely paused session).
    (SessionState.PAUSED, SessionEvent.FAIL): _TransitionSpec(
        terminal=SessionState.FAILED,
        transitional=SessionState.FAILING,
        broadcast_event="research_failed",
    ),
    # startup recovery (the caller selects resumable vs interrupted via
    # ``recovery_target`` and interrupts runtime commands as a side-effect).
    (SessionState.RUNNING, SessionEvent.RESTART_RECOVER): _TransitionSpec(
        terminal=SessionState.RESUMABLE
    ),
    (SessionState.PAUSED, SessionEvent.RESTART_RECOVER): _TransitionSpec(
        terminal=SessionState.RESUMABLE
    ),
}

# When a more-severe event arrives mid-flight, the in-flight intent is discarded
# and the event's own intent is written instead (ARC-011 §4.2 — the W8 fix).
_REDIRECT_SPEC: Dict[SessionEvent, _TransitionSpec] = {
    SessionEvent.STOP_REQUESTED: _TransitionSpec(terminal=SessionState.STOPPING),
    SessionEvent.TIMEOUT: _TransitionSpec(
        terminal=SessionState.TIMED_OUT,
        transitional=SessionState.TIMING_OUT,
        broadcast_event="research_timed_out",
    ),
    SessionEvent.HARD_TIMEOUT: _TransitionSpec(
        terminal=SessionState.TIMED_OUT,
        transitional=SessionState.TIMING_OUT,
        broadcast_event="research_timed_out",
    ),
    SessionEvent.FAIL: _TransitionSpec(
        terminal=SessionState.FAILED,
        transitional=SessionState.FAILING,
        broadcast_event="research_failed",
    ),
}

# Re-asserting the same intent against its own transitional state finalizes the
# pending two-phase (crash-recovery safe: a ``complete`` interrupted between the
# transitional and terminal writes is finished on retry). ``stopping`` has no
# paired terminal under ``stop_requested`` (the caller sends ``finalize_stop``),
# so it is handled as an idempotent no-op instead.
_SEVERITY_FINALIZE_SPEC: Dict[SessionState, _TransitionSpec] = {
    SessionState.COMPLETING: _TransitionSpec(
        terminal=SessionState.COMPLETED,
        transitional=SessionState.COMPLETING,
        broadcast_event="research_completed",
        auto_promote=True,
    ),
    SessionState.TIMING_OUT: _TransitionSpec(
        terminal=SessionState.TIMED_OUT,
        transitional=SessionState.TIMING_OUT,
        broadcast_event="research_timed_out",
    ),
    SessionState.FAILING: _TransitionSpec(
        terminal=SessionState.FAILED,
        transitional=SessionState.FAILING,
        broadcast_event="research_failed",
    ),
}


class SessionLockRegistry:
    """Per-session ``asyncio.Lock`` registry for ``transition()``.

    Lazily creates one lock per ``research_id`` so the
    read-decide-write-audit-broadcast critical section serializes per session
    without blocking unrelated sessions. Locks for sessions that reach a
    terminal state are evicted by ``SessionStateMachine.transition`` once the
    lock is released: a terminal session admits no state-changing transition
    (the only post-terminal change is the idempotent ``stopped -> timed_out``
    re-classify), so the lock is dead and a fresh one is created if activity
    ever resumes. ARC-011 §7.1.
    """

    def __init__(self) -> None:
        self._locks: Dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    @asynccontextmanager
    async def for_session(self, research_id: str) -> AsyncIterator[None]:
        """Acquire the per-session lock, creating it on first use."""
        async with self._guard:
            lock = self._locks.get(research_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[research_id] = lock
        async with lock:
            yield

    def evict(self, research_id: str) -> None:
        """Drop the per-session lock (called after a terminal transition)."""
        self._locks.pop(research_id, None)

    @property
    def size(self) -> int:
        return len(self._locks)


class SessionStateMachine:
    """The single legal writer of ``research_sessions.status``.

    Composes a ``StateStore`` (read / write status, emit audit) and an
    ``EventBroadcaster`` (lifecycle broadcasts). Both are injected rather than
    imported as globals so the machine is unit-testable with a tmp SQLite DB
    and a capturing broadcaster, and so the W8 race tests (P0-005) can drive it
    deterministically.
    """

    def __init__(
        self,
        store: StateStore,
        broadcaster: EventBroadcaster,
        *,
        lock_registry: Optional[SessionLockRegistry] = None,
    ) -> None:
        self._store = store
        self._broadcaster = broadcaster
        self._locks = lock_registry or SessionLockRegistry()

    async def transition(
        self,
        session_id: str,
        event: Union[SessionEvent, str],
        *,
        status_fields: Optional[Dict[str, Any]] = None,
        broadcast_fields: Optional[Dict[str, Any]] = None,
        actor_id: str = _SYSTEM_ACTOR,
        recovery_target: SessionState = SessionState.RESUMABLE,
    ) -> TransitionResult:
        """Drive one lifecycle transition under a per-session lock.

        Args:
            session_id: The research session id.
            event: The lifecycle event (enum or its string value).
            status_fields: Extra columns to persist alongside the terminal
                ``status`` write (e.g. ``completed_at``, ``error_message``,
                ``terminal_reason``, ``total_api_cost_usd``). Applied once, on
                the terminal write.
            broadcast_fields: Extra keys to merge into the broadcast event
                (e.g. ``iterations`` / ``total_cost_usd`` / ``elapsed_s`` for
                ``research_completed``, ``error`` for ``research_failed``) so
                the existing payload shapes are preserved (ARC-011 §9).
            actor_id: Audit actor for the machine-level ``session.transition``
                audit row.
            recovery_target: ``resumable`` or ``interrupted`` for
                ``restart_recover`` (caller-selected from workspace/manifest
                presence).

        Returns:
            A ``TransitionResult``. ``changed`` is ``False`` for idempotent
            no-ops, which emit no audit row and no broadcast.

        Raises:
            IllegalTransitionError: the event is not legal from the current
                state (ARC-011 §5).
            LookupError: the session row does not exist.
        """
        evt = event if isinstance(event, SessionEvent) else SessionEvent(event)
        if recovery_target not in _RECOVERY_TERMINAL:
            raise ValueError(
                "recovery_target must be a recovery-terminal state "
                f"(resumable/interrupted), got {recovery_target.value}"
            )

        async with self._locks.for_session(session_id):
            # ARC-011 P6-003: hold the cross-process advisory lock for the
            # duration of the read→guard→write→audit→broadcast critical
            # section. SQLiteStateStore.session_lock is a no-op (single-worker);
            # PostgresStateStore.session_lock takes pg_advisory_xact_lock so
            # the same-session transition is mutually exclusive across workers
            # sharing the DB (the H2 fix at multi-worker scale).
            async with self._store.session_lock(session_id):
                result = await self._transition_locked(
                    session_id,
                    evt,
                    status_fields,
                    broadcast_fields,
                    actor_id,
                    recovery_target,
                )
        if result.changed and result.new_state in _TERMINAL:
            # The session is now terminal-final: its lock is dead. Eviction is
            # safe because every post-terminal transition is a no-op (or the
            # idempotent stopped -> timed_out re-classify), so missing
            # serialization between a late no-op and a fresh transition cannot
            # produce a write/write conflict.
            self._locks.evict(session_id)
        return result

    async def _transition_locked(
        self,
        session_id: str,
        evt: SessionEvent,
        status_fields: Optional[Dict[str, Any]],
        broadcast_fields: Optional[Dict[str, Any]],
        actor_id: str,
        recovery_target: SessionState,
    ) -> TransitionResult:
        session = await self._store.get_session(session_id)
        if session is None:
            raise LookupError(f"Session {session_id} not found")
        current = SessionState(session["status"])

        # 1. Terminal finality (ARC-011 §5). Any event against a terminal state
        #    is an idempotent no-op, EXCEPT the documented ``stopped ->
        #    timed_out`` re-classify (interleaving C). Recovery-terminal states
        #    (resumable / interrupted) are no-op for everything: ``continue``
        #    spawns a *new* child session row and never transitions the parent.
        if current in _TERMINAL:
            if current is SessionState.STOPPED and evt is SessionEvent.HARD_TIMEOUT:
                return await self._apply(
                    session_id,
                    current,
                    evt,
                    _TransitionSpec(
                        terminal=SessionState.TIMED_OUT,
                        broadcast_event="research_timed_out",
                    ),
                    status_fields,
                    broadcast_fields,
                    actor_id,
                )
            return TransitionResult(
                new_state=current, changed=False, event=evt, from_state=current
            )

        # 2. Idempotent no-op: ``(paused, pause)`` (ARC-011 §7.2).
        if current is SessionState.PAUSED and evt is SessionEvent.PAUSE:
            return TransitionResult(
                new_state=current, changed=False, event=evt, from_state=current
            )

        # 3. Already mid-flight: resolve the incoming event against the
        #    in-flight intent by severity (ARC-011 §4.2).
        if current in _TRANSITIONAL:
            spec, redirected, no_op = _resolve_severity(current, evt)
            if no_op:
                return TransitionResult(
                    new_state=current, changed=False, event=evt, from_state=current
                )
            if spec is None:
                raise IllegalTransitionError(current, evt)
            return await self._apply(
                session_id,
                current,
                evt,
                spec,
                status_fields,
                broadcast_fields,
                actor_id,
                severity_redirected=redirected,
            )

        # 4. Active / pending source: straight base-table lookup.
        spec = _BASE_TRANSITIONS.get((current, evt))
        if spec is None:
            raise IllegalTransitionError(current, evt)
        if (
            evt is SessionEvent.RESTART_RECOVER
            and recovery_target is not spec.terminal
        ):
            spec = _TransitionSpec(
                terminal=recovery_target,
                transitional=spec.transitional,
                broadcast_event=spec.broadcast_event,
                auto_promote=spec.auto_promote,
            )
        return await self._apply(
            session_id, current, evt, spec, status_fields, broadcast_fields, actor_id
        )

    async def _apply(
        self,
        session_id: str,
        from_state: SessionState,
        evt: SessionEvent,
        spec: _TransitionSpec,
        status_fields: Optional[Dict[str, Any]],
        broadcast_fields: Optional[Dict[str, Any]],
        actor_id: str,
        *,
        severity_redirected: bool = False,
    ) -> TransitionResult:
        """Execute a resolved spec atomically under the caller's lock.

        Writes the transitional (intent) state first, then the terminal state
        (carrying the caller's ``status_fields`` exactly once), emits one
        uniform ``session.transition`` audit row, and broadcasts the spec's
        lifecycle event with the caller's domain fields merged. ARC-011 §7.1.
        """
        path: list[SessionState] = []
        extra = status_fields or {}
        if spec.transitional is not None and spec.transitional is not spec.terminal:
            await self._store.update_session(session_id, status=spec.transitional.value)
            path.append(spec.transitional)
        await self._store.update_session(
            session_id, status=spec.terminal.value, **extra
        )
        path.append(spec.terminal)
        # ARC-011 P6-003: bump the fencing epoch after the terminal status
        # write so any command dispatched before this transition is
        # deauthorized (its captured epoch no longer matches). No-op on
        # SQLiteStateStore (single-worker); increments lock_epoch on Postgres.
        await self._store.bump_session_epoch(session_id)

        await self._store.record_audit_event(
            actor_id=actor_id,
            action="session.transition",
            outcome="success",
            research_id=session_id,
            request_metadata={
                "from": from_state.value,
                "to": spec.terminal.value,
                "event": evt.value,
                "path": [state.value for state in path],
                "severity_redirected": severity_redirected,
            },
        )

        broadcast_event = spec.broadcast_event
        if broadcast_event is not None:
            payload: Dict[str, Any] = {
                "event": broadcast_event,
                "research_id": session_id,
            }
            if spec.terminal in _TERMINAL and spec.terminal not in _RECOVERY_TERMINAL:
                payload["status"] = spec.terminal.value
            if broadcast_fields:
                payload.update(broadcast_fields)
            await self._broadcaster.broadcast(payload)

        should_promote = (
            spec.auto_promote
            and not severity_redirected
            and spec.terminal is SessionState.COMPLETED
        )
        return TransitionResult(
            new_state=spec.terminal,
            changed=True,
            event=evt,
            from_state=from_state,
            path=tuple(path),
            should_auto_promote=should_promote,
            broadcast_event=broadcast_event,
            severity_redirected=severity_redirected,
        )


def _resolve_severity(
    current: SessionState, evt: SessionEvent
) -> Tuple[Optional[_TransitionSpec], bool, bool]:
    """Resolve an event against an in-flight transitional (intent) state.

    Returns ``(spec, severity_redirected, no_op)``:

    * a non-``None`` ``spec`` -> apply it (the W8 redirect, or a same-intent
      finalize of a crashed two-phase);
    * ``spec is None`` and ``no_op`` -> idempotent re-assert (no write);
    * ``spec is None`` and not ``no_op`` -> illegal (caller raises).

    ARC-011 §4.2 (severity overrides) and §5 (guards).
    """
    # ``finalize_stop`` is the only non-severity event legal against a
    # transitional state, and only from ``stopping``.
    if evt is SessionEvent.FINALIZE_STOP:
        if current is SessionState.STOPPING:
            spec = _BASE_TRANSITIONS[(SessionState.STOPPING, SessionEvent.FINALIZE_STOP)]
            return spec, False, False
        return None, False, False

    incoming = _SEVERITY_RANK.get(evt)
    if incoming is None:
        # start / pause / resume / restart_recover against a winding-down
        # session: illegal (ARC-011 §5).
        return None, False, False

    current_rank = _INTENT_RANK[current]
    if incoming > current_rank:
        # More-severe event redirects the intent — the headline W8 fix.
        return _REDIRECT_SPEC[evt], True, False
    if incoming < current_rank:
        # Less-severe event is refused (e.g. ``(stopping, complete)``).
        return None, False, False

    # Equal rank: the same intent is re-asserted. ``stopping`` has no paired
    # terminal under ``stop_requested`` (the caller sends ``finalize_stop``),
    # so re-asserting stop is an idempotent no-op; the other intents finalize.
    if current is SessionState.STOPPING:
        return None, False, True
    return _SEVERITY_FINALIZE_SPEC[current], False, False
