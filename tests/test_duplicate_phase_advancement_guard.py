"""Post-``res_99469dfc1088`` defense-in-depth — rejected-duplicate
iterations must not count toward phase advancement.

Live evidence: in session ``res_99469dfc1088`` (2026-05-20 21:55→22:59 UTC):
- iter 2 was ``rejected_duplicate`` in ``tabular_sweeps`` but carried a
  server-injected ``tabular_sweep_variant`` (Gap 1 regression, since
  patched at the orchestrator level). The phase plan still completed
  ``tabular_sweeps`` because ``_has_metric`` saw the marker key on the
  duplicate iter and the cardinality check counted it.
- iter 12 was ``rejected_duplicate`` in ``inference_parity_replay`` and
  contributed to satisfying Gap 2's floor=2, despite no training having
  run (only iter 11 was genuine).

The orchestrator-side Gap 1 patch closes the variant-injection path. This
file's tests verify the *phase-plan-side* defense: `_completed_phase_ids`
filters rejected-duplicate iters globally so the cardinality fallback and
any agent-emitted advancement key on a duplicate are both ignored.
"""
from __future__ import annotations

import json

from src.core.research_phase_plan import _completed_phase_ids


def _iter(
    *,
    iteration: int,
    search_phase: str,
    metrics: dict | None = None,
    duplicate_reason: str | None = None,
    config_snapshot: str | None = None,
    decision: str = "keep",
) -> dict:
    metrics = dict(metrics or {})
    if duplicate_reason and "status" not in metrics:
        metrics["status"] = "rejected_duplicate"
    return {
        "iteration": iteration,
        "search_phase": search_phase,
        "metrics_json": json.dumps(metrics) if metrics else None,
        "decision": decision,
        "duplicate_reason": duplicate_reason,
        "config_snapshot": config_snapshot,
        "primary_metric": metrics.get("primary_metric"),
        "metric_name": metrics.get("metric_name"),
    }


def _baseline_iter() -> dict:
    """A genuine baseline iter so `baseline_capture` is satisfied and the
    duplicate-filter test focuses on the tail-phase semantics."""
    return _iter(
        iteration=1,
        search_phase="baseline_capture",
        metrics={"primary_metric": 0.57, "all_gates_passed": True},
        config_snapshot="agent_strategy: BALA\ndirection_pct_threshold: 0.03\n",
    )


# --- Negative cases: duplicates must not advance phases ---------------- #


def test_rejected_duplicate_with_advancement_key_does_not_complete_phase() -> None:
    """The live `res_99469dfc1088` iter-2 scenario: a rejected-duplicate
    iter tagged tabular_sweeps that carries an injected
    `tabular_sweep_variant` must NOT complete the phase.
    """
    iters = [
        _baseline_iter(),
        _iter(
            iteration=2,
            search_phase="tabular_sweeps",
            metrics={"tabular_sweep_variant": "direction_pct_threshold=0.05"},
            duplicate_reason="Duplicate training attempt rejected: same canonical config…",
        ),
    ]
    completed = _completed_phase_ids(iters, [], [], "direction")
    assert "tabular_sweeps" not in completed, (
        "A rejected_duplicate iter carrying an injected advancement marker "
        "must not complete tabular_sweeps. The orchestrator-side guard "
        "prevents the injection going forward; this filter is defense-in-depth "
        "against agent-emitted markers on duplicates and against legacy rows."
    )


def test_rejected_duplicate_does_not_count_toward_cardinality_floor() -> None:
    """The live `res_99469dfc1088` iter-12 scenario: Gap 2's floor=2 for
    inference_parity_replay was satisfied by iter 11 (genuine) + iter 12
    (duplicate). After filtering, only iter 11 counts → floor not met."""
    parity_evidence = {
        "inference_parity": {
            "feature_count_alignment_passed": True,
            "feature_name_alignment_passed": True,
            "model_roster_parity_passed": True,
            "mlflow_run_id": "run-genuine",
        },
        "mlflow_run_id": "run-genuine",
        "auto_phase_evidence": True,
    }
    iters = [
        _baseline_iter(),
        _iter(
            iteration=11,
            search_phase="inference_parity_replay",
            metrics={"primary_metric": 0.64, "training_time_s": 270.0, **parity_evidence},
        ),
        _iter(
            iteration=12,
            search_phase="inference_parity_replay",
            metrics={"tabular_sweep_variant": "direction_pct_threshold=0.05"},
            duplicate_reason="Duplicate training attempt rejected…",
        ),
    ]
    completed = _completed_phase_ids(iters, [], [], "direction")
    assert "inference_parity_replay" not in completed, (
        "Gap 2 floor=2 must require 2 GENUINE in-phase iters, not 1 genuine "
        "+ 1 rejected duplicate. Iter 12 contributes no training, so the "
        "floor is unmet with only iter 11 in-phase."
    )


