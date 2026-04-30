from __future__ import annotations

import json
from pathlib import Path

from server.core.iteration_snapshot import (
    build_iteration_attempt_snapshot,
    build_trial_identity,
    canonical_config_hash,
    trial_identity_hash,
    write_iteration_attempt_snapshot,
)


def test_iteration_attempt_snapshot_hashes_config_and_writes_file(tmp_path: Path):
    snapshot = build_iteration_attempt_snapshot(
        research_id="res_attempt",
        iteration=2,
        turn=7,
        command="python scripts/autotuner/direction/prepare.py",
        config_snapshot="agent_strategy: BALA\n",
        workspace=str(tmp_path),
        marker={
            "status": "failed",
            "artifact_hash": "artifact-sha",
            "feature_schema_hash": "feature-sha",
        },
    )

    assert snapshot["schema_version"] == "autoresearch_iteration_attempt.v1"
    assert snapshot["status"] == "failed"
    assert snapshot["artifact_hash"] == "artifact-sha"
    assert snapshot["feature_schema_hash"] == "feature-sha"
    assert snapshot["config_snapshot_sha256"]
    assert snapshot["snapshot_hash"]

    path = write_iteration_attempt_snapshot(workspace=str(tmp_path), snapshot=snapshot)
    persisted = json.loads(Path(path).read_text(encoding="utf-8"))
    assert persisted["snapshot_hash"] == snapshot["snapshot_hash"]
    assert Path(path).name == "iteration_0002_attempt.json"


def test_trial_identity_hash_distinguishes_seed_mode_and_split():
    config_a = "training:\n  seed: 42\nwf_n_folds: 3\n"
    config_b = "wf_n_folds: 3\ntraining:\n  seed: 42\n"
    assert canonical_config_hash(config_a) == canonical_config_hash(config_b)

    base = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        command=(
            ".venv/bin/python scripts/autotuner/rl/prepare.py "
            "--config runs/autotuner/DOGE_USDT_15m/rl/best_train.yaml --quick"
        ),
        config_snapshot=config_a,
        quick_mode=True,
    )
    full_mode = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        command=(
            ".venv/bin/python scripts/autotuner/rl/prepare.py "
            "--config runs/autotuner/DOGE_USDT_15m/rl/best_train.yaml"
        ),
        config_snapshot=config_a,
        quick_mode=True,
    )
    seed_43 = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        command=(
            ".venv/bin/python scripts/autotuner/rl/prepare.py "
            "--config runs/autotuner/DOGE_USDT_15m/rl/best_train.yaml "
            "--seed 43 --quick"
        ),
        config_snapshot=config_a,
        quick_mode=True,
    )
    different_split = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        command=(
            ".venv/bin/python scripts/autotuner/rl/prepare.py "
            "--config runs/autotuner/DOGE_USDT_15m/rl/best_train.yaml --quick"
        ),
        config_snapshot="training:\n  seed: 42\nwf_n_folds: 4\n",
        quick_mode=True,
    )

    assert base["seed"] == 42
    assert seed_43["seed"] == 43
    assert base["validation_mode"] == "quick"
    assert full_mode["validation_mode"] == "full"
    assert trial_identity_hash(base) != trial_identity_hash(full_mode)
    assert trial_identity_hash(base) != trial_identity_hash(seed_43)
    assert trial_identity_hash(base) != trial_identity_hash(different_split)
