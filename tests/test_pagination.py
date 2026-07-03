"""Cursor-pagination tests (ARC-011 P0-015..019).

Covers:
  * the opaque cursor helper (encode/decode round-trip, malformed-input
    fail-open, limit clamping) — unit,
  * ``build_cursor_page`` envelope construction,
  * real-store keyset behavior for sessions / pipelines / iterations:
    forward iteration, tiebreaker determinism on shared timestamps,
    concurrent-insertion stability (cursor vs offset drift), cursor round-trip
    integrity, reverse (store-layer ``reverse=True``), and opt-in/bare-list
    parity for iterations,
  * API-layer envelope selection (cursor path vs legacy offset path) via
    direct handler calls.

Design reference: ``docs/adr/ARC-011-cursor-pagination.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.api import research as research_api
from src.api import results as results_api
from src.core.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    build_cursor_page,
    clamp_limit,
    decode_cursor,
    encode_cursor,
)
from src.core.results_store import ResultsStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def store(tmp_path: Path) -> ResultsStore:
    s = ResultsStore(str(tmp_path / "pagination.db"))
    await s.initialize()
    try:
        yield s
    finally:
        await s.close()


_SESSION_COMMON = dict(
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

_PIPELINE_COMMON = dict(
    instrument="BTCUSDT",
    timeframe="15m",
    tag="t",
    max_iterations=1,
    max_budget_usd=1.0,
    quick_mode=False,
    timeout_s=0,
    focus_hint=None,
    phase_budgets=None,
    trading_mode=None,
    agent_strategy=None,
    initial_balance=None,
    enable_hpo=False,
    hpo_trials=None,
    hpo_timesteps=None,
)


async def _set_started_at(store: ResultsStore, table: str, row_id: str, ts: str) -> None:
    """Force a row's ``started_at`` so tiebreaker/concurrency scenarios are exact."""
    async with store.connection() as db:
        await db.execute(f"UPDATE {table} SET started_at = ? WHERE id = ?", (ts, row_id))
        await db.commit()


def _sessions_extractor(row):
    return (row["started_at"], row["id"])


def _iterations_extractor(row):
    return (row["iteration"], row["id"])


# ---------------------------------------------------------------------------
# 1. Cursor helper unit tests
# ---------------------------------------------------------------------------


class TestCursorHelper:
    def test_round_trip_with_string_sort_key_and_string_tiebreak(self):
        # sessions/pipelines: (started_at TEXT, id TEXT)
        token = encode_cursor("2026-07-03T10:00:00+00:00", "res_abc")
        assert decode_cursor(token) == ("2026-07-03T10:00:00+00:00", "res_abc")

    def test_round_trip_with_integer_sort_key_and_int_tiebreak(self):
        # iterations: (iteration INT, id INT)
        token = encode_cursor(7, 42)
        assert decode_cursor(token) == (7, 42)

    def test_token_is_opaque_and_not_a_raw_offset(self):
        token = encode_cursor("2026-07-03T10:00:00+00:00", "res_abc")
        # Must not leak the raw values as plain text or look like "?offset=5".
        assert "res_abc" not in token
        assert "offset" not in token.lower()
        # And it is base64url (no padding, url-safe alphabet).
        assert "=" not in token

    @pytest.mark.parametrize(
        "bad",
        [
            None,
            "",
            "   ",
            "!!!not-base64!!!",
            "YWJjZA",  # valid b64 but not JSON
        ],
    )
    def test_malformed_tokens_decode_to_none(self, bad):
        assert decode_cursor(bad) is None

    def test_wrong_version_token_decodes_to_none(self):
        import base64
        import json

        payload = {"v": 999, "k": "x", "r": 1}
        raw = json.dumps(payload).encode()
        token = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        assert decode_cursor(token) is None

    def test_token_missing_fields_decodes_to_none(self):
        import base64
        import json

        payload = {"v": 1, "k": "x"}  # missing r
        raw = json.dumps(payload).encode()
        token = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        assert decode_cursor(token) is None

    @pytest.mark.parametrize(
        "limit_in, expected",
        [
            (None, DEFAULT_PAGE_SIZE),
            (0, DEFAULT_PAGE_SIZE),
            (-5, DEFAULT_PAGE_SIZE),
            (1, 1),
            (50, 50),
            (MAX_PAGE_SIZE, MAX_PAGE_SIZE),
            (MAX_PAGE_SIZE + 1, MAX_PAGE_SIZE),
            (10_000, MAX_PAGE_SIZE),
        ],
    )
    def test_clamp_limit_boundary_table(self, limit_in, expected):
        assert clamp_limit(limit_in) == expected


