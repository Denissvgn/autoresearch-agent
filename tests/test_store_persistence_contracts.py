"""Persistence contracts shared by both stores: selection and promotion.

The same test bodies run against SQLite (always) and Postgres (when
AUTORESEARCH_DATABASE_URL is set): the winner-selection semantics (objective
direction, ties, missing values, failed gates) and the promotion record
semantics (canonical identity metadata, effect acknowledgement, rollback
records) are persistence-level contracts, so every store implementation must
demonstrate them.
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

from src.core.objective_comparator import ObjectiveComparator
from src.core.results_store import ResultsStore
from tests.test_postgres_state_store import _base_dsn


def _pg_admin_dsn() -> str | None:
    base = _base_dsn()
    return None if base is None else base.rsplit("/", 1)[0] + "/postgres"


@pytest.fixture(params=["sqlite", "postgres"])
async def store(request, tmp_path):
    if request.param == "sqlite":
        sqlite_store = ResultsStore(str(tmp_path / "contract.sqlite"))
        await sqlite_store.initialize()
        yield sqlite_store
        return
    base = _base_dsn()
    if base is None:
        pytest.skip("AUTORESEARCH_DATABASE_URL unset")
    import asyncpg

    from src.core.postgres_state_store import PostgresStateStore

    admin_dsn = _pg_admin_dsn()
    dbname = f"autoresearch_contract_{uuid.uuid4().hex[:12]}"
    admin = await asyncpg.connect(admin_dsn)
    try:
        await admin.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await admin.close()
    test_dsn = base.rsplit("/", 1)[0] + "/" + dbname
    pg_store = PostgresStateStore(test_dsn)
    await pg_store.initialize()
    try:
        yield pg_store
    finally:
        await pg_store.close()
        cleanup = await asyncpg.connect(admin_dsn)
        try:
            await cleanup.execute(f'DROP DATABASE "{dbname}"')
        finally:
            await cleanup.close()


async def _seed_session(store, research_id: str) -> None:
    await store.create_session(
        session_id=research_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="contract",
        quick_mode=False,
        max_iterations=10,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path="/tmp/contract-workspace",
    )


async def _add(
    store,
    research_id: str,
    iteration: int,
    metric,
    *,
    decision: str,
    gates: bool = True,
    objective,
) -> None:
    await store.add_iteration(
        research_id=research_id,
        iteration=iteration,
        primary_metric=metric,
        metric_name="latency",
        all_gates_passed=gates,
        decision=decision,
        description=None,
        config_snapshot=f"metric: {metric}\n",
        metrics_json=json.dumps({"primary_metric": metric}),
        training_time_s=0.1,
        objective=objective,
    )


async def _best(store, research_id: str):
    session = await store.get_session(research_id)
    return session.get("best_iteration"), session.get("best_metric")



# ── Winner selection is direction-aware and persistent ────────────────────


@pytest.mark.asyncio
async def test_minimization_selection_persists(store):
    await _seed_session(store, "res_min")
    objective = ObjectiveComparator(direction="minimize", epsilon=0.0)
    await _add(store, "res_min", 1, 10.0, decision="keep", objective=objective)
    assert await _best(store, "res_min") == (1, 10.0)
    await _add(store, "res_min", 2, 5.0, decision="keep", objective=objective)
    assert await _best(store, "res_min") == (2, 5.0)
    # A worse (higher) metric must never displace the minimization winner.
    await _add(store, "res_min", 3, 20.0, decision="keep", objective=objective)
    assert await _best(store, "res_min") == (2, 5.0)


@pytest.mark.asyncio
async def test_maximization_selection_persists(store):
    await _seed_session(store, "res_max")
    objective = ObjectiveComparator(direction="maximize", epsilon=0.0)
    await _add(store, "res_max", 1, 10.0, decision="keep", objective=objective)
    await _add(store, "res_max", 2, 20.0, decision="keep", objective=objective)
    assert await _best(store, "res_max") == (2, 20.0)
    await _add(store, "res_max", 3, 5.0, decision="keep", objective=objective)
    assert await _best(store, "res_max") == (2, 20.0)


@pytest.mark.asyncio
async def test_ties_within_epsilon_do_not_move_best(store):
    await _seed_session(store, "res_tie")
    objective = ObjectiveComparator(direction="maximize", epsilon=0.5)
    await _add(store, "res_tie", 1, 10.0, decision="keep", objective=objective)
    await _add(store, "res_tie", 2, 10.3, decision="keep", objective=objective)
    assert await _best(store, "res_tie") == (1, 10.0)


@pytest.mark.asyncio
async def test_missing_metric_never_moves_best(store):
    await _seed_session(store, "res_missing")
    objective = ObjectiveComparator(direction="maximize", epsilon=0.0)
    await _add(
        store, "res_missing", 1, 10.0, decision="keep", objective=objective,
    )
    await _add(
        store, "res_missing", 2, None, decision="keep", objective=objective,
    )
    assert await _best(store, "res_missing") == (1, 10.0)


@pytest.mark.asyncio
async def test_failed_gates_never_raise_the_bar(store):
    await _seed_session(store, "res_gates")
    objective = ObjectiveComparator(direction="maximize", epsilon=0.0)
    await _add(store, "res_gates", 1, 10.0, decision="keep", objective=objective)
    # 'improve' (gates failed, raw metric up) is recorded but unpromotable.
    await _add(
        store, "res_gates", 2, 50.0,
        decision="improve", gates=False, objective=objective,
    )
    assert await _best(store, "res_gates") == (1, 10.0)
    rows = await store.get_iterations("res_gates")
    assert len(rows) == 2


# ── Promotion records persist identity, effect, and rollback state ───────


async def _seed_promotion(store, research_id: str, metadata: dict, name: str):
    await store.create_session(
        session_id=research_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="contract",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path="/tmp/contract-workspace",
    )
    return await store.record_promotion(
        research_id=research_id,
        iteration=1,
        model_type="direction",
        instrument="DOGE_USDT",
        timeframe="15m",
        target_path=f"/tmp/{name}.yaml",
        config_yaml="metric: 1\n",
        previous_yaml="metric: 0\n",
        scope="production",
        metadata_path=f"/tmp/{name}.json",
        promotion_metadata=metadata,
    )


@pytest.mark.asyncio
async def test_promotion_identity_metadata_round_trips(store):
    row = await _seed_promotion(
        store, "res_promo_a",
        {"skill_id": "skill-a", "target_identity": "identity-a"},
        "promo-a",
    )
    rows = await store.list_promotions()
    match = [r for r in rows if r.get("id") == row.get("id")]
    assert match, rows
    metadata = match[0].get("promotion_metadata") or {}
    assert metadata.get("skill_id") == "skill-a"
    assert metadata.get("target_identity") == "identity-a"
    # Two identities never collapse into one record.
    await _seed_promotion(
        store, "res_promo_b",
        {"skill_id": "skill-b", "target_identity": "identity-b"},
        "promo-b",
    )
    rows = await store.list_promotions()
    identities = {
        (r.get("promotion_metadata") or {}).get("target_identity")
        for r in rows
    }
    assert {"identity-a", "identity-b"} <= identities


@pytest.mark.asyncio
async def test_effect_ack_and_rollback_records_round_trip(store):
    row = await _seed_promotion(
        store, "res_effect",
        {"effect": {"status": "pending_effect", "idempotency_key": "k"}},
        "effect",
    )
    promotion_id = row.get("id")
    assert promotion_id is not None
    updated = await store.update_promotion_metadata(
        promotion_id=int(promotion_id),
        promotion_metadata={
            "effect": {"status": "applied", "idempotency_key": "k"},
            "skill_id": "skill-a",
            "target_identity": "identity-a",
        },
    )
    assert updated is not None
    assert (updated.get("promotion_metadata") or {}).get("effect", {}).get(
        "status",
    ) == "applied"
    rolled = await store.record_promotion_rollback(
        promotion_id=int(promotion_id),
        rollback_metadata_path="/tmp/effect-rollback.json",
        rollback_metadata={"restored": True},
    )
    assert rolled is not None
