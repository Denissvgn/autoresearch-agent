from __future__ import annotations

import json
from pathlib import Path

from src.core.iteration_snapshot import (
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
            "selected_feature_names_hash": "selected-sha",
            "feature_schema_flags": {
                "adaptive_levels": {
                    "enabled": True,
                    "version": "adaptive_levels.v1",
                    "selected_feature_names": ["return_1", "close_fib_bucket_24"],
                }
            },
            "n_features": 2,
            "rl_economic_replay_artifact_path": "/tmp/rl_economic_replay.json",
            "rl_economic_replay_artifact_hash": "rl-replay-sha",
        },
    )

    assert snapshot["schema_version"] == "autoresearch_iteration_attempt.v1"
    assert snapshot["status"] == "failed"
    assert snapshot["artifact_hash"] == "artifact-sha"
    assert snapshot["feature_schema_hash"] == "feature-sha"
    assert snapshot["selected_feature_names_hash"] == "selected-sha"
    assert snapshot["feature_schema_flags"]["adaptive_levels"]["enabled"] is True
    assert snapshot["n_features"] == 2
    assert snapshot["rl_economic_replay_artifact_path"] == (
        "/tmp/rl_economic_replay.json"
    )
    assert snapshot["rl_economic_replay_artifact_hash"] == "rl-replay-sha"
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


def _rl_identity(config_snapshot, *, source_model_ids=None):
    return build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        command=(
            ".venv/bin/python scripts/autotuner/rl/prepare.py "
            "--config runs/autotuner/DOGE_USDT_15m/rl/best_train.yaml --quick"
        ),
        config_snapshot=config_snapshot,
        quick_mode=True,
        source_model_ids=source_model_ids,
    )


def test_source_model_ids_distinguish_upstream_model_swaps():
    """Folding upstream direction/volatility run-ids into data_split_id makes a run
    against retrained source models distinct from the stale run (no manual seed
    bump). Same ids → same identity (dedup still fires); None → legacy behavior."""
    config = "training:\n  seed: 42\nwf_n_folds: 3\n"

    legacy = _rl_identity(config)  # no source_model_ids → split-only (pre-change)
    none_explicit = _rl_identity(config, source_model_ids=None)
    empty = _rl_identity(config, source_model_ids={})
    models_v1 = _rl_identity(
        config,
        source_model_ids={
            "direction_source_run_id": "dir_run_aaa",
            "volatility_source_run_id": "vol_run_111",
        },
    )
    models_v1_again = _rl_identity(
        config,
        source_model_ids={
            "direction_source_run_id": "dir_run_aaa",
            "volatility_source_run_id": "vol_run_111",
        },
    )
    models_v2 = _rl_identity(
        config,
        source_model_ids={
            "direction_source_run_id": "dir_run_bbb",  # direction re-promoted
            "volatility_source_run_id": "vol_run_111",
        },
    )

    # Back-compat: None / empty leave the split id exactly as before.
    assert legacy["data_split_id"] == none_explicit["data_split_id"]
    assert legacy["data_split_id"] == empty["data_split_id"]
    assert trial_identity_hash(legacy) == trial_identity_hash(none_explicit)

    # Source models present → different split id than the source-less legacy run.
    assert models_v1["data_split_id"] != legacy["data_split_id"]
    # A model swap (different upstream run-id) → a different, non-duplicate identity.
    assert trial_identity_hash(models_v1) != trial_identity_hash(models_v2)
    # Identical upstream models → identical identity, so true duplicates still dedup.
    assert trial_identity_hash(models_v1) == trial_identity_hash(models_v1_again)


def test_explicit_split_id_without_sources_is_unchanged():
    """A bare explicit split id with no source models is returned verbatim (the
    pre-source-aware behavior), so existing identities are not perturbed."""
    config = "data_split_id: doge_15m_split_v7\n"
    identity = _rl_identity(config)
    assert identity["data_split_id"] == "doge_15m_split_v7"
