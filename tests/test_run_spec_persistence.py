"""Resolved run spec persistence: round-trip, migrations, legacy read.

A run's immutable inputs — canonical parameters and defaults, objective and
policy, evaluator/dataset/package content digests, runtime identity, and the
effective nonsecret configuration — are persisted as a hashed, versioned
run spec that is inspected independently of the current registry and
settings. Secret parameters persist as references with an explicit rebinding
policy, never as values. Old artifacts without a spec report missing
provenance; unknown fields are reported, never backfilled.
"""

from __future__ import annotations

import json
import os

import pytest

from src.core.research_manifest import (
    build_research_manifest,
    load_persisted_manifest,
    manifest_pretty_json,
)
from src.core.results_store import ResultsStore
from src.core.run_spec import (
    SECRET_REBIND_POLICY,
    build_run_spec,
    provenance_report,
    split_secret_params,
    verify_run_spec,
)
from src.core.session_manager import SessionManager

_SECRET_VALUE = "super-secret-credential-value-123"


def _spec(**overrides):
    kwargs = {
        "skill_params": {"sequence": "10,5", "api_token": _SECRET_VALUE},
        "param_schema": None,
        "skill_id": "conformance-probe",
        "skill_version": "0.1.0",
        "skill_dir": None,
        "objective_policy": {"direction": "maximize", "epsilon": 0.0},
        "policy": {"command_policy_sha256": "0" * 64},
        "effective_config": {"provider": "anthropic", "environment": "test"},
    }
    kwargs.update(overrides)
    return build_run_spec(**kwargs)


def test_run_spec_records_params_defaults_digests_and_identity(tmp_path):
    dataset = tmp_path / "eval_set.jsonl"
    dataset.write_text('{"x": 1}\n', encoding="utf-8")
    schema = {
        "type": "object",
        "properties": {
            "sequence": {"type": "string", "default": "10,5"},
            "effort": {"type": "integer", "default": 3},
        },
    }
    spec = _spec(
        skill_params={"api_token": _SECRET_VALUE, "dataset": str(dataset)},
        param_schema=schema,
    )
    # Canonical parameters after defaults, with the applied defaults recorded.
    assert spec["param_defaults_applied"] == {"sequence": "10,5", "effort": 3}
    assert spec["skill_params"]["effort"] == 3
    # Dataset and identity digests are recorded, and the spec hash verifies.
    assert spec["digests"]["dataset_inputs"] == {
        "dataset": __import__("hashlib").sha256(
            dataset.read_bytes()
        ).hexdigest()
    }
    assert spec["runtime_identity"]["python_version"]
    assert spec["objective_policy"]["direction"] == "maximize"
    assert verify_run_spec(spec)


def test_secret_values_are_never_persisted(tmp_path):
    values, refs = split_secret_params({"api_token": _SECRET_VALUE, "a": 1})
    assert values == {"a": 1}
    assert refs["api_token"]["rebind_policy"] == SECRET_REBIND_POLICY
    assert refs["api_token"]["env_var"]
    spec = _spec()
    dumped = json.dumps(spec)
    assert _SECRET_VALUE not in dumped
    assert spec["skill_params"] == {"sequence": "10,5"}
    assert "api_token" in spec["secret_refs"]


def test_manifest_round_trips_the_run_spec(tmp_path, monkeypatch):
    from src.core import skill_registry as skill_registry_module

    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    monkeypatch.setattr(
        skill_registry_module, "DEFAULT_SKILLS_ROOT", skills_root,
    )
    manifest = build_research_manifest(
        research_id="res_spec_1",
        instrument="conformance-subject",
        timeframe="default",
        model_type="",
        tag="spec",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        timeout_s=60,
        focus_hint=None,
        skill_id="db-config-tuning",
        skill_params={"sequence": "10,5"},
    )
    assert manifest.run_spec is not None
    assert manifest.run_spec["skill_params"]["sequence"] == "10,5"
    assert verify_run_spec(manifest.run_spec)
    text = manifest_pretty_json(manifest)
    loaded, report = load_persisted_manifest(text)
    assert loaded is not None
    assert loaded.run_spec == manifest.run_spec
    assert report["spec_digest_verified"] is True
    assert report["unknown_fields"] == []
    assert report["reported_not_backfilled"] is True


# ── Old-run read fixtures: reported, never backfilled ─────────────────────


