"""Migration and restore qualification: upgraded databases keep their past.

Legacy databases upgrade to the current schema with rows, old manifests,
and artifact references preserved; backup and restore recover complete
state. These tests execute the same procedure the operational runbook
documents.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import aiosqlite
import pytest

from src.core.research_manifest import load_persisted_manifest
from src.core.run_spec import verify_run_spec
from src.core.state_store import (
    _LATEST_SCHEMA_VERSION,
    _MIGRATIONS,
    _SCHEMA_SQL,
    SQLiteStateStore,
    _migrate_to_v1,
    _set_schema_version,
)


@pytest.mark.asyncio
async def test_legacy_v1_database_upgrades_with_rows(tmp_path: Path):
    db_path = tmp_path / "v1_seed.sqlite"

    # a server that ran before the versioned era: schema at v1, one legacy
    # row in the era's column shape
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(_SCHEMA_SQL)
        await _set_schema_version(db, 1)
        await _migrate_to_v1(db)
        await db.commit()
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

    # upgrading drives v2..latest and preserves the row
    store = SQLiteStateStore(str(db_path))
    await store.initialize()
    try:
        assert await store.get_schema_version() == _LATEST_SCHEMA_VERSION
        row = await store.get_session("res_legacy_v1")
        assert row is not None
        assert row is not None
        assert row["instrument"] == "DOGE_USDT"
        assert row["tag"] == "legacy_tag"
        # the current surfaces exist on the upgraded database
        assert await store.list_events(stream_key="res_legacy_v1") == []
        assert await store.get_usage_events("res_legacy_v1") == []
        assert await store.reserve_work(
            reservation_key="post-upgrade",
            scope_key="scope",
            owner_id="worker",
            capacity_limit=1,
            lease_seconds=60.0,
        )
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_old_manifest_loads_with_its_provenance_reported(tmp_path: Path):
    """A pre-run-spec manifest loads as recorded: reported, never filled in."""
    from src.core.research_manifest import build_research_manifest

    db_path = tmp_path / "old_manifest.sqlite"
    manifest = build_research_manifest(
        research_id="res_old",
        instrument="EURUSD",
        timeframe="1h",
        model_type="",
        tag="old",
        quick_mode=True,
        max_iterations=3,
        max_budget_usd=7.5,
        timeout_s=0,
        focus_hint="old manifest fixture",
        skill_id="prompt-engineering",
        skill_params={},
    )
    old_payload = manifest.model_dump()
    old_payload.pop("run_spec", None)  # a manifest from before pinned specs

    store = SQLiteStateStore(str(db_path))
    await store.initialize()
    try:
        await store.create_session(
            session_id="res_old",
            instrument="EURUSD",
            timeframe="1h",
            model_type="",
            skill_id="prompt-engineering",
            subject_id="EURUSD",
            variant="1h",
            tag="old",
            quick_mode=True,
            max_iterations=3,
            max_budget_usd=7.5,
            focus_hint="old manifest fixture",
            workspace_path="/tmp/old-ws",
            manifest_json=json.dumps(old_payload),
            manifest_hash="h",
        )
        row = await store.get_session("res_old")
        assert row is not None
        assert row is not None
        loaded, report = load_persisted_manifest(row["manifest_json"])
        assert loaded is not None
        assert loaded.research_id == "res_old"
        # the absent run spec is reported as missing provenance — the
        # loader never back-fills it from today's defaults
        assert "run_spec" in (report.get("missing_provenance") or [])
        assert report.get("reported_not_backfilled") is True
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_modern_artifact_references_survive_the_new_migrations(
    tmp_path: Path,
):
    """A pre-reservations database keeps its pinned artifact references."""
    from src.core.run_spec import build_run_spec

    db_path = tmp_path / "v7_seed.sqlite"
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(_SCHEMA_SQL)
        # seed exactly as a server at schema v7: run the chain up to v7 and
        # stop, so the newer migrations remain pending
        for version, migration in _MIGRATIONS:
            if version <= 7:
                await migration(db)
        await _set_schema_version(db, 7)
        spec = build_run_spec(
            skill_params={"knob": 0.42},
            param_schema=None,
            skill_id="prompt-engineering",
            skill_version="1.0.0",
            skill_dir=None,
            objective_policy={"metric": "auc"},
            policy={},
            effective_config={"max_budget_usd": 7.5},
            parent_snapshot={"digest": "b" * 64, "files": {}},
        )
        from src.core.research_manifest import build_research_manifest

        manifest_obj = build_research_manifest(
            research_id="res_v7",
            instrument="EURUSD",
            timeframe="1h",
            model_type="",
            tag="v7",
            quick_mode=True,
            max_iterations=3,
            max_budget_usd=7.5,
            timeout_s=0,
            focus_hint="v7 fixture",
            skill_id="prompt-engineering",
            skill_params={},
        )
        manifest_obj.run_spec = spec
        await db.execute(
            "INSERT INTO research_sessions "
            "(id, instrument, timeframe, model_type, tag, skill_name, "
            " workspace_path, started_at, manifest_json, skill_id, "
            " subject_id, variant) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "res_v7",
                "EURUSD",
                "1h",
                "",
                "v7",
                "",
                str(tmp_path / "ws7"),
                "2026-01-01T00:00:00+00:00",
                manifest_obj.model_dump_json(),
                "prompt-engineering",
                "EURUSD",
                "1h",
            ),
        )
        await db.execute(
            "INSERT INTO iterations "
            "(research_id, iteration, metrics_json, attempt_snapshot_hash, "
            " created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "res_v7",
                1,
                '{"auc": 0.5}',
                "a" * 64,
                "2026-01-01T00:00:00+00:00",
            ),
        )
        await db.commit()

    store = SQLiteStateStore(str(db_path))
    await store.initialize()
    try:
        assert await store.get_schema_version() == _LATEST_SCHEMA_VERSION
        # the pinned spec and its parent artifact digest are intact
        row = await store.get_session("res_v7")
        assert row is not None
        assert row is not None
        manifest, _report = load_persisted_manifest(row["manifest_json"])
        run_spec = dict(getattr(manifest, "run_spec", None) or {})
        assert verify_run_spec(run_spec) is True
        assert run_spec["parent_snapshot"]["digest"] == "b" * 64
        # the attempt's artifact reference survived the upgrade
        rows = await store.get_iterations("res_v7")
        assert rows[0]["attempt_snapshot_hash"] == "a" * 64
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_backup_and_restore_recovers_complete_state(tmp_path: Path):
    """The documented backup/restore procedure recovers every surface."""
    source_path = tmp_path / "live.sqlite"
    store = SQLiteStateStore(str(source_path))
    await store.initialize()
    try:
        await store.create_session(
            session_id="res_backup",
            instrument="EURUSD",
            timeframe="1h",
            model_type="trend",
            tag="",
            quick_mode=True,
            max_iterations=2,
            max_budget_usd=7.5,
            focus_hint="backup fixture",
            workspace_path="/tmp/backup-ws",
            manifest_json='{"research_id": "res_backup"}',
            manifest_hash="h",
        )
        await store.append_event(
            event_id="res_backup:t:1",
            stream_key="res_backup",
            event_type="research_started",
            payload={"status": "running"},
            producer="worker-a",
        )
        await store.record_usage_event(
            {
                "event_key": "res_backup:agent:1",
                "research_id": "res_backup",
                "role": "agent",
                "provider": "mock",
                "model": "mock",
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "cost_status": "estimated",
                "cost_usd": 0.0,
                "pricing_basis": {"version": "mock-zero.v1"},
            }
        )
        await store.reserve_budget(
            reservation_id="budget:res_backup",
            research_id="res_backup",
            amount_usd=5.0,
            strict_cap_usd=10.0,
            enforcement="strict",
            lease_seconds=60.0,
        )
    finally:
        await store.close()

    # backup: the SQLite online backup API (the runbook's procedure)
    backup_path = tmp_path / "backup.sqlite"
    source = sqlite3.connect(str(source_path))
    try:
        destination = sqlite3.connect(str(backup_path))
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()

    # disaster: the live database is destroyed
    source_path.unlink()

    # restore: the backup becomes the live database again
    restored = SQLiteStateStore(str(backup_path))
    await restored.initialize()
    try:
        session = await restored.get_session("res_backup")
        assert session is not None
        assert session["focus_hint"] == "backup fixture"
        assert session["max_budget_usd"] == 7.5
        events = await restored.list_events(stream_key="res_backup")
        assert [e["event_id"] for e in events] == ["res_backup:t:1"]
        usage = await restored.get_usage_events("res_backup")
        assert [u["role"] for u in usage] == ["agent"]
        reservations = await restored.list_budget_reservations("res_backup")
        assert reservations[0]["state"] == "reserved"
    finally:
        await restored.close()
