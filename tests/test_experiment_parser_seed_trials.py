"""Tests for experiment_parser _json suffix handling for phase 6 evidence keys.

Verifies that seed_trials_json, n_seed_trials_json, and seeds_passed_gates emitted
by prepare.py are parsed correctly by parse_prepare_output() so that
check_evidence_artifact() can advance multi_seed_robustness.

Critical: n_seed_trials must be stored as int (not float). Plain numeric values
are stored as float by the parser fallback; the _json suffix forces json.loads()
which preserves int type. The validator does isinstance(n_required, int) and
resets to 2 if it gets a float, which would cause a single-seed probe to fail.
"""
from __future__ import annotations

import json

from src.core.experiment_parser import parse_prepare_output


def _block(extra_lines: str = "") -> str:
    return (
        "\n"
        "---\n"
        "status:             completed\n"
        "primary_metric:     0.6500\n"
        "metric_name:        composite_direction_score\n"
        "direction:          higher_is_better\n"
        "all_gates_passed:   true\n"
        "training_time_s:    120.0\n"
        f"{extra_lines}\n"
        "---\n"
    )


def test_seed_trials_json_parsed_as_list() -> None:
    payload = [{"mlflow_run_id": "run-abc123", "primary_metric": 0.65}]
    stdout = _block(f"seed_trials_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    assert "seed_trials" in m.extra
    assert isinstance(m.extra["seed_trials"], list)
    assert m.extra["seed_trials"][0]["mlflow_run_id"] == "run-abc123"


def test_n_seed_trials_json_stored_as_int() -> None:
    stdout = _block("n_seed_trials_json: 1")
    m = parse_prepare_output(stdout)
    assert "n_seed_trials" in m.extra
    assert m.extra["n_seed_trials"] == 1
    assert isinstance(m.extra["n_seed_trials"], int), (
        "n_seed_trials must be int — consistency_validator resets to n_required=2 "
        "if isinstance(n_required, int) is False (e.g. float 1.0)"
    )


def test_seeds_passed_gates_stored() -> None:
    stdout = _block("seeds_passed_gates: 1")
    m = parse_prepare_output(stdout)
    assert "seeds_passed_gates" in m.extra


def test_all_three_seed_keys_in_to_dict() -> None:
    trials = [{"mlflow_run_id": "run-xyz", "primary_metric": 0.70}]
    stdout = _block(
        f"seed_trials_json: {json.dumps(trials)}\n"
        "n_seed_trials_json: 1\n"
        "seeds_passed_gates: 1"
    )
    d = parse_prepare_output(stdout).to_dict()
    assert "seed_trials" in d
    assert "n_seed_trials" in d
    assert isinstance(d["n_seed_trials"], int)
    assert d["n_seed_trials"] == 1


def test_seed_trials_artifact_hash_fallback() -> None:
    trials = [{"artifact_hash": "deadbeef1234abcd", "primary_metric": 0.62}]
    stdout = _block(f"seed_trials_json: {json.dumps(trials)}")
    m = parse_prepare_output(stdout)
    assert m.extra["seed_trials"][0]["artifact_hash"] == "deadbeef1234abcd"