def test_duplicate_iter_filtered_by_duplicate_reason_column() -> None:
    """Defensive: the iteration row's `duplicate_reason` column alone is
    enough to filter, even if metrics_json doesn't carry
    `status: rejected_duplicate` (older rows, partial writes)."""
    iters = [
        _baseline_iter(),
        # No `status` field in metrics, but duplicate_reason column is set.
        _iter(
            iteration=2,
            search_phase="tabular_sweeps",
            metrics={"tabular_sweep_variant": "direction_pct_threshold=0.05"},
            duplicate_reason="Duplicate from prior session",
        ),
    ]
    # Mutate metrics_json to remove the auto-added status, simulating an
    # older row where only the duplicate_reason column was set.
    raw = json.loads(iters[1]["metrics_json"])
    raw.pop("status", None)
    iters[1]["metrics_json"] = json.dumps(raw)

    completed = _completed_phase_ids(iters, [], [], "direction")
    assert "tabular_sweeps" not in completed, (
        "duplicate_reason column alone must be enough to filter the iter"
    )


def test_duplicate_iter_filtered_by_status_in_metrics_json() -> None:
    """Defensive symmetry: metrics_json's `status: rejected_duplicate` is
    also authoritative, even if duplicate_reason column is empty.
    Catches paths where the marker is set at metrics level only."""
    iters = [
        _baseline_iter(),
        _iter(
            iteration=2,
            search_phase="tabular_sweeps",
            metrics={
                "tabular_sweep_variant": "direction_pct_threshold=0.05",
                "status": "rejected_duplicate",
            },
            duplicate_reason=None,  # column NOT set, only metrics_json.status
        ),
    ]
    completed = _completed_phase_ids(iters, [], [], "direction")
    assert "tabular_sweeps" not in completed, (
        "status:rejected_duplicate in metrics_json must filter the iter "
        "even when the duplicate_reason column is empty"
    )


# --- Positive control: filter does not over-block ---------------------- #


def test_two_genuine_in_phase_iters_complete_phase_with_one_duplicate_present() -> None:
    """The duplicate is filtered out, but the 2 genuine in-phase iters
    still satisfy Gap 2's floor=2 for calibration_replay_gates."""
    cal_evidence = {
        "calibration_full_validation": {
            "version": 1,
            "selected": {"artifact_hash": "abc123"},
        },
        "economic_replay": {
            "source": "training_gates_proxy",
            "gates": {"all_gates_passed": True, "source": "training_gates_proxy"},
        },
        "auto_phase_evidence": True,
    }
    iters = [
        _baseline_iter(),
        _iter(
            iteration=2,
            search_phase="calibration_replay_gates",
            metrics={"primary_metric": 0.64, "training_time_s": 273.0, **cal_evidence},
        ),
        _iter(
            iteration=3,
            search_phase="calibration_replay_gates",
            metrics={"primary_metric": 0.63, "training_time_s": 271.0, **cal_evidence},
        ),
        _iter(
            iteration=4,
            search_phase="calibration_replay_gates",
            duplicate_reason="duplicate of iter 2",
        ),
    ]
    completed = _completed_phase_ids(iters, [], [], "direction")
    assert "calibration_replay_gates" in completed, (
        "Two GENUINE in-phase iters satisfy floor=2; the rejected duplicate "
        "is filtered but doesn't block the legitimate completion"
    )


def test_duplicate_does_not_block_baseline_capture() -> None:
    """When the only iter is a rejected_duplicate, baseline_capture must
    NOT be marked complete (no genuine iter exists). When a genuine
    baseline iter coexists with a duplicate, baseline_capture IS complete.
    """
    # Case 1: only a duplicate exists → baseline_capture NOT complete.
    only_dup = [
        _iter(
            iteration=1,
            search_phase="baseline_capture",
            duplicate_reason="dup",
            metrics={"primary_metric": 0.5},
        ),
    ]
    completed = _completed_phase_ids(only_dup, [], [], "direction")
    assert "baseline_capture" not in completed, (
        "After filtering the duplicate, no iterations remain — baseline_capture "
        "must NOT be marked complete (the `if iterations:` check uses the "
        "filtered list)."
    )

    # Case 2: genuine baseline + duplicate sibling → baseline_capture IS complete.
    mixed = [
        _baseline_iter(),
        _iter(
            iteration=2,
            search_phase="baseline_capture",
            duplicate_reason="dup",
            metrics={"primary_metric": 0.57},
        ),
    ]
    completed_mixed = _completed_phase_ids(mixed, [], [], "direction")
    assert "baseline_capture" in completed_mixed, (
        "A genuine baseline iter alongside a duplicate must still complete "
        "the phase — the filter removes the duplicate, the genuine one remains."
    )