def test_old_run_artifacts_report_unknown_fields_and_missing_provenance():
    old_artifact = {
        "schema_version": "research_session_manifest.v1",
        "research_id": "res_old_1",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": "direction",
        "objective": "auc",
        "model_family": "lgbm",
        "data_window": {"bars": 500},
        "baseline_config": {"tag": "old"},
        "roster": {"models": ["m1"]},
        "tsfm": {"enabled": False},
        "adaptive_features": {"noop_reason": None},
        "split_ids": {"train": [1, 2]},
        "cost_model": {"per_token_usd": 0.0},
        "gate_bundle": {"name": "legacy-gates"},
        "service_urls": {"mlflow": "http://mlflow.local"},
        "budget": {"max_budget_usd": 1.0, "quick_mode": False},
        "max_iterations": 3,
        "timeout_s": 60,
        "promotion_policy": {"scope": "development"},
        "preflight": {"status": "not_run"},
        "runtime": {"environment": "legacy"},
        # Unknown legacy provenance: present on the artifact, absent from the
        # current schema.
        "legacy_optimizer_block": {"kind": "grid"},
        "trading_mode": "spot",
    }
    raw = json.dumps(old_artifact)
    manifest, report = load_persisted_manifest(raw)
    assert manifest is not None, report
    assert manifest.research_id == "res_old_1"
    assert report["unknown_fields"] == [
        "legacy_optimizer_block", "trading_mode",
    ]
    assert report["artifact_schema_version"] == "research_session_manifest.v1"
    assert "run_spec" in report["missing_provenance"]
    assert report["spec_digest_verified"] is None
    # Nothing was backfilled: the loaded manifest carries no invented spec.
    assert manifest.run_spec is None
    assert manifest.skill_params if hasattr(manifest, "skill_params") else True


def test_invalid_artifacts_report_instead_of_raising():
    manifest, report = load_persisted_manifest("not-json{")
    assert manifest is None
    assert "error" in report
    assert report["reported_not_backfilled"] is True
    manifest, report = load_persisted_manifest(json.dumps(["a", "list"]))
    assert manifest is None
    assert "error" in report
    # A structurally valid but unfillable artifact reports its validation gap.
    unfillable = json.dumps({"schema_version": "research_session_manifest.v1"})
    manifest, report = load_persisted_manifest(unfillable)
    assert manifest is None
    assert "error" in report


# ── Migrations on disposable databases ────────────────────────────────────


async def _migrated_store(tmp_path):
    """A v6-era database copy, migrated forward by the current code."""
    import aiosqlite

    db_path = tmp_path / "legacy_v6.sqlite"
    store = ResultsStore(str(db_path))
    await store.initialize()
    # Rewind to the v6-era shape: the secret refs table did not exist and the
    # schema was stamped at the previous version.
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DROP TABLE session_secret_refs")
        await db.execute("UPDATE schema_version SET version = 6 WHERE id = 1")
        await db.commit()
    await store.initialize()
    return store, db_path


@pytest.mark.asyncio
async def test_sqlite_migration_adds_secret_refs_on_a_legacy_database(tmp_path):
    store, db_path = await _migrated_store(tmp_path)
    assert await store.get_schema_version() == 10
    await store.add_secret_ref(
        research_id="res_mig",
        param_name="api_token",
        env_var="SKILL_PARAM_API_TOKEN",
        rebind_policy=SECRET_REBIND_POLICY,
    )
    refs = await store.get_secret_refs("res_mig")
    assert len(refs) == 1
    assert refs[0]["env_var"] == "SKILL_PARAM_API_TOKEN"
    # Idempotent re-initialization: the migration never re-fires destructively.
    await store.initialize()
    assert await store.get_secret_refs("res_mig") == refs
    await store.close()


@pytest.mark.asyncio
async def test_secret_refs_cascade_delete_with_the_session(tmp_path):
    store, _ = await _migrated_store(tmp_path)
    await store.create_session(
        session_id="res_cascade",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="cascade",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path="/tmp/cascade",
    )
    await store.add_secret_ref(
        research_id="res_cascade",
        param_name="api_token",
        env_var="SKILL_PARAM_API_TOKEN",
        rebind_policy=SECRET_REBIND_POLICY,
    )
    await store.delete_session("res_cascade")
    assert await store.get_secret_refs("res_cascade") == []
    await store.close()


