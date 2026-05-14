"""Tests for experiment_parser _json suffix handling for phase 7 evidence keys.

Verifies that inference_parity_json emitted by prepare.py is parsed into a
dict-valued extra by parse_prepare_output(), so that _has_metric() detects the
key and check_evidence_artifact() can advance inference_parity_replay.
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


def test_inference_parity_json_parsed_as_dict() -> None:
    payload = {
        "feature_count_alignment_passed": True,
        "feature_name_alignment_passed": True,
        "model_roster_parity_passed": True,
        "mlflow_run_id": "run-parity-abc123",
    }
    stdout = _block(f"inference_parity_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    assert "inference_parity" in m.extra
    assert isinstance(m.extra["inference_parity"], dict)
    assert m.extra["inference_parity"]["feature_count_alignment_passed"] is True
    assert m.extra["inference_parity"]["mlflow_run_id"] == "run-parity-abc123"


def test_inference_parity_in_to_dict() -> None:
    payload = {
        "feature_count_alignment_passed": True,
        "feature_name_alignment_passed": True,
        "model_roster_parity_passed": True,
        "mlflow_run_id": "run-xyz",
    }
    stdout = _block(f"inference_parity_json: {json.dumps(payload)}")
    d = parse_prepare_output(stdout).to_dict()
    assert "inference_parity" in d
    assert d["inference_parity"]["feature_count_alignment_passed"] is True


def test_inference_parity_hash_fallback_structure() -> None:
    payload = {
        "feature_count_alignment_passed": True,
        "feature_name_alignment_passed": True,
        "model_roster_parity_passed": True,
        "mlflow_run_id": "a1b2c3d4e5f60718",
    }
    stdout = _block(f"inference_parity_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    run_id = m.extra["inference_parity"]["mlflow_run_id"]
    assert isinstance(run_id, str) and len(run_id) == 16


def test_missing_inference_parity_produces_no_extra() -> None:
    stdout = _block()
    m = parse_prepare_output(stdout)
    assert "inference_parity" not in m.extra