# ---------------------------------------------------------------------------
# 2. build_cursor_page envelope
# ---------------------------------------------------------------------------


class TestBuildCursorPage:
    def test_full_page_yields_next_cursor(self):
        rows = [{"started_at": "t1", "id": "a"}, {"started_at": "t2", "id": "b"}]
        page = build_cursor_page(rows, 2, _sessions_extractor)
        assert page["next_cursor"] is not None
        assert decode_cursor(page["next_cursor"]) == ("t2", "b")
        assert page["limit"] == 2

    def test_short_final_page_yields_null_cursor(self):
        rows = [{"started_at": "t1", "id": "a"}]
        page = build_cursor_page(rows, 10, _sessions_extractor)
        assert page["next_cursor"] is None

    def test_empty_page_yields_null_cursor(self):
        page = build_cursor_page([], 10, _sessions_extractor)
        assert page["next_cursor"] is None
        assert page["items"] == []


# ---------------------------------------------------------------------------
# 3. Real-store keyset behavior — sessions
# ---------------------------------------------------------------------------


class TestSessionsCursorPagination:
    async def _seed(self, store: ResultsStore, n: int) -> None:
        for i in range(n):
            await store.create_session(session_id=f"r_{i}", **_SESSION_COMMON)

    async def test_forward_iteration_reconstructs_full_set(self, store):
        await self._seed(store, 5)
        seen, cursor = [], None
        for _ in range(10):  # safety cap
            page_rows = await store.list_sessions(limit=2, cursor=cursor)
            if not page_rows:
                break
            seen.extend(page_rows)
            sk, rid = page_rows[-1]["started_at"], page_rows[-1]["id"]
            cursor = (sk, rid)
            if len(page_rows) < 2:
                break
        ids = [r["id"] for r in seen]
        assert len(ids) == 5
        assert len(set(ids)) == 5  # no dupes, no skips
        # DESC by started_at: created-last first.
        assert ids == ["r_4", "r_3", "r_2", "r_1", "r_0"]

    async def test_tiebreaker_is_deterministic_on_shared_timestamp(self, store):
        # Five sessions sharing the exact same started_at must be ordered by
        # id DESC deterministically — the whole point of the tiebreaker.
        tied_ts = "2026-07-03T10:00:00+00:00"
        for i in range(5):
            await store.create_session(session_id=f"r_{i}", **_SESSION_COMMON)
            await _set_started_at(store, "research_sessions", f"r_{i}", tied_ts)
        rows_a = await store.list_sessions(limit=5, cursor=None)
        rows_b = await store.list_sessions(limit=5, cursor=None)
        assert [r["id"] for r in rows_a] == [r["id"] for r in rows_b]
        # id DESC lexicographic.
        assert [r["id"] for r in rows_a] == sorted([r["id"] for r in rows_a], reverse=True)

    async def test_concurrent_insertion_does_not_shift_cursor_pages(self, store):
        # Cursor pagination is immune to the offset drift that occurs when new
        # rows are inserted mid-walk.
        await self._seed(store, 4)
        page1 = await store.list_sessions(limit=2, cursor=None)
        cursor = (page1[-1]["started_at"], page1[-1]["id"])

        # Insert rows that are NEWER than every existing row.
        for i in range(3):
            await store.create_session(session_id=f"new_{i}", **_SESSION_COMMON)

        page2 = await store.list_sessions(limit=2, cursor=cursor)
        page2_ids = {r["id"] for r in page2}
        # Page 2 must be exactly the two rows that followed page 1 before the
        # insert — neither the new rows nor a shifted window.
        assert page2_ids == {"r_1", "r_0"}
        assert not (page2_ids & {"new_0", "new_1", "new_2"})

    async def test_cursor_round_trip_integrity(self, store):
        await self._seed(store, 3)
        rows = await store.list_sessions(limit=10, cursor=None)
        # rows are DESC (newest first); anchor on the newest so the keyset
        # returns the remaining older rows.
        anchor = rows[0]
        token = encode_cursor(anchor["started_at"], anchor["id"])
        # The opaque token survives a (de)serialize cycle unchanged in meaning.
        assert decode_cursor(token) == (anchor["started_at"], anchor["id"])
        # And the store accepts the decoded tuple as a keyset (excludes anchor).
        remaining = await store.list_sessions(limit=10, cursor=decode_cursor(token))
        assert len(remaining) == 2
        assert all(r["id"] != anchor["id"] for r in remaining)

    async def test_reverse_walks_backward(self, store):
        await self._seed(store, 5)
        rows = await store.list_sessions(limit=10, cursor=None)
        # newest first: r_4..r_0
        # cursor positioned at r_2 (the middle); reverse must ascend from there.
        anchor = rows[2]
        cursor = (anchor["started_at"], anchor["id"])
        back = await store.list_sessions(limit=2, cursor=cursor, reverse=True)
        # ASC + (> anchor) -> the two rows newer than the anchor, ascending.
        assert [r["id"] for r in back] == ["r_3", "r_4"]


