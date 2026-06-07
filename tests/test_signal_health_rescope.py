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


def test_signal_saturation_does_not_block_when_only_oof_youden_exceeds_cap() -> None:
    """DM-3: regression for the phantom signal_saturation blocker observed on
    res_be66790e192e. The *deployed* operating signal rate (0.199 on the
    served threshold) passes the 0.35 cap, but an OOF / Youden-J variant
    (0.765) is also present in ``gate_results``. The previous
    ``_max_number(...)`` aggregation took ``max(0.199, 0.765) = 0.765`` and
    tripped the gate; the precedence-ordered resolver must pick the
    higher-trust deployed value first and ignore the lower-trust OOF entry."""
    metrics = {
        # Untagged Youden-J / OOF variant bleeding into the gate-results bag.
        # Lowest precedence in the resolver — must NOT win over canonical
        # deployed sources higher up.
        "gate_results": {"operating_signal_rate": 0.765},
        # Deployed operating rate emitted by prepare.py (the value the
        # inference service will actually serve). Higher precedence.
        "signal_rate": 0.199,
        "signal_health": {
            "metrics": {
                "probability_mean": 0.61,
                "probability_std": 0.08,
                "entropy_mean": 0.74,
                "signal_rate": 0.199,
            },
        },
    }
    result = evaluate_development_gate_bundle(
        bundle=_bundle(), model_type="direction", best_iteration=_iteration(metrics),
    )
    assert "signal_saturation" not in result["blockers"]


def test_signal_saturation_does_not_block_when_fold_max_within_distribution_buffer() -> None:
    """DM-3 distribution-gate scope: ``signal_rate_distribution.max`` is the
    walk-forward per-fold max, NOT the single served operating point. The
    previous gate compared it against ``max_signal_rate`` (the operating
    cap, e.g. 0.35), which is the wrong scope — per-fold variance naturally
    runs higher than the operating mean. With the operating served rate at
    0.249 (well under 0.35) and fold-3 at 0.361, the gate must use the
    looser distribution threshold (default ``max_signal_rate * 1.2 = 0.42``)
    and not block. Mirrors the actual data from res_be66790e192e iter 7."""
    metrics = {
        # Deployed served rate — passes the operating cap.
        "signal_rate": 0.249,
        "gate_results": {"operating_signal_rate": 0.249},
        # Per-fold distribution from served_best_base_at_operating_threshold.
        # max=0.361 > operating cap 0.35 but within the per-fold variance
        # buffer (0.42).
        "config": {
            "calibration_full_validation": {
                "signal_rate_distribution": {
                    "by_fold": [0.318, 0.300, 0.361],
                    "max": 0.361,
                    "mean": 0.326,
                    "min": 0.300,
                    "source": "served_best_base_at_operating_threshold",
                },
            },
        },
        "signal_health": {
            "metrics": {
                "probability_mean": 0.61,
                "probability_std": 0.08,
                "entropy_mean": 0.74,
                "signal_rate": 0.249,
            },
        },
    }
    result = evaluate_development_gate_bundle(
        bundle=_bundle(), model_type="direction", best_iteration=_iteration(metrics),
    )
    assert "signal_saturation" not in result["blockers"]


def test_signal_saturation_blocks_when_fold_max_exceeds_distribution_buffer() -> None:
    """DM-3 mirror: the distribution gate must still block when per-fold
    saturation is genuinely above the configured ``max_signal_rate_distribution``
    (PR-9: 0.6). Guards against the looser threshold becoming a free pass."""
    metrics = {
        "signal_rate": 0.30,
        "gate_results": {"operating_signal_rate": 0.30},
        "config": {
            "calibration_full_validation": {
                "signal_rate_distribution": {
                    "by_fold": [0.55, 0.60, 0.66],
                    "max": 0.66,  # > 0.6 distribution cap
                    "mean": 0.60,
                    "source": "served_best_base_at_operating_threshold",
                },
            },
        },
        "signal_health": {
            "metrics": {
                "probability_mean": 0.61,
                "probability_std": 0.08,
                "entropy_mean": 0.74,
                "signal_rate": 0.30,
            },
        },
    }
    result = evaluate_development_gate_bundle(
        bundle=_bundle(), model_type="direction", best_iteration=_iteration(metrics),
    )
    assert "signal_saturation" in result["blockers"]


def test_signal_saturation_distribution_uses_separate_looser_threshold() -> None:
    """PR-9: the per-fold signal-rate DISTRIBUTION (walk-forward variance) is gated
    by the separate, looser ``max_signal_rate_distribution`` (0.6) — NOT the
    operating cap. The served operating rate passes (0.348 <= 0.35); a fold-max of
    0.543 must not trip a phantom signal_saturation."""
    metrics = {
        "operating_signal_rate": 0.348,
        "signal_rate": 0.348,
        "config": {
            "operating_signal_rate": 0.348,
            "calibration_full_validation": {
                "signal_rate_distribution": {
                    "max": 0.543, "mean": 0.424, "by_fold": [0.434, 0.294, 0.543],
                },
            },
        },
    }
    result = evaluate_development_gate_bundle(
        bundle=_bundle(), model_type="direction", best_iteration=_iteration(metrics),
    )
    assert "signal_saturation" not in result["blockers"]


def test_signal_saturation_distribution_still_blocks_extreme_folds() -> None:
    """A uniformly-saturating model (fold-max 0.72 > 0.6 distribution cap) must
    still trip signal_saturation even when the operating rate looks fine."""
    metrics = {
        "operating_signal_rate": 0.30,
        "signal_rate": 0.30,
        "config": {
            "operating_signal_rate": 0.30,
            "calibration_full_validation": {
                "signal_rate_distribution": {"max": 0.72, "mean": 0.66},
            },
        },
    }
    result = evaluate_development_gate_bundle(
        bundle=_bundle(), model_type="direction", best_iteration=_iteration(metrics),
    )
    assert "signal_saturation" in result["blockers"]
