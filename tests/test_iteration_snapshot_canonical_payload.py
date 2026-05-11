"""AR-1: Tests for canonical_config_payload / canonical_config_hash hardening.

Covers the crash path where the LLM emits ``config_snapshot`` as a JSON object
(Python dict) instead of a YAML text string, e.g.:
  ITERATION_RESULT: {"config_snapshot": {"learning_rate": 0.001, ...}, ...}
"""

from __future__ import annotations

import hashlib
import json

import pytest

from src.core.iteration_snapshot import (
    build_iteration_attempt_snapshot,
    build_trial_identity,
    canonical_config_hash,
    canonical_config_payload,
)


# ---------------------------------------------------------------------------
# canonical_config_payload
# ---------------------------------------------------------------------------


def test_canonical_config_payload_handles_dict_input():
    """Dict input must canonicalise without raising AttributeError."""
    result = canonical_config_payload({"a": 1, "b": [1, 2]})
    assert result == {"a": 1, "b": [1, 2]}


def test_canonical_config_payload_dict_keys_sorted():
    """Dict path must sort keys for deterministic output."""
    result = canonical_config_payload({"z": 3, "a": 1, "m": 2})
    assert list(result.keys()) == ["a", "m", "z"]


def test_canonical_config_payload_nested_dict_input():
    """Nested dicts within a dict config_snapshot are canonicalised recursively."""
    result = canonical_config_payload(
        {"training": {"seed": 42, "lr": 1e-3}, "wf_n_folds": 3}
    )
    assert result["training"]["seed"] == 42
    assert result["wf_n_folds"] == 3


def test_canonical_config_payload_handles_yaml_string():
    """YAML string input still works (regression guard for existing behaviour)."""
    result = canonical_config_payload("training:\n  seed: 42\nwf_n_folds: 3\n")
    assert result == {"training": {"seed": 42}, "wf_n_folds": 3}


def test_canonical_config_payload_handles_none():
    """None input returns None."""
    assert canonical_config_payload(None) is None


def test_canonical_config_payload_handles_empty_string():
    """Empty string returns empty dict (not None)."""
    assert canonical_config_payload("") == {}


def test_canonical_config_payload_handles_list_input():
    """List input canonicalises without exception."""
    result = canonical_config_payload([1, 2, 3])
    assert result == [1, 2, 3]


def test_canonical_config_payload_handles_tuple_input():
    """Tuple input is treated like a list."""
    result = canonical_config_payload((1, 2, 3))
    assert result == [1, 2, 3]


# ---------------------------------------------------------------------------
# canonical_config_hash stability guarantee
# ---------------------------------------------------------------------------


def test_canonical_config_hash_stable_across_dict_and_equivalent_yaml():
    """A dict and its YAML-serialised equivalent must produce the same hash.

    This is the core invariant: the orchestrator should NOT produce a different
    canonical_config_hash depending on whether the LLM returned config_snapshot
    as a JSON object or as a YAML text string.
    """
    hash_from_dict = canonical_config_hash({"a": 1})
    hash_from_yaml = canonical_config_hash("a: 1\n")
    assert hash_from_dict is not None
    assert hash_from_yaml is not None
    assert hash_from_dict == hash_from_yaml


def test_canonical_config_hash_stable_across_key_order():
    """Key order must not affect the hash (both dict and YAML paths)."""
    h1 = canonical_config_hash({"z": 3, "a": 1})
    h2 = canonical_config_hash({"a": 1, "z": 3})
    assert h1 == h2


def test_canonical_config_hash_none_returns_none():
    assert canonical_config_hash(None) is None


def test_canonical_config_hash_dict_is_deterministic():
    """Repeated calls with the same dict must return the same hash."""
    payload = {"learning_rate": 0.001, "n_estimators": 100}
    assert canonical_config_hash(payload) == canonical_config_hash(payload)


# ---------------------------------------------------------------------------
# build_trial_identity with dict config_snapshot (the actual crash scenario)
# ---------------------------------------------------------------------------


def test_build_trial_identity_dict_config_snapshot_no_crash():
    """build_trial_identity must not crash when config_snapshot is a dict.

    Reproduces the crash from res_a1ba6cbd520f where the LLM emitted
    config_snapshot as a JSON object on the ITERATION_RESULT marker.
    """
    identity = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        command=None,
        config_snapshot={"learning_rate": 0.001, "n_estimators": 100},
        quick_mode=False,
    )
    # canonical_config_hash must be non-null since we have a real config
    assert identity["canonical_config_hash"] is not None
    assert identity["instrument"] == "DOGE_USDT"


def test_build_trial_identity_dict_and_yaml_produce_same_hash():
    """dict and YAML-string config_snapshot produce the same canonical hash."""
    yaml_snapshot = "learning_rate: 0.001\nn_estimators: 100\n"
    dict_snapshot = {"learning_rate": 0.001, "n_estimators": 100}

    id_yaml = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        command=None,
        config_snapshot=yaml_snapshot,
        quick_mode=False,
    )
    id_dict = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        command=None,
        config_snapshot=dict_snapshot,
        quick_mode=False,
    )
    assert id_yaml["canonical_config_hash"] == id_dict["canonical_config_hash"]


# ---------------------------------------------------------------------------
# build_iteration_attempt_snapshot with dict config_snapshot
# ---------------------------------------------------------------------------


def test_build_iteration_attempt_snapshot_dict_config_snapshot_no_crash(tmp_path):
    """build_iteration_attempt_snapshot must not crash when config_snapshot is a dict.

    Without the _sha256_text fix this raises:
      AttributeError: 'dict' object has no attribute 'encode'
    """
    snapshot = build_iteration_attempt_snapshot(
        research_id="res_test",
        iteration=1,
        turn=5,
        command=".venv/bin/python scripts/autotuner/direction/prepare.py",
        config_snapshot={"learning_rate": 0.001},
        workspace=str(tmp_path),
    )
    assert snapshot["config_snapshot_sha256"] is not None
    assert snapshot["canonical_config_hash"] is not None
    # The sha256 must be a valid 64-char hex string
    assert len(snapshot["config_snapshot_sha256"]) == 64
