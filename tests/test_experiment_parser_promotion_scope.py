"""Tests for experiment_parser handling of phase 8 evidence key (promotion_scope).

Verifies that promotion_scope emitted by prepare.py is stored correctly by
parse_prepare_output() so that _has_metric() can detect it and advance
promotion_proposal. No _json suffix needed — key presence is all that matters.
"""
from __future__ import annotations

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


def test_promotion_scope_absent_when_not_emitted() -> None:
    stdout = _block()
    m = parse_prepare_output(stdout)
    assert "promotion_scope" not in m.extra
