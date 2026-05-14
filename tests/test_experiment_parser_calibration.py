"""Tests for experiment_parser _json suffix handling for phase 5 evidence keys.

Verifies that calibration_full_validation_json and economic_replay_json emitted
by prepare.py are parsed into dict-valued extras by parse_prepare_output(), so
that _has_metric() and check_evidence_artifact() can advance calibration_replay_gates.
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


def test_calibration_full_validation_json_parsed_as_dict() -> None:
    payload = {
        "version": 1,
        "n_samples": 500,
        "selected": {"artifact_hash": "abc123def456", "metrics": {"ece": 0.05}},
    }
    stdout = _block(f"calibration_full_validation_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    assert "calibration_full_validation" in m.extra
    assert isinstance(m.extra["calibration_full_validation"], dict)
    assert m.extra["calibration_full_validation"]["selected"]["artifact_hash"] == "abc123def456"


def test_economic_replay_json_parsed_as_dict() -> None:
    payload = {
        "source": "training_gates_proxy",
        "gates": {"all_gates_passed": True, "source": "training_gates_proxy"},
    }
    stdout = _block(f"economic_replay_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    assert "economic_replay" in m.extra
    assert isinstance(m.extra["economic_replay"], dict)
    assert isinstance(m.extra["economic_replay"]["gates"], dict)


def test_both_keys_appear_in_to_dict() -> None:
    cal = {"version": 1, "selected": {"artifact_hash": "deadbeef1234", "metrics": {"ece": 0.03}}}
    eco = {"source": "training_gates_proxy", "gates": {"all_gates_passed": False}}
    stdout = _block(
        f"calibration_full_validation_json: {json.dumps(cal)}\n"
        f"economic_replay_json: {json.dumps(eco)}"
    )
    d = parse_prepare_output(stdout).to_dict()
    assert "calibration_full_validation" in d
    assert "economic_replay" in d
    assert d["calibration_full_validation"]["selected"]["artifact_hash"] == "deadbeef1234"
    assert d["economic_replay"]["gates"]["all_gates_passed"] is False


def test_missing_calibration_keys_produce_no_extra() -> None:
    stdout = _block()
    m = parse_prepare_output(stdout)
    assert "calibration_full_validation" not in m.extra
    assert "economic_replay" not in m.extra


def test_json_suffix_also_stores_raw_key() -> None:
    payload = {"gates": {"all_gates_passed": True}}
    stdout = _block(f"economic_replay_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    # Parser stores both the _json key and the bare key
    assert "economic_replay_json" in m.extra
    assert "economic_replay" in m.extra
    assert m.extra["economic_replay_json"] == m.extra["economic_replay"]
