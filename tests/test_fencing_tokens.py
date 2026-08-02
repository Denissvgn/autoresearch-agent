"""ARC-011 P6-004 — fencing tokens + cross-worker control tests.

Validates the H3 (cross-worker stop/pause propagation) and H4 (stale-write
fencing) fixes against a live Postgres, simulating two workers as two
``PostgresStateStore`` instances sharing the same pool/DB within one process.
The real multi-process harness is P6-007; this is the in-process precursor.

Skipped when ``AUTORESEARCH_DATABASE_URL`` is unset.
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.postgres


def _base_dsn() -> str | None:
    raw = os.getenv("AUTORESEARCH_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not raw:
        return None
    return raw.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture()
async def pg_store():
    import asyncpg

    from src.core.postgres_state_store import PostgresStateStore

    base = _base_dsn()
    if base is None:
        pytest.skip("AUTORESEARCH_DATABASE_URL unset")
    dbname = f"autoresearch_fence_{uuid.uuid4().hex[:12]}"
    admin_dsn = base.rsplit("/", 1)[0] + "/postgres"
    admin = await asyncpg.connect(admin_dsn)
    try:
        await admin.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await admin.close()
    test_dsn = base.rsplit("/", 1)[0] + f"/{dbname}"
    store = PostgresStateStore(test_dsn)
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()
        cleanup = await asyncpg.connect(admin_dsn)
        try:
            await cleanup.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                dbname,
            )
            await cleanup.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        finally:
            await cleanup.close()


async def _seed_session(store, sid: str) -> None:
    await store.create_session(
        session_id=sid, instrument="EURUSD", timeframe="H1",
        model_type="direction", tag="t", quick_mode=False, max_iterations=5,
        max_budget_usd=10.0, focus_hint=None, workspace_path="/tmp/ws",
    )


async def test_cross_worker_stop_observed_by_owner(pg_store):
    """H3: a stop transition on worker B is observed by worker A's poll."""
    from src.core.state_machine import SessionStateMachine
    from src.ws.events import EventBroadcaster

    store = pg_store
    sid = f"res_cwstop_{uuid.uuid4().hex[:6]}"
    await _seed_session(store, sid)
    # Worker B drives the stop via its own state machine against the shared DB.
    sm_b = SessionStateMachine(store, EventBroadcaster())
    await sm_b.transition(sid, "stop_requested", actor_id="operator_B")

    # Worker A's orchestrator polls the cross-worker stop path.
    class _FakeOrch:
        _stop_flags: dict = {}
        def __init__(self, s):
            self._store = s

    from src.core.orchestrator import AgentOrchestrator

    fake = _FakeOrch(store)
    observed = await AgentOrchestrator._should_stop_cross_worker(fake, sid)
    assert observed is True
    session = await store.get_session(sid)
    assert session["status"] == "stopping"
    assert session["lock_epoch"] >= 1  # the transition bumped the epoch


async def test_cross_worker_stop_false_for_active_session(pg_store):
    """No false positives: an active running session is not 'stopped'."""
    from src.core.orchestrator import AgentOrchestrator

    store = pg_store
    sid = f"res_active_{uuid.uuid4().hex[:6]}"
    await _seed_session(store, sid)

    class _FakeOrch:
        _stop_flags: dict = {}
        def __init__(self, s):
            self._store = s

    fake = _FakeOrch(store)
    observed = await AgentOrchestrator._should_stop_cross_worker(fake, sid)
    assert observed is False


async def test_update_session_fencing_stale_epoch_rejected(pg_store):
    """H4: update_session with a stale lock_epoch returns None (0 rows)."""
    store = pg_store
    sid = f"res_fence_{uuid.uuid4().hex[:6]}"
    await _seed_session(store, sid)
    # Bump the epoch to 5 (simulating a stop/timeout transition).
    conn = await store._conn()
    try:
        await conn.execute(
            "UPDATE research_sessions SET lock_epoch = 5 WHERE id = $1", sid
        )
    finally:
        await store._release_short_lived(conn)
    # A stale worker (captured epoch=4) is rejected.
    result = await store.update_session(sid, lock_epoch=4, total_api_cost_usd=1.0)
    assert result is None
    conn = await store._conn()
    try:
        cost = await conn.fetchval(
            "SELECT total_api_cost_usd FROM research_sessions WHERE id = $1", sid
        )
    finally:
        await store._release_short_lived(conn)
    assert cost == 0.0  # not written
    # The fresh-epoch update succeeds.
    await store.update_session(sid, lock_epoch=5, total_api_cost_usd=2.0)
    conn = await store._conn()
    try:
        cost = await conn.fetchval(
            "SELECT total_api_cost_usd FROM research_sessions WHERE id = $1", sid
        )
    finally:
        await store._release_short_lived(conn)
    assert cost == 2.0


async def test_bump_session_epoch_monotonic(pg_store):
    """bump_session_epoch increments lock_epoch by 1 each call."""
    store = pg_store
    sid = f"res_bump_{uuid.uuid4().hex[:6]}"
    await _seed_session(store, sid)
    conn = await store._conn()
    try:
        e0 = await conn.fetchval(
            "SELECT lock_epoch FROM research_sessions WHERE id = $1", sid
        )
        await store._release_short_lived(conn)
        await store.bump_session_epoch(sid)
        await store.bump_session_epoch(sid)
        conn = await store._conn()
        e2 = await conn.fetchval(
            "SELECT lock_epoch FROM research_sessions WHERE id = $1", sid
        )
    finally:
        await store._release_short_lived(conn)
    assert e0 == 0
    assert e2 == 2


async def test_transition_bumps_epoch(pg_store):
    """A committed transition increments lock_epoch (P6-003/P6-004 wiring)."""
    from src.core.state_machine import SessionStateMachine
    from src.ws.events import EventBroadcaster

    store = pg_store
    sid = f"res_tx_{uuid.uuid4().hex[:6]}"
    await _seed_session(store, sid)
    session = await store.get_session(sid)
    assert session["lock_epoch"] == 0
    sm = SessionStateMachine(store, EventBroadcaster())
    await sm.transition(sid, "stop_requested", actor_id="tester")
    session = await store.get_session(sid)
    # One committed transition ⇒ epoch bumped by 1.
    assert session["lock_epoch"] == 1
    assert session["status"] == "stopping"
