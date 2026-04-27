from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from server.api.results import _enrich_iteration
from server.core.consistency_validator import build_consistency_report
from server.core.research_phase_plan import phase_state_json
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
    consistency_report = build_consistency_report(
        research_id="res_m8",
        iteration=1,
        model_type="direction",
        config_snapshot="agent_strategy: BALA\n",
        metrics_payload={"status": "failed"},
        attempt_snapshot=snapshot,
    )
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
        consistency_report_json=json.dumps(consistency_report),
    )

    row = await store.get_iteration("res_m8", 1)
    assert row["attempt_snapshot_hash"] == "attempt-sha"
    assert json.loads(row["attempt_snapshot_json"])["artifact_hash"] == "artifact-sha"
    assert json.loads(row["consistency_report_json"])["schema_version"] == (
        "cross_service_consistency_report.v1"
    )

    enriched = _enrich_iteration(row, "direction")
    assert enriched["attempt_snapshot"]["snapshot_hash"] == "attempt-sha"
    assert enriched["attempt_snapshot_hash"] == "attempt-sha"
    assert enriched["config_snapshot_sha256"] == "config-sha"
    assert enriched["artifact_hash"] == "artifact-sha"
    assert enriched["consistency_report"]["artifact_hash"] == "artifact-sha"

    phase_state = {
        "schema_version": "autoresearch_phase_state.v1",
        "current_phase": "tabular_sweeps",
        "next_action": "Run bounded tabular sweeps.",
    }
    await store.update_session(
        "res_m8",
        current_phase="tabular_sweeps",
        next_action="Run bounded tabular sweeps.",
        phase_state_json=phase_state_json(phase_state),
    )
    session = await store.get_session("res_m8")
    assert session["current_phase"] == "tabular_sweeps"
    assert json.loads(session["phase_state_json"])["next_action"] == (
        "Run bounded tabular sweeps."
    )

    await store.record_hpo_study_plan(
        research_id="res_m8",
        study_id="hpo_res_m8_direction",
        max_trials=3,
        search_space_json=json.dumps({"prediction_horizon": [3, 6]}),
        budget_json=json.dumps({"max_iterations": 3}),
        timeout_s=900,
        quick_mode=True,
    )
    studies = await store.get_hpo_studies("res_m8")
    assert studies[0]["study_id"] == "hpo_res_m8_direction"
    assert studies[0]["max_trials"] == 3
    assert studies[0]["quick_mode"] == 1
