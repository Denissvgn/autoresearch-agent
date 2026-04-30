from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from server.api.results import _enrich_iteration
from server.core.consistency_validator import build_consistency_report
from server.core.iteration_snapshot import build_trial_identity, trial_identity_hash
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
    identity = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        command=(
            ".venv/bin/python scripts/autotuner/direction/prepare.py "
            "--config runs/autotuner/DOGE_USDT_15m/direction/train.yaml --quick"
        ),
        config_snapshot="agent_strategy: BALA\nwalkforward_n_folds: 3\n",
        quick_mode=True,
    )
    identity_hash = trial_identity_hash(identity)
    consistency_report = build_consistency_report(
        research_id="res_m8",
        iteration=1,
        model_type="direction",
        config_snapshot="agent_strategy: BALA\nwalkforward_n_folds: 3\n",
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
        config_snapshot="agent_strategy: BALA\nwalkforward_n_folds: 3\n",
        metrics_json=json.dumps({"status": "failed"}),
        training_time_s=None,
        canonical_config_hash=identity["canonical_config_hash"],
        trial_identity_hash=identity_hash,
        trial_identity_json=json.dumps(identity, sort_keys=True),
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
    assert row["trial_identity_hash"] == identity_hash
    assert json.loads(row["trial_identity_json"])["validation_mode"] == "quick"
    assert json.loads(row["attempt_snapshot_json"])["artifact_hash"] == "artifact-sha"
    assert json.loads(row["consistency_report_json"])["schema_version"] == (
        "cross_service_consistency_report.v1"
    )

    enriched = _enrich_iteration(row, "direction")
    assert enriched["attempt_snapshot"]["snapshot_hash"] == "attempt-sha"
    assert enriched["attempt_snapshot_hash"] == "attempt-sha"
    assert enriched["config_snapshot_sha256"] == "config-sha"
    assert enriched["artifact_hash"] == "artifact-sha"
    assert enriched["trial_identity_hash"] == identity_hash
    assert enriched["trial_identity"]["seed"] == "default"
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

    await store.record_planned_trials(
        research_id="res_m8",
        study_id="hpo_res_m8_direction",
        trials=[
            {
                "trial_id": "trial_001_dz200_scoped_isotonic",
                "trial_index": 1,
                "study_id": "hpo_res_m8_direction",
                "search_phase": "hpo_screening",
                "config_patch": {"direction_pct_threshold": 0.020},
                "config_hash": "trial-sha",
                "expected_command": (
                    ".venv/bin/python scripts/autotuner/direction/prepare.py "
                    "--config runs/autotuner/DOGE_USDT_15m/direction/"
                    "planned_trials/trial_001_dz200_scoped_isotonic/train.yaml --quick"
                ),
                "result_path": (
                    "runs/autotuner/DOGE_USDT_15m/direction/planned_trials/"
                    "trial_001_dz200_scoped_isotonic/results.json"
                ),
                "train_config_path": (
                    "runs/autotuner/DOGE_USDT_15m/direction/planned_trials/"
                    "trial_001_dz200_scoped_isotonic/train.yaml"
                ),
            }
        ],
    )
    planned = await store.get_planned_trials("res_m8")
    assert planned[0]["trial_id"] == "trial_001_dz200_scoped_isotonic"
    assert planned[0]["config_patch"]["direction_pct_threshold"] == 0.020
    assert planned[0]["config_hash"] == "trial-sha"

    by_command = await store.get_planned_trial_for_command(
        "res_m8",
        planned[0]["expected_command"],
    )
    assert by_command["trial_id"] == planned[0]["trial_id"]

    await store.update_planned_trial_status(
        research_id="res_m8",
        trial_id=planned[0]["trial_id"],
        status="completed",
        mlflow_run_id="run-planned",
    )
    completed = await store.get_planned_trial("res_m8", planned[0]["trial_id"])
    assert completed["status"] == "completed"
    assert completed["mlflow_run_id"] == "run-planned"

    manual = await store.record_planned_trial_manual_review(
        research_id="res_m8",
        study_id="hpo_res_m8_direction",
        expected_command="bad command",
        reason="outside approved plan",
    )
    assert manual["status"] == "manual_review"
    planned = await store.get_planned_trials("res_m8")
    assert planned[-1]["manual_review_reason"] == "outside approved plan"


@pytest.mark.asyncio
async def test_results_store_finds_duplicate_trial_identity_by_scope(tmp_path: Path):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    for session_id in ("res_a", "res_b"):
        await store.create_session(
            session_id=session_id,
            instrument="DOGE_USDT",
            timeframe="15m",
            model_type="rl",
            tag=session_id,
            quick_mode=True,
            max_iterations=3,
            max_budget_usd=1.0,
            focus_hint=None,
            workspace_path=str(tmp_path / session_id),
        )

    config_snapshot = "training:\n  seed: 42\nwf_n_folds: 3\n"
    identity = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        command=(
            ".venv/bin/python scripts/autotuner/rl/prepare.py "
            "--config runs/autotuner/DOGE_USDT_15m/rl/train.yaml --quick"
        ),
        config_snapshot=config_snapshot,
        quick_mode=True,
    )
    identity_hash = trial_identity_hash(identity)
    await store.add_iteration(
        research_id="res_a",
        iteration=1,
        primary_metric=0.1,
        metric_name="composite_rl_score",
        all_gates_passed=False,
        decision="discard",
        description="screening",
        config_snapshot=config_snapshot,
        metrics_json=json.dumps({"status": "completed"}),
        training_time_s=10.0,
        canonical_config_hash=identity["canonical_config_hash"],
        trial_identity_hash=identity_hash,
        trial_identity_json=json.dumps(identity, sort_keys=True),
    )

    same_session = await store.find_duplicate_trial_identity(
        research_id="res_a",
        trial_identity_hash=identity_hash,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
    )
    assert same_session["iteration"] == 1

    cross_disabled = await store.find_duplicate_trial_identity(
        research_id="res_b",
        trial_identity_hash=identity_hash,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
    )
    assert cross_disabled is None

    cross_enabled = await store.find_duplicate_trial_identity(
        research_id="res_b",
        trial_identity_hash=identity_hash,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        include_cross_session=True,
    )
    assert cross_enabled["research_id"] == "res_a"

    seed_43 = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        command=(
            ".venv/bin/python scripts/autotuner/rl/prepare.py "
            "--config runs/autotuner/DOGE_USDT_15m/rl/train.yaml "
            "--seed 43 --quick"
        ),
        config_snapshot=config_snapshot,
        quick_mode=True,
    )
    assert trial_identity_hash(seed_43) != identity_hash


@pytest.mark.asyncio
async def test_results_store_records_audit_events(tmp_path: Path):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()

    event = await store.record_audit_event(
        actor_id="token_sha256:abc123",
        action="research.start",
        research_id="res_audit",
        request_metadata={"method": "POST", "path": "/api/research/start"},
        outcome="success",
    )

    events = await store.list_audit_events(action="research.start", research_id="res_audit")
    assert len(events) == 1
    assert events[0]["event_id"] == event["event_id"]
    assert events[0]["actor_id"] == "token_sha256:abc123"
    assert events[0]["request_metadata"]["path"] == "/api/research/start"
