"""Tests for the autoresearch-agent hardening backlog (phases 1–5).

These tests target the focused behaviors changed in the hardening pass
documented in ``docs/ml/autoresearch_agent_hardening_backlog.md``. Each
test exercises the surface that changed; full integration smoke tests
of the agent loop are out of scope for this file.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.api.promotion import PromotionApproval, PromotionScopeRequest
from src.core.config_promoter import _atomic_write_text
from src.core.results_store import ResultsStore, _add_column_if_missing
from src.ws.events import EventBroadcaster

# ---------------------------------------------------------------------------
# Phase 1.3 — _add_column_if_missing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_column_if_missing_is_idempotent(tmp_path: Path) -> None:
    import aiosqlite

    db_path = tmp_path / "t.db"
    async with aiosqlite.connect(db_path) as db:
        await db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        await _add_column_if_missing(db, "t", "name TEXT")
        # Second call must be a no-op, not raise duplicate-column.
        await _add_column_if_missing(db, "t", "name TEXT")
        cursor = await db.execute("PRAGMA table_info(t)")
        cols = {row[1] for row in await cursor.fetchall()}
    assert {"id", "name"}.issubset(cols)


@pytest.mark.asyncio
async def test_add_column_if_missing_propagates_real_errors(tmp_path: Path) -> None:
    import aiosqlite

    db_path = tmp_path / "t.db"
    async with aiosqlite.connect(db_path) as db:
        await db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        with pytest.raises(aiosqlite.Error):
            # Invalid column definition: real OperationalError must escape.
            await _add_column_if_missing(db, "t", "bad column ((((")


# ---------------------------------------------------------------------------
# Phase 3.1 — atomic config promotion
# ---------------------------------------------------------------------------


def test_atomic_write_text_replaces_existing(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text("old\n")
    _atomic_write_text(str(target), "new\n")
    assert target.read_text() == "new\n"
    # No leftover .tmp files
    leftovers = [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_atomic_write_text_creates_parent(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "x.json"
    _atomic_write_text(str(target), "{}")
    assert target.read_text() == "{}"


# ---------------------------------------------------------------------------
# Phase 3.2 — production-scope approval enforcement
# ---------------------------------------------------------------------------


def test_production_scope_requires_full_approval() -> None:
    with pytest.raises(ValidationError):
        PromotionScopeRequest(scope="production")


def test_production_scope_rejects_partial_approval() -> None:
    with pytest.raises(ValidationError):
        PromotionScopeRequest(
            scope="production",
            approval=PromotionApproval(approved=True, approver="alice"),
        )


def test_production_scope_accepts_full_approval() -> None:
    req = PromotionScopeRequest(
        scope="production",
        approval=PromotionApproval(
            approved=True,
            approver="alice",
            signature="sig",
            method="hsm",
        ),
    )
    assert req.scope == "production"


def test_development_scope_does_not_require_approval() -> None:
    PromotionScopeRequest(scope="development")  # must not raise


# ---------------------------------------------------------------------------
# Phase 4.1 — EventBroadcaster lock + snapshot
# ---------------------------------------------------------------------------


class _FakeWS:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[str] = []

    async def accept(self, *, subprotocol: str | None = None) -> None:
        return None

    async def send_text(self, payload: str) -> None:
        if self.fail:
            raise RuntimeError("dead socket")
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_broadcaster_drops_dead_clients_under_concurrent_churn() -> None:
    bc = EventBroadcaster()
    ws_alive = _FakeWS()
    ws_dead = _FakeWS(fail=True)
    await bc.connect(ws_alive)
    await bc.connect(ws_dead)
    # Concurrent broadcast and disconnect must not raise.
    await asyncio.gather(
        bc.broadcast({"event": "x"}),
        bc.disconnect(ws_dead),
    )
    assert ws_alive.sent  # alive socket received at least one event
    assert bc.client_count <= 1


# ---------------------------------------------------------------------------
# Phase 4.5 + 5.1 — list_sessions filtering and pagination
# ---------------------------------------------------------------------------


@pytest.fixture
async def store(tmp_path: Path) -> ResultsStore:
    db_path = tmp_path / "rs.db"
    s = ResultsStore(db_path=str(db_path))
    await s.initialize()
    return s


@pytest.mark.asyncio
async def test_list_sessions_status_in_filters_at_sql_level(store: ResultsStore) -> None:
    common = dict(
        instrument="DOGEUSDT",
        timeframe="15m",
        model_type="direction",
        tag="t",
        quick_mode=False,
        max_iterations=1,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path="/tmp/ws",
    )
    await store.create_session(session_id="r_running", **common)
    await store.create_session(session_id="r_done", **common)
    await store.update_session("r_done", status="completed")
    await store.create_session(session_id="r_failed", **common)
    await store.update_session("r_failed", status="failed")

    rows = await store.list_sessions(status_in=("running", "paused"))
    ids = {r["id"] for r in rows}
    assert "r_running" in ids
    assert "r_done" not in ids
    assert "r_failed" not in ids


@pytest.mark.asyncio
async def test_results_store_records_schema_version(store: ResultsStore) -> None:
    assert await store.get_schema_version() == 1


@pytest.mark.asyncio
async def test_list_sessions_pagination(store: ResultsStore) -> None:
    common = dict(
        instrument="BTCUSDT",
        timeframe="15m",
        model_type="direction",
        tag="t",
        quick_mode=False,
        max_iterations=1,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path="/tmp/ws",
    )
    for i in range(5):
        await store.create_session(session_id=f"r_{i}", **common)

    page1 = await store.list_sessions(limit=2, offset=0)
    page2 = await store.list_sessions(limit=2, offset=2)
    total = await store.count_sessions()
    assert len(page1) == 2
    assert len(page2) == 2
    assert {r["id"] for r in page1}.isdisjoint({r["id"] for r in page2})
    assert total == 5
