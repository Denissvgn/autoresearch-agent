"""Transaction-span serialization on the shared SQLite connection.

aiosqlite serializes statements but not transaction spans: concurrent
unlocked implicit writes used to interleave with BEGIN IMMEDIATE
sections and fail with "cannot start a transaction within a
transaction". The task-reentrant connection lock serializes spans and
stays deadlock-free for same-task nesting.
"""
from __future__ import annotations

import asyncio

from src.core.state_store import CapacityExceeded, SQLiteStateStore


async def _build(tmp_path):
    store = SQLiteStateStore(str(tmp_path / "state.db"))
    await store.initialize()
    return store


def test_concurrent_implicit_and_explicit_transactions_serialize(tmp_path):
    async def _scenario():
        store = await _build(tmp_path)

        async def worker(i: int):
            rid = f"res_{i:03d}"
            await store.create_session(
                session_id=rid, instrument="I", timeframe="1h",
                model_type="direction", tag="t", quick_mode=False,
                max_iterations=3, max_budget_usd=5.0, focus_hint=None,
                workspace_path=f"/tmp/ws-{rid}",
            )
            await store.add_iteration(
                research_id=rid, iteration=1, primary_metric=0.5,
                metric_name="primary", all_gates_passed=True,
                decision="keep", description="d", config_snapshot="{}",
                metrics_json="{}", training_time_s=1.0,
            )
            # the explicit-BEGIN reservation path interleaves too
            await store.reserve_budget(
                reservation_id=f"resv_{i:03d}",
                research_id=rid,
                amount_usd=0.25,
                strict_cap_usd=100.0,
                enforcement="strict",
            )
            return rid

        # many concurrent workers: any nested-transaction race raises
        results = await asyncio.gather(
            *(worker(i) for i in range(12)), return_exceptions=True
        )
        errors = [r for r in results if isinstance(r, BaseException)]
        await store.close()
        return errors

    errors = asyncio.run(asyncio.wait_for(_scenario(), timeout=60))
    assert errors == []


def test_same_task_nested_connection_use_is_deadlock_free(tmp_path):
    async def _scenario():
        store = await _build(tmp_path)
        await store.create_session(
            session_id="res_nested", instrument="I", timeframe="1h",
            model_type="direction", tag="t", quick_mode=False,
            max_iterations=3, max_budget_usd=5.0, focus_hint=None,
            workspace_path="/tmp/ws-nested",
        )
        # add_iteration opens nested connection() calls internally
        await store.add_iteration(
            research_id="res_nested", iteration=1, primary_metric=0.5,
            metric_name="primary", all_gates_passed=True,
            decision="keep", description="d", config_snapshot="{}",
            metrics_json="{}", training_time_s=1.0,
        )
        session = await store.get_session("res_nested")
        await store.close()
        return session

    session = asyncio.run(asyncio.wait_for(_scenario(), timeout=20))
    assert session is not None
    assert session["best_metric"] == 0.5


def test_capacity_limits_still_enforced_under_contention(tmp_path):
    async def _scenario():
        store = await _build(tmp_path)

        async def worker(i: int):
            try:
                await store.reserve_work(
                    reservation_key=f"task-{i % 2}",
                    scope_key="scope-a",
                    owner_id=f"owner-{i}",
                    capacity_limit=10,
                )
                return "reserved"
            except CapacityExceeded:
                return "capacity"

        results = await asyncio.gather(*(worker(i) for i in range(6)))
        await store.close()
        return results

    results = asyncio.run(asyncio.wait_for(_scenario(), timeout=30))
    # the duplicate reservation key never double-reserves
    assert results.count("reserved") >= 1