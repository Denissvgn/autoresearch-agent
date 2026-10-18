"""Work reservations: atomic admission, ownership leases, and write fencing.

Covers the shared-storage admission contract: logical work plus global
capacity are reserved atomically before any side effect; ownership is leased
and fenced by a monotonic epoch; expired leases are reconciled without
touching live workers' sessions.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from src.core.session_manager import SessionManager
from src.core.state_store import (
    CapacityExceeded,
    SQLiteStateStore,
    StaleFenceError,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

ITERATION_KW = dict(
    primary_metric=0.5,
    metric_name="auc",
    all_gates_passed=True,
    decision="keep",
    description="candidate",
    config_snapshot="agent_strategy: BALA\n",
    metrics_json=json.dumps({"auc": 0.5}),
    training_time_s=1.0,
)


async def _open_store(tmp_path: Path) -> SQLiteStateStore:
    store = SQLiteStateStore(str(tmp_path / "state.db"))
    await store.initialize()
    return store


async def _make_session(store: SQLiteStateStore, session_id: str) -> dict:
    return await store.create_session(
        session_id=session_id,
        instrument="EURUSD",
        timeframe="1h",
        model_type="trend",
        tag="",
        quick_mode=True,
        max_iterations=1,
        max_budget_usd=1.0,
        focus_hint="",
        workspace_path="",
    )


@pytest.mark.asyncio
async def test_capacity_limit_and_duplicate_request_semantics(tmp_path):
    store = await _open_store(tmp_path)
    try:
        first = await store.reserve_work(
            reservation_key="work-a",
            scope_key="trend/EURUSD/1h",
            owner_id="worker-1",
            capacity_limit=2,
            lease_seconds=60.0,
        )
        # duplicate request: same key is idempotent and consumes one slot
        again = await store.reserve_work(
            reservation_key="work-a",
            scope_key="trend/EURUSD/1h",
            owner_id="worker-2",
            capacity_limit=2,
            lease_seconds=60.0,
        )
        assert again["epoch"] == first["epoch"]
        assert again["owner_id"] == "worker-1"

        await store.reserve_work(
            reservation_key="work-b",
            scope_key="trend/EURUSD/1h",
            owner_id="worker-1",
            capacity_limit=2,
            lease_seconds=60.0,
        )
        with pytest.raises(CapacityExceeded):
            await store.reserve_work(
                reservation_key="work-c",
                scope_key="trend/EURUSD/1h",
                owner_id="worker-2",
                capacity_limit=2,
                lease_seconds=60.0,
            )

        # releasing frees the slot for new work
        assert await store.release_work("work-a") is True
        third = await store.reserve_work(
            reservation_key="work-c",
            scope_key="trend/EURUSD/1h",
            owner_id="worker-2",
            capacity_limit=2,
            lease_seconds=60.0,
        )
        assert third["state"] == "reserved"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_released_key_reserves_with_fresh_epoch(tmp_path):
    store = await _open_store(tmp_path)
    try:
        first = await store.reserve_work(
            reservation_key="work-a",
            scope_key="scope",
            owner_id="worker-1",
            capacity_limit=2,
            lease_seconds=60.0,
        )
        await store.release_work("work-a")
        second = await store.reserve_work(
            reservation_key="work-a",
            scope_key="scope",
            owner_id="worker-2",
            capacity_limit=2,
            lease_seconds=60.0,
        )
        assert second["epoch"] == int(first["epoch"]) + 1
        assert second["owner_id"] == "worker-2"
    finally:
        await store.close()


_WORKER_SCRIPT = textwrap.dedent(
    """
    import asyncio
    import sys
    from pathlib import Path

    sys.path.insert(0, sys.argv[4])

    from src.core.state_store import CapacityExceeded, SQLiteStateStore

    async def main():
        db_path, key, limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
        barrier = sys.argv[5]
        while not Path(barrier).exists():
            await asyncio.sleep(0.002)
        store = SQLiteStateStore(db_path)
        await store.initialize()
        try:
            await store.reserve_work(
                reservation_key=key,
                scope_key="race/scope",
                owner_id=key,
                capacity_limit=limit,
                lease_seconds=120.0,
            )
            print("ADMITTED")
        except CapacityExceeded:
            print("REJECTED")
        finally:
            await store.close()

    asyncio.run(main())
    """
)


def test_admission_race_with_real_separate_processes(tmp_path):
    """Real competing OS processes against one shared database.

    Exactly the configured global limit may be admitted; the rest must be
    rejected before any side effect, so simultaneous requests through two
    workers can never exceed the configured global limit.
    """
    db_path = tmp_path / "shared.db"
    barrier = tmp_path / "go"
    script = tmp_path / "worker.py"
    script.write_text(_WORKER_SCRIPT)
    limit = 2
    workers = 6
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                str(script),
                str(db_path),
                f"work-{i}",
                str(limit),
                str(REPO_ROOT),
                str(barrier),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(workers)
    ]
    barrier.write_text("go")
    outputs = []
    for proc in procs:
        out, err = proc.communicate(timeout=120)
        assert proc.returncode == 0, err
        outputs.append(out.strip())
    admitted = sum(1 for line in outputs if line == "ADMITTED")
    assert admitted == limit, outputs
    assert outputs.count("REJECTED") == workers - limit, outputs


@pytest.mark.asyncio
async def test_stale_owner_cannot_publish_evidence_or_promotion_effects(tmp_path):
    store = await _open_store(tmp_path)
    try:
        await _make_session(store, "res_1")
        # the admitted owner writes with the epoch it was granted
        await store.add_iteration(
            research_id="res_1", iteration=1,
            lock_epoch=0, **ITERATION_KW,
        )
        # ownership changes hands: the epoch moves forward monotonically
        await store.bump_session_epoch("res_1")

        with pytest.raises(StaleFenceError):
            await store.add_iteration(
                research_id="res_1", iteration=2,
                lock_epoch=0, **ITERATION_KW,
            )
        promo_target = tmp_path / "t.yaml"
        promo_target.write_text("x: 1\n")
        with pytest.raises(StaleFenceError):
            await store.record_promotion(
                research_id="res_1",
                iteration=1,
                model_type="trend",
                instrument="EURUSD",
                timeframe="1h",
                target_path=str(promo_target),
                config_yaml="x: 2\n",
                previous_yaml="x: 1\n",
                lock_epoch=0,
            )
        promo = await store.record_promotion(
            research_id="res_1",
            iteration=1,
            model_type="trend",
            instrument="EURUSD",
            timeframe="1h",
            target_path=str(promo_target),
            config_yaml="x: 2\n",
            previous_yaml="x: 1\n",
            lock_epoch=1,
        )
        with pytest.raises(StaleFenceError):
            await store.update_promotion_metadata(
                promotion_id=int(promo["id"]),
                promotion_metadata={"effect": {"status": "confirmed"}},
                lock_epoch=0,
            )
        # the current owner's writes still land
        updated = await store.update_promotion_metadata(
            promotion_id=int(promo["id"]),
            promotion_metadata={"effect": {"status": "confirmed"}},
            lock_epoch=1,
        )
        assert updated is not None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_lease_expiry_reclaim_bumps_epoch_and_frees_capacity(tmp_path):
    store = await _open_store(tmp_path)
    try:
        await store.reserve_work(
            reservation_key="work-a",
            scope_key="scope",
            owner_id="worker-1",
            capacity_limit=1,
            lease_seconds=0.05,
        )
        with pytest.raises(CapacityExceeded):
            await store.reserve_work(
                reservation_key="work-b",
                scope_key="scope",
                owner_id="worker-2",
                capacity_limit=1,
                lease_seconds=60.0,
            )
        await asyncio.sleep(0.1)

        # a live worker's lease must not be reclaimed
        reclaimed = await store.reclaim_expired_reservations()
        assert [r["reservation_key"] for r in reclaimed] == ["work-a"]
        assert reclaimed[0]["state"] == "released"

        # capacity is free again and a stale renewal cannot resurrect the lease
        assert await store.renew_work_lease(
            reservation_key="work-a", owner_id="worker-1", lease_seconds=60.0,
        ) is False
        again = await store.reserve_work(
            reservation_key="work-b",
            scope_key="scope",
            owner_id="worker-2",
            capacity_limit=1,
            lease_seconds=60.0,
        )
        assert again["state"] == "reserved"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_live_lease_survives_reclaim_and_renews(tmp_path):
    store = await _open_store(tmp_path)
    try:
        await store.reserve_work(
            reservation_key="work-a",
            scope_key="scope",
            owner_id="worker-1",
            capacity_limit=2,
            lease_seconds=60.0,
        )
        assert await store.renew_work_lease(
            reservation_key="work-a", owner_id="worker-1", lease_seconds=120.0,
        ) is True
        # a foreign owner cannot renew someone else's lease
        assert await store.renew_work_lease(
            reservation_key="work-a", owner_id="worker-2", lease_seconds=120.0,
        ) is False
        assert await store.reclaim_expired_reservations() == []
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_orphan_classification_never_takes_a_live_workers_session(tmp_path):
    store = await _open_store(tmp_path)
    manager = SessionManager(store)
    try:
        session = await _make_session(store, "res_live")
        await store.reserve_work(
            reservation_key="res_live",
            scope_key="trend/EURUSD/1h",
            owner_id="another-worker",
            capacity_limit=4,
            lease_seconds=60.0,
        )
        running = dict(session, status="running")
        classification = await manager._classify_orphaned_session(running)
        assert classification["orphaned"] is False
        assert classification["status"] == "owned_elsewhere"

        # an expired lease (crashed worker) is a real orphan candidate
        await store.reserve_work(
            reservation_key="res_dead",
            scope_key="trend/EURUSD/1h",
            owner_id="crashed-worker",
            capacity_limit=4,
            lease_seconds=0.01,
        )
        session_dead = await _make_session(store, "res_dead")
        await asyncio.sleep(0.05)
        dead = dict(session_dead, status="running")
        classification = await manager._classify_orphaned_session(dead)
        assert classification["orphaned"] is True
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_failed_start_releases_its_reservation(tmp_path, monkeypatch):
    store = await _open_store(tmp_path)
    manager = SessionManager(store)
    try:

        async def boom(config):
            raise RuntimeError("bootstrap failed")

        monkeypatch.setattr(manager, "_run_preflight", boom)
        monkeypatch.setattr(manager, "_validate_session_skill", lambda config: None)
        with pytest.raises(RuntimeError, match="bootstrap failed"):
            await manager.start_session(
                instrument="EURUSD",
                timeframe="1h",
                model_type="trend",
                skill_id="baseline-trend",
                skill_params={},
                subject_id="EURUSD",
                variant="1h",
            )
        manager_reservations = [
            row
            async for row in _iter_reservations(store)
        ]
        assert manager_reservations, "the failed start must leave a reservation row"
        assert all(
            state == "released" for _, state in manager_reservations
        ), manager_reservations
    finally:
        await store.close()


async def _iter_reservations(store):
    async with store.connection() as db:
        db.row_factory = __import__("aiosqlite").Row
        rows = await (
            await db.execute("SELECT reservation_key, state FROM work_reservations")
        ).fetchall()
    for row in rows:
        yield row["reservation_key"], row["state"]


@pytest.mark.asyncio
@pytest.mark.skipif(
    "not os.environ.get('AUTORESEARCH_DATABASE_URL')",
    reason="Postgres test legs require AUTORESEARCH_DATABASE_URL",
)
async def test_reservation_contract_on_postgres_store(tmp_path):
    """The same admission and fencing contract holds on the shared store."""
    from src.core.postgres_state_store import build_state_store

    store = build_state_store()
    await store.initialize()
    try:
        first = await store.reserve_work(
            reservation_key="pg-work-a",
            scope_key="scope",
            owner_id="worker-1",
            capacity_limit=1,
            lease_seconds=60.0,
        )
        assert first["state"] == "reserved"
        with pytest.raises(CapacityExceeded):
            await store.reserve_work(
                reservation_key="pg-work-b",
                scope_key="scope",
                owner_id="worker-2",
                capacity_limit=1,
                lease_seconds=60.0,
            )
        assert await store.release_work("pg-work-a") is True
        again = await store.reserve_work(
            reservation_key="pg-work-a",
            scope_key="scope",
            owner_id="worker-2",
            capacity_limit=1,
            lease_seconds=60.0,
        )
        assert int(again["epoch"]) == int(first["epoch"]) + 1
    finally:
        await store.release_work("pg-work-a")
        await store.close()
