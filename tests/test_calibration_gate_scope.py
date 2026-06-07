"""PR-9 Layer 8: the ``weak_calibration`` gate must evaluate the SERVED best-base
calibrated ECE (Option A serving), not the inert meta-stacker's full-validation ECE.

Same scope-fix class as the DM-3 ``signal_saturation`` resolver: reading
``calibration_full_validation.selected.ece`` (the never-served meta) produced a
phantom block (e.g. served ECE ~3.9e-17 but meta ECE 0.0677 > 0.05 cap).
"""
from __future__ import annotations

import json
from pathlib import Path

from src.core.development_gate_bundle import (
    evaluate_development_gate_bundle,
    load_gate_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _bundle():
    return load_gate_bundle(REPO_ROOT)


def _iteration(metrics: dict) -> dict:
    return {"iteration": 1, "metrics_json": json.dumps(metrics)}


def test_weak_calibration_reads_served_best_base_ece_not_meta() -> None:
    # Served best-base calibrated ECE ~0 (well-calibrated); the meta full-validation
    # selected ECE is 0.0677 > the 0.05 cap. The gate must use the served value.
    metrics = {
        "config": {
            "best_base_calibration": {"calibrated": {"ece": 3.9e-17}},
            "calibration_full_validation": {"selected": {"metrics": {"ece": 0.0677}}},
            "calibration_diagnostics": {"cal_ece_after": 1.8e-16},
        },
    }
    result = evaluate_development_gate_bundle(
        bundle=_bundle(), model_type="direction", best_iteration=_iteration(metrics),
    )
    assert "weak_calibration" not in result["blockers"]


def test_weak_calibration_still_blocks_when_served_ece_high() -> None:
    # Genuinely poor SERVED calibration (ECE 0.12 > 0.05) must still block, even
    # if the meta selected ECE happens to be low — the served value is authoritative.
    metrics = {
        "config": {
            "best_base_calibration": {"calibrated": {"ece": 0.12}},
            "calibration_full_validation": {"selected": {"metrics": {"ece": 0.01}}},
        },
    }
    result = evaluate_development_gate_bundle(
        bundle=_bundle(), model_type="direction", best_iteration=_iteration(metrics),
    )
    assert "weak_calibration" in result["blockers"]
