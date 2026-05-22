"""Fix B1: re-scoped development signal-health gate.

Drift + operational serving counters moved to production scope; the dev gate
now needs only what a sandbox paper-replay can produce (probability summary,
entropy, signal rate). These tests confirm the gate is satisfiable by that
evidence — and that the genuine signal_saturation gate still blocks.
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


def test_signal_health_passes_with_sandbox_evidence_only() -> None:
    """probability summary + entropy + signal_rate present, NO drift / NO
    operational counters → signal-health tier no longer blocks."""
    metrics = {
        "signal_health": {
            "metrics": {
                "probability_mean": 0.61,
                "probability_std": 0.08,
                "entropy_mean": 0.74,
                "signal_rate": 0.30,
            },
            # Deliberately no "drift" and no full "operational" block —
            # those are now production-scope.
        },
    }
    result = evaluate_development_gate_bundle(
        bundle=_bundle(), model_type="direction", best_iteration=_iteration(metrics),
    )
    assert "missing_signal_health_metrics" not in result["blockers"]


def test_signal_health_still_blocks_when_payload_absent() -> None:
    result = evaluate_development_gate_bundle(
        bundle=_bundle(), model_type="direction", best_iteration=_iteration({}),
    )
    assert "missing_signal_health_metrics" in result["blockers"]


def test_signal_saturation_still_blocks_when_rate_exceeds_cap() -> None:
    """The genuine model-quality gate (operating signal rate above the 0.35
    cap) is independent of the re-scope and must still block."""
    metrics = {
        "gate_results": {"operating_signal_rate": 0.50},
        "signal_rate": 0.50,
        "signal_health": {
            "metrics": {
                "probability_mean": 0.61,
                "probability_std": 0.08,
                "entropy_mean": 0.74,
                "signal_rate": 0.50,
            },
        },
    }
    result = evaluate_development_gate_bundle(
        bundle=_bundle(), model_type="direction", best_iteration=_iteration(metrics),
    )
    assert "signal_saturation" in result["blockers"]
