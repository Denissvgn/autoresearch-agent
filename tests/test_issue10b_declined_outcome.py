"""Issue 10B — outcome taxonomy: distinguish ``declined`` from ``failed``.

A trained-successfully iteration (prepare.py ``status:completed``,
``all_gates_passed:true``) that the agent declined because the metric did not
beat best was previously recorded with ``outcome:"failed"``, conflating it
with crash/timeout/error and inflating dashboard failure rates. Live evidence:
session ``res_dd666f273f99`` had 16 of 23 iterations in this exact shape
(``decision:discard`` + ``status:completed`` + ``all_gates_passed:true``).

The fix introduces ``outcome:"declined"`` with precedence:

    consistency_blocked  >  declined  >  failed

so a consistency-blocked run (Issue 8) is still ``consistency_blocked``, a real
training crash is still ``failed``, and only the previously mis-tagged path
becomes ``declined``.

Behavior preserved for all other paths:
- crash/timeout/error/failed status → still ``failed``
- rejected_duplicate → still ``rejected_duplicate``
- pruned → still ``pruned``
- decision=keep WITHOUT consistency block → still ``completed``
- decision=discard WITH unknown/empty status → still ``failed`` (legacy
  fall-through preserved for non-success status)
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


# --- New behavior: declined outcome ------------------------------------- #


def test_completed_discard_with_passing_consistency_returns_declined() -> None:
    """The Issue-10B scenario: training succeeded, gates passed, consistency
    passed, but the agent discarded because metric did not beat best.
    Was 'failed', now 'declined'."""
    row = _row(
        decision="discard",
        all_gates_passed=True,
        primary_metric=0.6,
        consistency_report_json=_report(passed=True),
    )
    metrics = {"status": "completed"}
    assert _attempt_outcome(row, metrics) == "declined"


def test_success_discard_with_passing_consistency_returns_declined() -> None:
    """`status: success` is treated equivalently to `completed`."""
    row = _row(
        decision="discard",
        all_gates_passed=True,
        primary_metric=0.6,
        consistency_report_json=_report(passed=True),
    )
    metrics = {"status": "success"}
    assert _attempt_outcome(row, metrics) == "declined"


def test_completed_discard_without_consistency_report_returns_declined() -> None:
    """Defensive: a missing consistency report is NOT a block. Older rows
    without a report and discard decision should now surface as 'declined'
    rather than the legacy 'failed' mis-tag."""
    row = _row(
        decision="discard",
        all_gates_passed=True,
        primary_metric=0.6,
        consistency_report_json=None,
    )
    metrics = {"status": "completed"}
    assert _attempt_outcome(row, metrics) == "declined"


# --- Precedence: consistency_blocked > declined > failed ---------------- #


def test_consistency_block_takes_precedence_over_declined() -> None:
    """Issue 8 precedence preserved: a consistency-blocked discard stays
    'consistency_blocked', NOT 'declined'. Operator must address the
    blocker; the discard label answers a different question."""
    row = _row(
        decision="discard",
        all_gates_passed=True,
        primary_metric=0.6,
        consistency_report_json=_report(
            passed=False, blockers=["adaptive_feature_not_enabled"],
        ),
    )
    metrics = {"status": "completed"}
    assert _attempt_outcome(row, metrics) == "consistency_blocked"


def test_crash_status_takes_precedence_over_declined() -> None:
    """A real training failure beats the decision label: crash with
    decision=discard is still 'failed', not 'declined'."""
    row = _row(decision="discard", consistency_report_json=_report(passed=True))
    metrics = {"status": "crash"}
    assert _attempt_outcome(row, metrics) == "failed"


def test_timeout_status_takes_precedence_over_declined() -> None:
    row = _row(decision="discard", consistency_report_json=_report(passed=True))
    metrics = {"status": "timeout"}
    assert _attempt_outcome(row, metrics) == "failed"


def test_error_status_takes_precedence_over_declined() -> None:
    row = _row(decision="discard", consistency_report_json=_report(passed=True))
    metrics = {"status": "error"}
    assert _attempt_outcome(row, metrics) == "failed"


def test_pruned_takes_precedence_over_declined() -> None:
    row = _row(decision="discard")
    metrics = {"status": "pruned"}
    assert _attempt_outcome(row, metrics) == "pruned"


def test_rejected_duplicate_takes_precedence_over_declined() -> None:
    row = _row(decision="discard", duplicate_reason="duplicate canonical config")
    metrics = {"status": "rejected_duplicate"}
    assert _attempt_outcome(row, metrics) == "rejected_duplicate"


# --- Regressions: unchanged behavior for non-discard paths -------------- #


def test_keep_decision_remains_completed() -> None:
    """Issue 10B does not affect the keep path."""
    row = _row(
        decision="keep",
        all_gates_passed=True,
        primary_metric=0.65,
        consistency_report_json=_report(passed=True),
    )
    metrics = {"status": "completed"}
    assert _attempt_outcome(row, metrics) == "completed"


def test_improve_decision_remains_completed() -> None:
    row = _row(decision="improve", all_gates_passed=True, primary_metric=0.5)
    metrics = {"status": "completed"}
    assert _attempt_outcome(row, metrics) == "completed"


def test_discard_with_unknown_status_still_failed() -> None:
    """Defensive: discard with non-success status remains 'failed' so the
    legacy fall-through preserves pre-10B semantics for unknown-status rows."""
    row = _row(decision="discard", consistency_report_json=_report(passed=True))
    metrics: dict = {}
    assert _attempt_outcome(row, metrics) == "failed"


def test_discard_with_empty_status_still_failed() -> None:
    row = _row(decision="discard")
    metrics = {"status": ""}
    assert _attempt_outcome(row, metrics) == "failed"
