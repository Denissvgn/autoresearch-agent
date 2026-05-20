"""Issue 8 — outcome taxonomy: distinguish consistency-blocked from training-failed.

A trained-successfully iteration (prepare.py status:completed, all_gates_passed:true)
whose only failure is a downstream consistency-validator block was previously
recorded with ``outcome:"failed"``, conflating it with crash/timeout/error. The
fix introduces ``outcome:"consistency_blocked"`` so retry/UI logic can treat
the two cases distinctly (do NOT retry as transient; address the blocker).

Behavior preserved for all other paths:
- crash/timeout/error/failed status → still "failed"
- rejected_duplicate → still "rejected_duplicate"
- pruned → still "pruned"
- decision=discard WITHOUT consistency block → still "failed"
- decision=keep WITHOUT consistency block → still "completed"
"""
from __future__ import annotations

import json

from src.core.results_store import _attempt_outcome


def _report(passed: bool, blockers=None):
    return json.dumps({"passed": passed, "blockers": list(blockers or [])})


def _row(**kw):
    base = {
        "decision": None,
        "all_gates_passed": False,
        "primary_metric": None,
        "duplicate_reason": None,
        "consistency_report_json": None,
    }
    base.update(kw)
    return base


# --- New behavior: consistency_blocked outcome --------------------------- #


def test_consistency_blocked_discard_returns_new_label():
    """The Issue-6/8 scenario: training succeeded, gates passed, but
    consistency validator blocked. Was 'failed', now 'consistency_blocked'.
    """
    row = _row(
        decision="discard",
        all_gates_passed=True,
        primary_metric=0.6447,
        consistency_report_json=_report(
            passed=False, blockers=["adaptive_feature_not_enabled"],
        ),
    )
    metrics = {"status": "completed", "all_gates_passed": True, "primary_metric": 0.6447}
    assert _attempt_outcome(row, metrics) == "consistency_blocked"


def test_consistency_blocked_keep_also_returns_new_label():
    """Decision is keep/discard answers a different question (metric improvement);
    consistency blocking should still surface even when the agent kept the iteration.
    """
    row = _row(
        decision="keep",
        all_gates_passed=True,
        primary_metric=0.6500,
        consistency_report_json=_report(
            passed=False, blockers=["adaptive_feature_not_enabled"],
        ),
    )
    metrics = {"status": "completed", "all_gates_passed": True, "primary_metric": 0.65}
    assert _attempt_outcome(row, metrics) == "consistency_blocked"


def test_consistency_blocked_with_success_status_returns_new_label():
    """`status: success` is treated equivalently to `completed`."""
    row = _row(
        decision="discard",
        all_gates_passed=True,
        consistency_report_json=_report(passed=False, blockers=["some_blocker"]),
    )
    metrics = {"status": "success"}
    assert _attempt_outcome(row, metrics) == "consistency_blocked"


# --- Regressions: unchanged behavior for non-consistency-block paths ----- #


def test_unchanged_real_training_crash_still_failed():
    row = _row(decision="discard", consistency_report_json=_report(passed=False))
    metrics = {"status": "crash"}
    # Crash short-circuits before the consistency check: it's a real training
    # failure, not a downstream block.
    assert _attempt_outcome(row, metrics) == "failed"


def test_unchanged_rejected_duplicate_still_rejected_duplicate():
    row = _row(duplicate_reason="duplicate canonical config")
    metrics = {"status": "rejected_duplicate"}
    assert _attempt_outcome(row, metrics) == "rejected_duplicate"


def test_unchanged_pruned_still_pruned():
    row = _row(decision="discard")
    metrics = {"status": "pruned"}
    assert _attempt_outcome(row, metrics) == "pruned"


def test_unchanged_completed_keep_with_passing_consistency():
    row = _row(
        decision="keep",
        all_gates_passed=True,
        primary_metric=0.65,
        consistency_report_json=_report(passed=True),
    )
    metrics = {"status": "completed"}
    assert _attempt_outcome(row, metrics) == "completed"


def test_completed_discard_with_passing_consistency_now_declined():
    """Issue 10B updated this assertion: completed + decision=discard +
    consistency pass is now 'declined' (was 'failed' pre-10B). 'failed' is
    reserved for training failures; see test_issue10b_declined_outcome.py.
    Issue 8 precedence (consistency_blocked > declined) is unaffected — see
    test_consistency_blocked_discard_returns_new_label above."""
    row = _row(
        decision="discard",
        all_gates_passed=True,
        primary_metric=0.6,
        consistency_report_json=_report(passed=True),
    )
    metrics = {"status": "completed"}
    assert _attempt_outcome(row, metrics) == "declined"


def test_unchanged_completed_when_no_consistency_report():
    """Defensive: missing consistency_report_json must not raise and must
    fall through to the pre-Issue-8 path."""
    row = _row(decision="keep", all_gates_passed=True, primary_metric=0.5)
    metrics = {"status": "completed"}
    assert _attempt_outcome(row, metrics) == "completed"


def test_malformed_consistency_report_does_not_raise():
    """Defensive: invalid JSON in consistency_report_json is treated as 'no
    block info', not a crash. Falls through to pre-Issue-8 outcome."""
    row = _row(
        decision="keep",
        all_gates_passed=True,
        consistency_report_json="{not valid json",
    )
    metrics = {"status": "completed"}
    assert _attempt_outcome(row, metrics) == "completed"


def test_consistency_report_as_dict_also_accepted():
    """Some code paths may pass the report as a dict rather than JSON string."""
    row = _row(
        decision="discard",
        all_gates_passed=True,
        consistency_report_json={"passed": False, "blockers": ["x"]},
    )
    metrics = {"status": "completed"}
    assert _attempt_outcome(row, metrics) == "consistency_blocked"