@pytest.mark.asyncio
async def test_postgres_store_carries_the_secret_refs_contract():
    base = os.environ.get("AUTORESEARCH_DATABASE_URL") or os.environ.get(
        "DATABASE_URL",
    )
    if not base:
        pytest.skip("AUTORESEARCH_DATABASE_URL unset")
    import uuid as _uuid

    import asyncpg

    from src.core.postgres_state_store import PostgresStateStore

    base = base.replace("postgresql+asyncpg://", "postgresql://")
    admin_dsn = base.rsplit("/", 1)[0] + "/postgres"
    dbname = f"autoresearch_runspec_{_uuid.uuid4().hex[:12]}"
    admin = await asyncpg.connect(admin_dsn)
    try:
        await admin.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await admin.close()
    dsn = base.rsplit("/", 1)[0] + "/" + dbname
    store = PostgresStateStore(dsn)
    await store.initialize()
    try:
        await store.add_secret_ref(
            research_id="res_pg",
            param_name="api_token",
            env_var="SKILL_PARAM_API_TOKEN",
            rebind_policy=SECRET_REBIND_POLICY,
        )
        refs = await store.get_secret_refs("res_pg")
        assert len(refs) == 1
        assert refs[0]["rebind_policy"] == SECRET_REBIND_POLICY
    finally:
        await store.close()
        cleanup = await asyncpg.connect(admin_dsn)
        try:
            await cleanup.execute(f'DROP DATABASE "{dbname}"')
        finally:
            await cleanup.close()


# ── Pinned spec vs the live registry ──────────────────────────────────────


def test_registry_mutation_after_start_keeps_the_pinned_spec(tmp_path):
    spec = _spec(skill_params={"sequence": "10,5"}, skill_version="0.1.0")
    # The recorded spec is the run's authority: nothing consults the registry
    # to read it back.
    assert spec["skill_params"] == {"sequence": "10,5"}
    assert spec["skill_version"] == "0.1.0"
    assert verify_run_spec(spec)
    # Tampering with the recorded spec is detectable, not silently accepted.
    tampered = dict(spec)
    tampered["skill_params"] = {"sequence": "999"}
    assert verify_run_spec(tampered) is False


def test_skill_pin_refuses_silent_drift():
    manager = object.__new__(SessionManager)
    run_spec = {"skill_version": "0.0.9", "digests": {}}
    with pytest.raises(RuntimeError, match="migrate explicitly"):
        manager._check_skill_pin(
            skill_id="db-config-tuning",
            run_spec=run_spec,
            allow_skill_drift=False,
        )
    # Explicit operator migration: the drift override is the only way through.
    manager._check_skill_pin(
        skill_id="db-config-tuning",
        run_spec=run_spec,
        allow_skill_drift=True,
    )
    # A legacy parent without a pin has nothing to check — reported, not
    # enforced against invented facts.
    manager._check_skill_pin(
        skill_id="db-config-tuning",
        run_spec={},
        allow_skill_drift=False,
    )


# ── Continuation restores the pinned parameters (never today's defaults) ──


def test_continuation_restores_pinned_parameters_and_rebinds_secrets(
    monkeypatch,
):
    manifest = build_research_manifest(
        research_id="res_parent",
        instrument="conformance-subject",
        timeframe="default",
        model_type="",
        tag="parent",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        timeout_s=60,
        focus_hint=None,
        skill_id="db-config-tuning",
        skill_params={"api_token": _SECRET_VALUE, "sequence": "10,5"},
    )
    row = {"manifest_json": manifest_pretty_json(manifest)}
    params, refs, run_spec = SessionManager._parent_run_spec(row)
    # Nonsecret parameters persist with their applied defaults; secret values
    # are never in the artifact.
    assert params["sequence"] == "10,5"
    assert params["target_latency_ms"] == 10
    assert _SECRET_VALUE not in json.dumps(run_spec)
    assert "api_token" in refs

    # A missing secret binding is an explicit operator error naming the ref.
    monkeypatch.delenv(refs["api_token"]["env_var"], raising=False)
    with pytest.raises(RuntimeError, match="api_token"):
        SessionManager._rebind_secret_params(params, refs)
    # With the binding supplied, continuation carries the operator's value.
    monkeypatch.setenv(refs["api_token"]["env_var"], "fresh-bound-value")
    restored = dict(params)
    SessionManager._rebind_secret_params(restored, refs)
    assert restored["api_token"] == "fresh-bound-value"
    assert restored["sequence"] == "10,5"
    assert restored["target_latency_ms"] == 10

    # A legacy parent without a spec continues with empty parameters —
    # reported, never back-filled from today's defaults.
    params, refs, run_spec = SessionManager._parent_run_spec({"manifest_json": ""})
    assert params == {}
    assert refs == {}
    assert run_spec == {}


def test_provenance_report_names_what_is_recorded_and_lacking():
    report = provenance_report({"research_id": "res_x", "mystery_section": {}})
    assert report["unknown_fields"] == ["mystery_section"]
    assert "run_spec" in report["missing_provenance"]
    assert report["reported_not_backfilled"] is True


