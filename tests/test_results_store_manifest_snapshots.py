from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from server.api.results import _enrich_iteration
from server.core.results_store import ResultsStore


@pytest.mark.asyncio
async def test_results_store_persists_manifest_and_attempt_snapshot(tmp_path: Path):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()

    manifest = {
        "schema_version": "research_session_manifest.v1",
        "research_id": "res_m8",
        "manifest_hash": "manifest-sha",
    }
    await store.create_session(
        session_id="res_m8",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="m8",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path=str(tmp_path / "runs" / "direction"),
        manifest_json=json.dumps(manifest),
        manifest_path=str(tmp_path / "runs" / "direction" / "research_manifest.json"),
        manifest_hash="manifest-sha",
    )
    session = await store.get_session("res_m8")

    assert session["manifest_hash"] == "manifest-sha"
    assert json.loads(session["manifest_json"])["research_id"] == "res_m8"

    snapshot = {
        "schema_version": "autoresearch_iteration_attempt.v1",
        "research_id": "res_m8",
        "iteration": 1,
        "snapshot_hash": "attempt-sha",
        "config_snapshot_sha256": "config-sha",
        "artifact_hash": "artifact-sha",
    }
    await store.add_iteration(
        research_id="res_m8",
        iteration=1,
        primary_metric=None,
        metric_name=None,
        all_gates_passed=False,
        decision="discard",
        description="failed before metrics",
        config_snapshot="agent_strategy: BALA\n",
        metrics_json=json.dumps({"status": "failed"}),
        training_time_s=None,
        attempt_snapshot_json=json.dumps(snapshot),
        attempt_snapshot_path=str(
            tmp_path
            / "runs"
            / "direction"
            / "server_snapshots"
            / "iteration_0001_attempt.json"
        ),
        attempt_snapshot_hash="attempt-sha",
    )

    row = await store.get_iteration("res_m8", 1)
    assert row["attempt_snapshot_hash"] == "attempt-sha"
    assert json.loads(row["attempt_snapshot_json"])["artifact_hash"] == "artifact-sha"

    enriched = _enrich_iteration(row, "direction")
    assert enriched["attempt_snapshot"]["snapshot_hash"] == "attempt-sha"
    assert enriched["attempt_snapshot_hash"] == "attempt-sha"
    assert enriched["config_snapshot_sha256"] == "config-sha"
    assert enriched["artifact_hash"] == "artifact-sha"
