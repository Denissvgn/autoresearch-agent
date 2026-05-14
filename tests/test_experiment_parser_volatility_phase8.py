"""Tests for experiment_parser handling of phases 6-8 evidence keys emitted by volatility prepare.py.

Phases 6 (multi_seed_robustness), 7 (inference_parity_replay), and 8 (promotion_proposal)
use identical evidence key emission patterns in both direction and volatility prepare.py.
These tests verify the parser handles the volatility metric_name (auc vs composite_direction_score).
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


# ── Phase 6 (multi_seed_robustness) ──────────────────────────────────────────

def test_seed_trials_json_parsed_as_list() -> None:
    payload = [{"mlflow_run_id": "vol-run-abc123", "primary_metric": 0.62}]
    stdout = _block(f"seed_trials_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    assert "seed_trials" in m.extra
    assert isinstance(m.extra["seed_trials"], list)
    assert m.extra["seed_trials"][0]["mlflow_run_id"] == "vol-run-abc123"


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


# ── Phase 7 (inference_parity_replay) ────────────────────────────────────────

def test_inference_parity_json_parsed_as_dict() -> None:
    payload = {
        "feature_count_alignment_passed": True,
        "feature_name_alignment_passed": True,
        "model_roster_parity_passed": True,
        "mlflow_run_id": "vol-parity-abc123",
    }
    stdout = _block(f"inference_parity_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    assert "inference_parity" in m.extra
    assert isinstance(m.extra["inference_parity"], dict)
    assert m.extra["inference_parity"]["feature_count_alignment_passed"] is True
    assert m.extra["inference_parity"]["mlflow_run_id"] == "vol-parity-abc123"


def test_inference_parity_hash_fallback() -> None:
    payload = {
        "feature_count_alignment_passed": True,
        "feature_name_alignment_passed": True,
        "model_roster_parity_passed": True,
        "mlflow_run_id": "cafebabe12345678",
    }
    stdout = _block(f"inference_parity_json: {json.dumps(payload)}")
    m = parse_prepare_output(stdout)
    run_id = m.extra["inference_parity"]["mlflow_run_id"]
    assert isinstance(run_id, str) and len(run_id) == 16


# ── Phase 8 (promotion_proposal) ─────────────────────────────────────────────

def test_promotion_scope_stored_in_extra() -> None:
    stdout = _block("promotion_scope: development")
    m = parse_prepare_output(stdout)
    assert "promotion_scope" in m.extra
    assert m.extra["promotion_scope"] == "development"


def test_promotion_scope_in_to_dict() -> None:
    stdout = _block("promotion_scope: development")
    d = parse_prepare_output(stdout).to_dict()
    assert "promotion_scope" in d
    assert d["promotion_scope"] == "development"
