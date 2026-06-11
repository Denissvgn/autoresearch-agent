"""Track D2 — bash output digest before agent context.

Pins:
1. Small outputs pass through byte-identical (no behavior change for normal
   commands).
2. Training-stream digests keep the decision inputs — ITERATION_RESULT, the
   final ``---`` metrics block, errors, per-fold gate lines — while progress
   ticks and library noise collapse into counters.
3. The hard cap holds even for pathological outputs.
"""
from __future__ import annotations

from src.core.output_digest import DEFAULT_MAX_CHARS, digest_command_output


def _training_stream(n_progress: int = 2000) -> str:
    lines = [f"[prepare] Starting run with config x.yaml param_{i}" for i in range(10)]
    lines += [
        f"[prepare] Training in progress... {i}.0m elapsed | "
        "2026-06-11 src.data.feature_loader - INFO - Using feature library version: 2.3.0"
        for i in range(n_progress)
    ]
    lines += [
        "2026-06-11 matplotlib.font_manager - INFO - generated new fontManager",
        "2026-06-11 alembic.runtime.migration - INFO - Will assume non-transactional DDL.",
        "Downloading artifacts:  45%|████      | 5/11",
        "fold_1:          PASS sharpe=0.1 ret=0.02 dd=0.01 trades=120",
        "fold_2:          FAIL sharpe=0.0 ret=0.00 dd=0.00 trades=0 FAILED:[oos_sharpe=0.0029]",
        "Some ERROR: ValueError: bad things happened",
    ]
    lines += [f"summary line {i}" for i in range(50)]
    lines += [
        "---",
        "primary_metric: 0.4387",
        "metric_name: composite_direction_score",
        "all_gates_passed: true",
        "selective_auc_top25: 0.6855",
        "---",
        'ITERATION_RESULT: {"iteration": 5, "primary_metric": 0.4387, "decision": "keep"}',
    ]
    return "\n".join(lines)


def test_small_output_unchanged() -> None:
    out = "hello\nworld"
    assert digest_command_output(out) == out


def test_training_stream_keeps_decision_inputs() -> None:
    raw = _training_stream()
    digest = digest_command_output(raw, full_log_path="runs/x/command_logs/t1.log")

    assert len(digest) < len(raw) / 5  # massive reduction
    assert "ITERATION_RESULT" in digest
    assert "primary_metric: 0.4387" in digest          # metrics block survived
    assert "selective_auc_top25: 0.6855" in digest
    assert "fold_2:          FAIL" in digest           # gate lines survived
    assert "ValueError: bad things happened" in digest # errors survived
    assert "training-progress tick ×" in digest        # noise collapsed, counted
    assert "full log: runs/x/command_logs/t1.log" in digest
    # raw progress spam is gone
    assert digest.count("Training in progress") <= 2


def test_hard_cap_holds() -> None:
    # pathological: every line matches a keep pattern
    raw = "\n".join(f"ERROR line {i} " + "x" * 200 for i in range(5000))
    digest = digest_command_output(raw, max_chars=10_000)
    assert len(digest) <= 10_000 + 300  # cap + footer slack


def test_disabled_via_zero_max_chars() -> None:
    raw = _training_stream()
    assert digest_command_output(raw, max_chars=0) == raw


def test_no_metrics_block_still_works() -> None:
    raw = "\n".join(f"plain line {i}" for i in range(3000))
    digest = digest_command_output(raw, max_chars=5_000)
    assert len(digest) <= 5_300
    assert "output digest:" in digest


def test_default_cap_sane() -> None:
    assert DEFAULT_MAX_CHARS == 12_000
