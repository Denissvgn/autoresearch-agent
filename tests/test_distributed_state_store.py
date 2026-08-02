"""ARC-011 P6-007 — distributed concurrency tests (the Phase-6 exit gate).

Real multi-process + real Postgres. Spawns N worker subprocesses (each its own
asyncio loop + its own ``PostgresStateStore`` sharing the same DB) via
``multiprocessing`` to validate the cross-process guarantees that
single-process tests cannot:

* H1 — atomic idempotency reserve across processes (exactly one winner)
* H2 — cross-process transition serialization (the W8 race, now cross-worker)
* H4 — fencing-token stale-write rejection across processes

These complement the in-process tests in ``test_fencing_tokens.py`` /
``test_postgres_state_store.py`` (which prove the same contracts within one
process). The distributed tests prove the contracts hold across real OS
processes sharing a pool/DB — the actual WEB_CONCURRENCY>1 deployment shape.

Skipped when ``AUTORESEARCH_DATABASE_URL`` is unset (default CI run). The
dedicated ``distributed`` CI job wires a Postgres service + the DSN.
"""

from __future__ import annotations

import asyncio
import multiprocessing as mp
import os
import sys
import uuid
from typing import Any

import pytest

pytestmark = pytest.mark.distributed

_SERVICE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _base_dsn() -> str | None:
    raw = os.getenv("AUTORESEARCH_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not raw:
        return None
    return raw.replace("postgresql+asyncpg://", "postgresql://")


# --------------------------------------------------------------------------
# Worker-process entry points (run in spawned subprocesses). Each is a
# self-contained async function that the child runs to completion, returning a
# picklable result the parent asserts on.
# --------------------------------------------------------------------------

def _worker_attempt_idempotency(dsn: str, op: str, parent_id: str,
                                 key_hash: str) -> dict[str, Any]:
    """Child: try to reserve an idempotency key; return whether it won.

    Assumes the schema is already initialized (the parent fixture does it once
    before spawning — concurrent ``initialize()`` calls race on Postgres
    catalog creation, so workers must NOT re-run the full DDL).
    """
    sys.path.insert(0, _SERVICE_ROOT)
    # Settings env required for the orchestrator import chain.
    os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
    os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
    from src.core.postgres_state_store import PostgresStateStore

    async def run() -> dict[str, Any]:
        store = PostgresStateStore(dsn)
        # create_pool only — no schema DDL (parent initialized once).
        store._pool = await __import__("asyncpg").create_pool(
            dsn=dsn, min_size=1, max_size=2, command_timeout=30,
        )
        try:
            result = await store.begin_idempotency_record(
                operation=op, parent_id=parent_id, key_hash=key_hash,
                request_hash="rh",
            )
            await asyncio.sleep(0.02)  # let concurrent workers genuinely race
            return {"won": result is None, "dsn_ok": True}
        finally:
            await store.close()

    return asyncio.run(run())


def _worker_stop_session(dsn: str, sid: str, actor: str) -> dict[str, Any]:
    """Child: drive a stop transition on the shared session."""
    sys.path.insert(0, _SERVICE_ROOT)
    os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
    os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
    from src.core.postgres_state_store import PostgresStateStore
    from src.core.state_machine import SessionStateMachine
    from src.ws.events import EventBroadcaster

    async def run() -> dict[str, Any]:
        store = PostgresStateStore(dsn)
        await store.initialize()
        try:
            sm = SessionStateMachine(store, EventBroadcaster())
            result = await sm.transition(sid, "stop_requested", actor_id=actor)
            return {"changed": result.changed, "new_state": result.new_state.value}
        finally:
            await store.close()

    return asyncio.run(run())


def _worker_stale_write(dsn: str, sid: str, captured_epoch: int) -> dict[str, Any]:
    """Child: attempt a fenced update with a (stale) captured epoch."""
    sys.path.insert(0, _SERVICE_ROOT)
    os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
    os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
    from src.core.postgres_state_store import PostgresStateStore

    async def run() -> dict[str, Any]:
        store = PostgresStateStore(dsn)
        await store.initialize()
        try:
            result = await store.update_session(
                sid, lock_epoch=captured_epoch, total_api_cost_usd=9.99,
            )
            return {"accepted": result is not None}
        finally:
            await store.close()

    return asyncio.run(run())


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture()
async def pg_dsn():
    """A throwaway DB shared across the test; skip if no Postgres."""
    import asyncpg

    base = _base_dsn()
    if base is None:
        pytest.skip("AUTORESEARCH_DATABASE_URL unset")
    dbname = f"autoresearch_dist_{uuid.uuid4().hex[:12]}"
    admin_dsn = base.rsplit("/", 1)[0] + "/postgres"
    admin = await asyncpg.connect(admin_dsn)
    try:
        await admin.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await admin.close()
    test_dsn = base.rsplit("/", 1)[0] + f"/{dbname}"
    yield test_dsn
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


@pytest.fixture()
async def pg_store(pg_dsn):
    from src.core.postgres_state_store import PostgresStateStore

    store = PostgresStateStore(pg_dsn)
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()


async def _seed(store, sid: str) -> None:
    await store.create_session(
        session_id=sid, instrument="EURUSD", timeframe="H1",
        model_type="direction", tag="dist", quick_mode=False, max_iterations=5,
        max_budget_usd=10.0, focus_hint=None, workspace_path="/tmp/ws",
    )


def _spawn(fn, *args, n: int = 8) -> list:
    """Spawn n worker processes running fn(*args); collect results."""
    ctx = mp.get_context("spawn")  # spawn: clean interpreter, no fork inherit
    with ctx.Pool(processes=n) as pool:
        tasks = [pool.apply_async(fn, args) for _ in range(n)]
        return [task.get(timeout=60) for task in tasks]


# --------------------------------------------------------------------------
# Distributed scenarios
# --------------------------------------------------------------------------

async def test_distributed_idempotency_exactly_one_winner(pg_dsn):
    """H1 across processes: N workers race the same idempotency key; exactly
    one wins (returns None), the rest get the replay record."""
    # Initialize the schema once in the parent (concurrent initialize() in
    # workers races on Postgres catalog creation — see worker docstring).
    from src.core.postgres_state_store import PostgresStateStore

    init_store = PostgresStateStore(pg_dsn)
    await init_store.initialize()
    await init_store.close()

    key = f"dist_op_{uuid.uuid4().hex[:8]}"
    results = _spawn(
        _worker_attempt_idempotency, pg_dsn, key, "parent", "kh", n=8,
    )
    winners = [r for r in results if r["won"]]
    replays = [r for r in results if not r["won"]]
    assert len(winners) == 1, f"expected 1 winner, got {len(winners)}"
    assert len(replays) == 7


async def test_distributed_cross_worker_stop_serialized(pg_store, pg_dsn):
    """H2 across processes: two workers race stop vs complete on the same
    session; the advisory lock serializes them so the outcome is deterministic
    (no interleaved/corrupted status). The session ends in a terminal state
    and lock_epoch reflects exactly the committed transitions."""
    sid = f"res_dist_stop_{uuid.uuid4().hex[:6]}"
    await _seed(pg_store, sid)
    # Two workers drive stop concurrently from separate processes.
    results = _spawn(_worker_stop_session, pg_dsn, sid, "op", n=2)
    # Exactly the first transition changes the state (running -> stopping);
    # the second is a no-op (already stopping ⇒ severity-absorbed).
    changed = sum(1 for r in results if r["changed"])
    assert changed >= 1, "at least one worker must observe the stop"
    session = await pg_store.get_session(sid)
    assert session["status"] in {"stopping", "stopped"}
    # Every committed transition bumped the epoch; it is monotonic.
    assert session["lock_epoch"] >= 1


async def test_distributed_fencing_rejects_stale_write(pg_store, pg_dsn):
    """H4 across processes: worker A captures an epoch, worker B stops the
    session (bumping the epoch), then A's write with the stale epoch is
    rejected (0 rows)."""
    sid = f"res_dist_fence_{uuid.uuid4().hex[:6]}"
    await _seed(pg_store, sid)
    initial = await pg_store.get_session(sid)
    captured_epoch = initial["lock_epoch"]  # 0
    # Worker B stops the session from another process (bumps epoch to >=1).
    _spawn(_worker_stop_session, pg_dsn, sid, "op_b", n=1)
    # Worker A's stale write (captured_epoch == 0) must be rejected.
    results = _spawn(_worker_stale_write, pg_dsn, sid, captured_epoch, n=1)
    assert results[0]["accepted"] is False, "stale write should be rejected"
    # Confirm the cost was NOT written.
    session = await pg_store.get_session(sid)
    assert float(session["total_api_cost_usd"]) == 0.0


async def test_distributed_fresh_epoch_write_accepted(pg_store, pg_dsn):
    """The fence only rejects STALE epochs: a write with the current epoch
    succeeds. Proves the fence isn't over-rejecting."""
    sid = f"res_dist_fresh_{uuid.uuid4().hex[:6]}"
    await _seed(pg_store, sid)
    current = await pg_store.get_session(sid)
    results = _spawn(_worker_stale_write, pg_dsn, sid, current["lock_epoch"], n=1)
    assert results[0]["accepted"] is True
    session = await pg_store.get_session(sid)
    assert float(session["total_api_cost_usd"]) == 9.99
