"""ARC-011 P6-002b — dual-backend parity sweep.

The gate that proves ``PostgresStateStore`` is behavior-identical to
``SQLiteStateStore``. Runs the same representative write+read sequence against
both backends and asserts the observable results match (modulo backend-specific
column types like rowid vs BIGSERIAL id, which are normalized).

Mirrors the P1-007 "parity suite green" rule: a behavior-touching change to
either backend must keep this green.

Skipped when ``AUTORESEARCH_DATABASE_URL`` is unset (the SQLite-only half still
runs, proving SQLite is unchanged — the default deployment path).
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List

import pytest

# Columns whose values legitimately differ between backends (autoincrement
# id sequences, timestamps captured separately, Phase-6-only fencing columns).
# Compared leniently.
_BACKEND_INVARIANT_DROP = {"id", "started_at", "created_at", "updated_at",
                           "completed_at", "promoted_at", "rolled_back_at",
                           "applied_at", "timestamp", "rolled_back_metadata_json",
                           # Phase 6 (D-fencing): Postgres-only fencing epoch.
                           # SQLite is single-worker (no stale writers), so the
                           # column doesn't exist there by design.
                           "lock_epoch"}


def _base_pg_dsn() -> str | None:
    raw = os.getenv("AUTORESEARCH_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not raw:
        return None
    return raw.replace("postgresql+asyncpg://", "postgresql://")


def _normalize_row(row: Dict[str, Any] | None) -> Dict[str, Any] | None:
    """Drop backend-specific columns and coerce None/0/empty to a comparable form."""
    if row is None:
        return None
    return {k: v for k, v in row.items() if k not in _BACKEND_INVARIANT_DROP}


def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_normalize_row(r) for r in rows]  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture()
async def sqlite_store(tmp_path):
    from src.core.state_store import SQLiteStateStore

    store = SQLiteStateStore(str(tmp_path / "parity.db"))
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()


@pytest.fixture()
async def pg_store_parity():
    """PostgresStateStore against a throwaway DB; skip if no DSN."""
    import asyncpg

    from src.core.postgres_state_store import PostgresStateStore

    base = _base_pg_dsn()
    if base is None:
        pytest.skip("AUTORESEARCH_DATABASE_URL unset")
    dbname = f"autoresearch_parity_{uuid.uuid4().hex[:12]}"
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


async def _run_full_sequence(store: Any, *, sid: str) -> Dict[str, Any]:
    """Run a representative write+read sequence; return a snapshot of results.

    Identical for both backends — this is the parity contract.
    """
    # Create a session.
    await store.create_session(
        session_id=sid,
        instrument="EURUSD",
        timeframe="H1",
        model_type="direction",
        tag="parity",
        quick_mode=False,
        max_iterations=10,
        max_budget_usd=20.0,
        focus_hint="focus",
        workspace_path="/tmp/ws",
        manifest_json='{"v":1}',
        manifest_path="/tmp/m.json",
        manifest_hash="abc",
    )
    session = await store.get_session(sid)
    # Two iterations (one keep/gates-passing, one discard).
    await store.add_iteration(
        research_id=sid, iteration=1, primary_metric=0.4, metric_name="sharpe",
        all_gates_passed=True, decision="keep", description="first",
        config_snapshot="{}", metrics_json='{"status":"completed"}',
        training_time_s=5.0, api_cost_usd=0.1,
    )
    await store.add_iteration(
        research_id=sid, iteration=2, primary_metric=0.5, metric_name="sharpe",
        all_gates_passed=True, decision="keep", description="second",
        config_snapshot="{}", metrics_json='{"status":"completed"}',
        training_time_s=6.0, api_cost_usd=0.2,
    )
    best = await store.get_best_iteration(sid)
    iters = await store.get_iterations(sid)
    iter_one = await store.get_iteration(sid, 1)
    # Audit event.
    audit = await store.record_audit_event(
        actor_id="tester", action="parity.test", outcome="success",
        research_id=sid, request_metadata={"k": "v"},
    )
    audits = await store.list_audit_events(research_id=sid)
    # Runtime command lifecycle.
    cmd = await store.record_runtime_command(
        research_id=sid, turn=1, tool_name="bash", command="echo hi",
        normalized_command="echo hi", policy_operation="allow",
        timeout_s=10, metadata={"phase": "x"},
    )
    finished = await store.finish_runtime_command(
        cmd["id"], status="completed", returncode=0, output_preview="hi",
    )
    # Promotion.
    promo = await store.record_promotion(
        research_id=sid, iteration=2, model_type="direction",
        instrument="EURUSD", timeframe="H1", target_path="/tmp/t.yaml",
        config_yaml="k: v", previous_yaml="k: old", scope="development",
        promotion_metadata={"reason": "best"},
    )
    promos = await store.list_promotions()
    latest_dev = await store.get_latest_development_promotion(
        model_type="direction", instrument="EURUSD", timeframe="H1",
    )
    # HPO study.
    hpo = await store.add_hpo_study(
        research_id=sid, iteration=2, n_trials=10, completed_trials=10,
        best_composite=0.9, training_time_s=100.0, top_trials_json="[]",
        status="completed",
    )
    hpos = await store.get_hpo_studies(sid)
    # Planned trial.
    await store.record_planned_trials(
        research_id=sid, study_id="s1",
        trials=[{
            "trial_id": "t1", "trial_index": 0, "search_phase": "screening",
            "config_patch": {"a": 1}, "config_hash": "h1",
            "expected_command": "train.py",
        }],
    )
    planned = await store.get_planned_trials(sid)
    planned_one = await store.get_planned_trial(sid, "t1")
    # Pagination (no cursor: full list; with cursor: one page).
    listed = await store.list_sessions(status="running")
    counted = await store.count_sessions(status="running")
    page1 = await store.list_sessions(limit=1)
    # Update + delete-session path (on a second session).
    await store.create_session(
        session_id=f"{sid}_del", instrument="EURUSD", timeframe="H1",
        model_type="direction", tag="parity", quick_mode=False,
        max_iterations=10, max_budget_usd=20.0, focus_hint=None,
        workspace_path="/tmp/ws",
    )
    await store.update_session(f"{sid}_del", status="paused",
                                current_phase="baseline")
    updated = await store.get_session(f"{sid}_del")
    deleted = await store.delete_session(f"{sid}_del")

    return {
        "session": _normalize_row(session),
        "best_iteration_metric": (best or {}).get("primary_metric") if best else None,
        "best_iteration_number": (best or {}).get("iteration") if best else None,
        "iterations_count": len(iters),
        "iterations_metrics": [(r.get("iteration"), r.get("primary_metric"))
                               for r in iters],
        "iter_one_metric": _normalize_row(iter_one).get("primary_metric") if iter_one else None,
        "audit_outcome": audit.get("outcome"),
        "audits_count": len(audits),
        "audits_actions": [a.get("action") for a in audits],
        "cmd_status": (finished or {}).get("status"),
        "cmd_returncode": (finished or {}).get("returncode"),
        "promo_scope": promo.get("scope"),
        "promos_count": len(promos),
        "latest_dev_target": (latest_dev or {}).get("target_path") if latest_dev else None,
        "hpo_status": hpo.get("status"),
        "hpos_count": len(hpos),
        "planned_count": len(planned),
        "planned_one_trial_id": (planned_one or {}).get("trial_id") if planned_one else None,
        "listed_sessions_statuses": sorted({s.get("status") for s in listed}),
        "listed_sessions_count": len(listed),
        "counted_sessions": counted,
        "page1_len": len(page1),
        "updated_status": (updated or {}).get("status") if updated else None,
        "updated_phase": (updated or {}).get("current_phase") if updated else None,
        "deleted": deleted,
    }


# --------------------------------------------------------------------------
# Parity tests
# --------------------------------------------------------------------------

@pytest.mark.postgres
async def test_full_sequence_parity_across_backends(sqlite_store, pg_store_parity):
    """The same write+read sequence produces identical observable results on
    both backends. This is the P6-002b gate — a divergence here is a parity
    bug in the Postgres port."""
    sid = f"res_parity_{uuid.uuid4().hex[:8]}"
    sqlite_snapshot = await _run_full_sequence(sqlite_store, sid=sid)
    pg_snapshot = await _run_full_sequence(pg_store_parity, sid=sid)
    # Compare the two snapshots field-by-field for a precise diff on failure.
    assert sqlite_snapshot == pg_snapshot, (
        f"backend divergence:\n"
        f"sqlite={sqlite_snapshot}\npostgres={pg_snapshot}"
    )


async def test_sqlite_full_sequence_unchanged(sqlite_store):
    """The SQLite sequence runs and produces the expected shape.

    This half runs unconditionally (no Postgres required) so the default
    deployment path (SQLite) is proven unchanged by the Phase-6 wiring — the
    core §1.6 backward-compat guarantee. The cross-backend comparison lives in
    the postgres-marked test above."""
    sid = f"res_sqlite_{uuid.uuid4().hex[:8]}"
    snap = await _run_full_sequence(sqlite_store, sid=sid)
    # Spot-check the invariants that matter for parity.
    assert snap["best_iteration_metric"] == 0.5  # higher of the two keep runs
    assert snap["best_iteration_number"] == 2
    assert snap["iterations_count"] == 2
    assert snap["cmd_status"] == "completed"
    assert snap["deleted"] is True
    assert snap["counted_sessions"] == 1  # the _del session was deleted
    assert snap["page1_len"] == 1
    assert snap["updated_status"] == "paused"