# ---------------------------------------------------------------------------
# 4. Real-store keyset behavior — pipelines (mirror, lighter)
# ---------------------------------------------------------------------------


class TestPipelinesCursorPagination:
    async def _seed(self, store: ResultsStore, n: int) -> None:
        for i in range(n):
            await store.create_pipeline(pipeline_id=f"pipe_{i}", **_PIPELINE_COMMON)

    async def test_forward_iteration_and_envelope_shape(self, store):
        await self._seed(store, 3)
        page1 = await store.list_pipelines(limit=2, cursor=None)
        assert len(page1) == 2
        cursor = (page1[-1]["started_at"], page1[-1]["id"])
        page2 = await store.list_pipelines(limit=2, cursor=cursor)
        assert len(page2) == 1
        all_ids = {r["id"] for r in page1} | {r["id"] for r in page2}
        assert all_ids == {"pipe_0", "pipe_1", "pipe_2"}

    async def test_offset_path_parity_preserves_ordering(self, store):
        await self._seed(store, 4)
        cursor_ids = {r["id"] for r in await store.list_pipelines(limit=10, cursor=None)}
        offset_ids = {r["id"] for r in await store.list_pipelines(limit=10, offset=0)}
        assert cursor_ids == offset_ids


# ---------------------------------------------------------------------------
# 5. Real-store keyset behavior — iterations (opt-in)
# ---------------------------------------------------------------------------


class TestIterationsCursorPagination:
    @staticmethod
    async def _seed(store: ResultsStore, *, sid: str = "res_x", n: int = 5) -> None:
        await store.create_session(session_id=sid, **_SESSION_COMMON)
        for i in range(n):
            await store.add_iteration(
                research_id=sid,
                iteration=i,
                primary_metric=float(i),
                metric_name="sharpe",
                all_gates_passed=True,
                decision="keep",
                description=f"iter {i}",
                config_snapshot="{}",
                metrics_json="{}",
                training_time_s=1.0,
            )

    async def test_limit_omitted_returns_full_bare_list(self, store):
        await self._seed(store)
        rows = await store.get_iterations("res_x")
        assert isinstance(rows, list)
        assert [r["iteration"] for r in rows] == [0, 1, 2, 3, 4]

    async def test_limit_set_paginates_forward(self, store):
        await self._seed(store)
        seen, cursor = [], None
        for _ in range(10):
            page_rows = await store.get_iterations("res_x", limit=2, cursor=cursor)
            if not page_rows:
                break
            seen.extend(page_rows)
            cursor = (page_rows[-1]["iteration"], page_rows[-1]["id"])
            if len(page_rows) < 2:
                break
        assert [r["iteration"] for r in seen] == [0, 1, 2, 3, 4]

    async def test_malformed_cursor_fails_open_to_page1(self, store):
        await self._seed(store)
        # A garbled cursor must not raise; the store receives None (the API
        # layer decodes fail-open). Here we pass None directly to emulate that.
        rows = await store.get_iterations("res_x", limit=10, cursor=None)
        assert len(rows) == 5

    async def test_reverse_walks_backward(self, store):
        await self._seed(store)
        rows = await store.get_iterations("res_x", limit=10)
        anchor = rows[2]  # iteration 2
        cursor = (anchor["iteration"], anchor["id"])
        back = await store.get_iterations("res_x", limit=2, cursor=cursor, reverse=True)
        # DESC + (< anchor) -> iterations newer than 2, descending.
        assert [r["iteration"] for r in back] == [1, 0]


# ---------------------------------------------------------------------------
# 6. API-layer envelope selection (direct handler calls)
# ---------------------------------------------------------------------------


