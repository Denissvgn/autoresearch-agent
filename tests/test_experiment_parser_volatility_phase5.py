"""Tests for experiment_parser handling of phase 5 evidence keys emitted by volatility prepare.py.

Volatility phase 5 (calibration_replay_gates): prepare.py builds a proxy
calibration_full_validation from a config-derived artifact_hash (no
calibration_full_validation key exists in volatility results.json).
The selected.artifact_hash is a 16-char hex string from hashlib.sha256.
"""
from __future__ import annotations

import json

from src.core.experiment_parser import parse_prepare_output


def _block(extra_lines: str = "") -> str:
    return (
        "\n"
        "---\n"
        "status:             completed\n"
        "primary_metric:     0.6200\n"
        "metric_name:        auc\n"
        "direction:          higher_is_better\n"
        "all_gates_passed:   true\n"
        "training_time_s:    95.0\n"
        f"{extra_lines}\n"
        "---\n"
    )


def _cal_payload(artifact_hash: str = "abcdef1234567890") -> dict:
    return {
        "version": 1,
        "n_samples": None,
        "probability_space": "volatility",
        "selected": {"artifact_hash": artifact_hash},
    }


def _eco_payload() -> dict:
    return {
        "source": "training_gates_proxy",
        "gates": {"all_gates_passed": True, "source": "training_gates_proxy"},
    }


def test_calibration_full_validation_parsed_as_dict() -> None:
    payload = _cal_payload()
    stdout = _block(f"calibration_full_validation_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    assert "calibration_full_validation" in m.extra
    assert isinstance(m.extra["calibration_full_validation"], dict)
    assert m.extra["calibration_full_validation"]["probability_space"] == "volatility"


def test_calibration_selected_has_artifact_hash() -> None:
    payload = _cal_payload("deadbeef0000cafe")
    stdout = _block(f"calibration_full_validation_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    selected = m.extra["calibration_full_validation"]["selected"]
    assert isinstance(selected, dict)
    assert selected["artifact_hash"] == "deadbeef0000cafe"


def test_economic_replay_parsed_as_dict() -> None:
    payload = _eco_payload()
    stdout = _block(f"economic_replay_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    assert "economic_replay" in m.extra
    assert isinstance(m.extra["economic_replay"]["gates"], dict)
    assert m.extra["economic_replay"]["gates"]["all_gates_passed"] is True


def test_both_phase5_keys_in_to_dict() -> None:
    lines = (
        f"calibration_full_validation_json: {json.dumps(_cal_payload())}\n"
        f"economic_replay_json: {json.dumps(_eco_payload())}"
    )
    d = parse_prepare_output(_block(lines)).to_dict()
    assert "calibration_full_validation" in d
    assert "economic_replay" in d


def test_phase5_absent_when_not_emitted() -> None:
    m = parse_prepare_output(_block())
    assert "calibration_full_validation" not in m.extra
    assert "economic_replay" not in m.extra
