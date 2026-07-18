"""Tests for ARC-011 P0-008 / P0-009 / P0-010 — migration error surfacing.

P0-009's target (a bare ``try/except Exception: pass`` over ``ALTER TABLE``)
was already removed in commit 3c47c1e34 (Phase 1.3 hardening) and replaced
with ``_add_column_if_missing`` — a ``PRAGMA table_info`` pre-check (LBYL)
that lets genuine ``OperationalError`` propagate. These tests pin that
behavior, the migration runner's idempotency, the version-skew guard, and the
ARC-011 P0-008 de-duplication (evolutionary columns live in the migration as
the single source of truth, not the bootstrap ``_SCHEMA_SQL``).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

import aiosqlite
import pytest

from src.core.results_store import (
    _LATEST_SCHEMA_VERSION,
    ResultsStore,
    _add_column_if_missing,
    _set_schema_version,
)
from src.core.state_store import (
    _MIGRATIONS,
    _SCHEMA_SQL,
    _get_schema_version,
    _migrate_to_v1,
)

# ---------------------------------------------------------------------------
# P0-009 — _add_column_if_missing (LBYL pre-check; real errors propagate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_column_if_missing_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "idem_cols.sqlite"
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
    db_path = tmp_path / "real_err.sqlite"
    async with aiosqlite.connect(db_path) as db:
        await db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        with pytest.raises(aiosqlite.Error):
            # Invalid column definition: a genuine OperationalError must escape
            # (not be swallowed by an idempotency guard).
            await _add_column_if_missing(db, "t", "bad column ((((")


# ---------------------------------------------------------------------------
# P0-010 — initialize() idempotency + version-skew guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_is_idempotent(tmp_path: Path) -> None:
    """initialize() twice (same store re-runs, and a reopened DB) is a no-op."""
    db_path = tmp_path / "idem_init.sqlite"
    store = ResultsStore(str(db_path))
    await store.initialize()
    version_after_first = await store.get_schema_version()
    # initialize() closes + reopens internally when _conn is already set.
    await store.initialize()
    version_after_second = await store.get_schema_version()
    await store.close()

    # A second store on the same DB file must also be a clean no-op.
    store2 = ResultsStore(str(db_path))
    await store2.initialize()
    version_after_reopen = await store2.get_schema_version()
    await store2.close()

    assert version_after_first == _LATEST_SCHEMA_VERSION
    assert {version_after_first, version_after_second, version_after_reopen} == {
        _LATEST_SCHEMA_VERSION,
    }


@pytest.mark.asyncio
async def test_initialize_rejects_newer_schema(tmp_path: Path) -> None:
    """A schema_version newer than supported must fail loudly, not silently migrate."""
    db_path = tmp_path / "skew.sqlite"
    store = ResultsStore(str(db_path))
    await store.initialize()
    await store.close()

    # Forge a version from the future.
    async with aiosqlite.connect(str(db_path)) as db:
        await _set_schema_version(db, _LATEST_SCHEMA_VERSION + 1)
        await db.commit()

    future_store = ResultsStore(str(db_path))
    with pytest.raises(RuntimeError, match="newer than supported"):
        await future_store.initialize()


@pytest.mark.asyncio
async def test_fresh_db_migrates_to_latest_with_evolutionary_columns(
    tmp_path: Path,
) -> None:
    """A fresh DB reaches the latest version and the evolutionary columns that
    ARC-011 P0-008 moved out of the bootstrap (single source of truth = the
    migration) are present — i.e. _migrate_to_v1 still adds them for fresh DBs."""
    db_path = tmp_path / "fresh.sqlite"
    store = ResultsStore(str(db_path))
    await store.initialize()
    assert await store.get_schema_version() == _LATEST_SCHEMA_VERSION
    await store.close()

    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute("PRAGMA table_info(research_sessions)")
        cols = {row[1] for row in await cursor.fetchall()}

    evolutionary = {
        "manifest_json",
        "manifest_path",
        "manifest_hash",
        "current_phase",
        "next_action",
        "phase_state_json",
    }
    assert evolutionary.issubset(cols), evolutionary - cols


@pytest.mark.asyncio
async def test_v6_migration_adds_canonical_skill_columns(tmp_path: Path) -> None:
    """P3-019: v6 migration adds ``skill_id``, ``subject_id``, ``variant``
    columns to ``research_sessions`` so the canonical shape is persisted
    (not just synthesized at read time). Idempotent and defaults to empty
    string for existing rows."""
    db_path = tmp_path / "v6.sqlite"
    store = ResultsStore(str(db_path))
    await store.initialize()
    assert await store.get_schema_version() == _LATEST_SCHEMA_VERSION
    assert _LATEST_SCHEMA_VERSION >= 6
    await store.close()

    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute("PRAGMA table_info(research_sessions)")
        cols = {row[1] for row in await cursor.fetchall()}

    canonical = {"skill_id", "subject_id", "variant"}
    assert canonical.issubset(cols), f"missing columns: {canonical - cols}"


# ---------------------------------------------------------------------------
# P3-019 — forward migration from a v1-era DB → latest (v6), dual-shape read.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v1_to_latest_forward_migration_dual_shape(tmp_path: Path) -> None:
    """A DB seeded at v1 (pre-ARC-011 canonical columns) migrates forward to
    the latest version on ``initialize()``, and a legacy row round-trips
    through ``_dual_shape_session`` to produce the canonical surface.

    This is the P3-019 AC: "A v1 fixture round-trips through read → produces a
    v2-shape response" + "ResultsStore.initialize() migrates existing v1 rows".
    """
    db_path = tmp_path / "v1_seed.sqlite"

    # 1. Bootstrap the pre-versioned schema and run only _migrate_to_v1 so the
    #    DB looks exactly like a server that ran before ARC-011 landed.
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(_SCHEMA_SQL)
        await _set_schema_version(db, 1)
        await _migrate_to_v1(db)
        await db.commit()
        # 2. Insert a legacy research_sessions row — no skill_id/subject_id/
        #    variant columns exist at v1.
        await db.execute(
            "INSERT INTO research_sessions "
            "(id, instrument, timeframe, model_type, tag, skill_name, "
            " workspace_path, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "res_legacy_v1",
                "DOGE_USDT",
                "15m",
                "direction",
                "legacy_tag",
                "direction-autotuner",
                str(tmp_path / "ws"),
                "2026-01-01T00:00:00+00:00",
            ),
        )
        await db.commit()

    # 3. Re-open through initialize(); the migration runner drives v2..latest.
    store = ResultsStore(str(db_path))
    await store.initialize()
    assert await store.get_schema_version() == _LATEST_SCHEMA_VERSION
    assert _LATEST_SCHEMA_VERSION >= 6

    # 4. The canonical columns now exist (v6 added them).
    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute("PRAGMA table_info(research_sessions)")
        cols = {row[1] for row in await cursor.fetchall()}
    assert {"skill_id", "subject_id", "variant"}.issubset(cols)
    await store.close()

    # 5. The legacy row round-trips through the dual-shape projection: canonical
    #    fields are back-filled from the legacy trio (skill_id empty in the row
    #    because the column was added post-insert with a default).
    from src.api.research import _dual_shape_session

    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM research_sessions WHERE id = ?", ("res_legacy_v1",)
        )
        row = dict(await cursor.fetchone())

    projected = _dual_shape_session(row)
    assert projected["skill_id"] == "ml-direction"  # ← model_type via alias
    assert projected["subject_id"] == "DOGE_USDT"  # ← instrument
    assert projected["variant"] == "15m"  # ← timeframe
    # Legacy trio preserved (dual shape, not replacement).
    assert projected["model_type"] == "direction"
    assert projected["instrument"] == "DOGE_USDT"
    assert projected["timeframe"] == "15m"


@pytest.mark.asyncio
async def test_migration_chain_is_logged(tmp_path: Path, caplog) -> None:
    """P3-019 AC: migration is logged. The generic runner emits one info log
    per applied version; a fresh DB records every migration v1..latest."""
    db_path = tmp_path / "logged.sqlite"
    store = ResultsStore(str(db_path))

    import logging

    caplog.set_level(logging.INFO, logger="src.core.results_store")
    await store.initialize()
    await store.close()

    applied = [
        record.getMessage()
        for record in caplog.records
        if "schema migration v" in record.getMessage()
    ]
    # A fresh DB runs every migration from v1 up to the latest version.
    expected_versions = [v for v, _ in _MIGRATIONS]
    for version in expected_versions:
        assert any(f"v{version}" in msg for msg in applied), (
            f"missing migration log for v{version}; got {applied}"
        )