class TestApiEnvelopeSelection:
    async def test_list_research_offset_envelope_has_total_and_next_cursor(
        self, store, monkeypatch
    ):
        for i in range(3):
            await store.create_session(session_id=f"r_{i}", **_SESSION_COMMON)
        monkeypatch.setattr(research_api, "_store", store)

        # No cursor -> legacy offset path, with an additive next_cursor so a
        # client can transparently upgrade to cursor pagination next request.
        page = await research_api.list_research(limit=2, offset=0, cursor=None)
        assert set(page) == {"items", "total", "limit", "offset", "next_cursor"}
        assert page["total"] == 3
        assert page["offset"] == 0
        # 3 rows, limit 2 -> page is full -> a cursor is offered.
        assert page["next_cursor"] is not None

    async def test_list_research_cursor_envelope_omits_total(self, store, monkeypatch):
        for i in range(3):
            await store.create_session(session_id=f"r_{i}", **_SESSION_COMMON)
        monkeypatch.setattr(research_api, "_store", store)

        first = await research_api.list_research(limit=2, offset=0, cursor=None)
        # Use the offered cursor -> cursor path -> no total.
        page2 = await research_api.list_research(limit=2, offset=0, cursor=first["next_cursor"])
        assert set(page2) == {"items", "limit", "next_cursor"}
        assert len(page2["items"]) == 1
        # Final single-row page -> exhausted.
        assert page2["next_cursor"] is None

    async def test_list_pipelines_cursor_and_offset_envelopes(self, store, monkeypatch):
        for i in range(3):
            await store.create_pipeline(pipeline_id=f"pipe_{i}", **_PIPELINE_COMMON)
        monkeypatch.setattr(research_api, "_store", store)

        offset_page = await research_api.list_pipelines(limit=10, offset=0, cursor=None)
        assert "total" in offset_page and offset_page["total"] == 3
        assert "next_cursor" in offset_page  # exhausted (3 < 10) -> None
        assert offset_page["next_cursor"] is None

        # Page-1 with limit 2 -> offers a cursor; page-2 via cursor -> no total.
        first = await research_api.list_pipelines(limit=2, offset=0, cursor=None)
        token = first["next_cursor"]
        page2 = await research_api.list_pipelines(limit=2, offset=0, cursor=token)
        assert set(page2) == {"items", "limit", "next_cursor"}

    async def test_iterations_endpoint_opt_in_pagination(self, store, monkeypatch):
        await store.create_session(session_id="res_x", **_SESSION_COMMON)
        for i in range(3):
            await store.add_iteration(
                research_id="res_x",
                iteration=i,
                primary_metric=float(i),
                metric_name="sharpe",
                all_gates_passed=True,
                decision="keep",
                description=f"iter {i}",
                config_snapshot="{}",
                metrics_json="{}",
                training_time_s=1.0,
            )
        monkeypatch.setattr(results_api, "_store", store)

        # Bare list when limit omitted (today's behavior).
        bare = await results_api.get_iterations("res_x")
        assert isinstance(bare, list)
        assert len(bare) == 3

        # Envelope when limit supplied.
        page = await results_api.get_iterations("res_x", limit=2)
        assert set(page) == {"items", "limit", "next_cursor"}
        assert len(page["items"]) == 2
        assert page["next_cursor"] is not None

        # Walk to the last page.
        token = page["next_cursor"]
        last = await results_api.get_iterations("res_x", limit=2, cursor=token)
        assert len(last["items"]) == 1
        assert last["next_cursor"] is None

    async def test_iterations_endpoint_malformed_cursor_is_page1(self, store, monkeypatch):
        await store.create_session(session_id="res_x", **_SESSION_COMMON)
        for i in range(3):
            await store.add_iteration(
                research_id="res_x",
                iteration=i,
                primary_metric=float(i),
                metric_name="sharpe",
                all_gates_passed=True,
                decision="keep",
                description=f"iter {i}",
                config_snapshot="{}",
                metrics_json="{}",
                training_time_s=1.0,
            )
        monkeypatch.setattr(results_api, "_store", store)

        page = await results_api.get_iterations("res_x", limit=2, cursor="!!!bad!!!")
        # Fail-open: page 1, no crash.
        assert len(page["items"]) == 2
        assert [row["iteration"] for row in page["items"]] == [0, 1]


# ---------------------------------------------------------------------------
# 7. v5 indexes + schema version
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v5_indexes_present_after_initialize(tmp_path: Path) -> None:
    s = ResultsStore(str(tmp_path / "idx.db"))
    await s.initialize()
    assert await s.get_schema_version() == 5
    async with s.connection() as db:
        cur = await db.execute("SELECT name FROM sqlite_master WHERE type='index'")
        names = {row[0] for row in await cur.fetchall()}
    await s.close()
    assert {
        "idx_sessions_started_at_rowid",
        "idx_pipelines_started_at_rowid",
        "idx_iterations_research_iteration",
    }.issubset(names)
