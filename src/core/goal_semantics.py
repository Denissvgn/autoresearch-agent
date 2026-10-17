"""Declarative optimize/satisfice goal semantics (no expressions, no plugins).

``metric_schema.goal`` selects the decision and outcome semantics:

* ``optimize`` — single-winner optimization: decisions run through the one
  objective comparator (keep/improve/discard against the incumbent).
* ``satisfice`` — meet a declared threshold condition, **no single winner**:
  the declared boolean ``satisfice_threshold_field`` is the threshold
  evidence. A satisfied observation is accepted regardless of ranking; an
  unsatisfied one is not a solution; a condition that was never observed is
  **inconclusive** and can never be silently reported as success.

Terminal outcomes keep exhaustion and inconclusive distinct from success:
``goal_satisficed`` is produced only when the declared condition was observed
true on a verified observation. Unknown goal context is rejected, never
silently treated as a different goal.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

GOAL_OPTIMIZE = "optimize"
GOAL_SATISFICE = "satisfice"

#: Terminal outcome tokens shared with the terminal-reason vocabulary.
GOAL_SATISFICED = "goal_satisficed"
GOAL_INCONCLUSIVE = "goal_inconclusive"
GOAL_THRESHOLD_UNMET = "goal_threshold_unmet"

__all__ = [
    "GOAL_INCONCLUSIVE",
    "GOAL_OPTIMIZE",
    "GOAL_SATISFICED",
    "GOAL_SATISFICE",
    "GOAL_THRESHOLD_UNMET",
    "goal_decision",
    "goal_outcome",
    "threshold_evidence",
]


def threshold_evidence(
    metrics: Any, threshold_field: Optional[str]
) -> Mapping[str, Any]:
    """The declared threshold evidence from one verified observation.

    The condition is satisfied only by an explicit boolean ``True`` on the
    declared field. An absent field is *not observed* (inconclusive evidence);
    any other value is observed but unsatisfied.
    """
    base = {
        "field": threshold_field,
        "observed": False,
        "satisfied": False,
        "value": None,
    }
    if not threshold_field or not isinstance(metrics, Mapping):
        return base
    if threshold_field not in metrics:
        return base
    value = metrics[threshold_field]
    return {
        "field": threshold_field,
        "observed": True,
        "satisfied": value is True,
        "value": value,
    }


def goal_decision(
    *,
    goal: str,
    metrics: Any = None,
    threshold_field: Optional[str] = None,
    gates_passed: bool = False,
    comparator: Any = None,
    primary_metric: Optional[float] = None,
    incumbent: Optional[float] = None,
) -> str:
    """Explicit goal-aware decision for one verified observation.

    optimize — the comparator's winner selection: ``keep`` (gates passed and
    improved), ``improve`` (improved, gates failed), ``discard``.
    satisfice — the declared condition decides: satisfied is accepted (``keep``
    with gates, ``improve`` without); anything else is not a solution.
    """
    if goal == GOAL_SATISFICE:
        evidence = threshold_evidence(metrics, threshold_field)
        if evidence["satisfied"]:
            return "keep" if gates_passed else "improve"
        return "discard"
    if goal != GOAL_OPTIMIZE:
        raise ValueError(f"unknown goal {goal!r}; expected 'optimize' or 'satisfice'")
    if primary_metric is None:
        return "discard"
    if comparator is None:
        raise ValueError("optimize decisions require an objective comparator")
    improved = (incumbent is None) or comparator.is_better(primary_metric, incumbent)
    if gates_passed and improved:
        return "keep"
    if improved:
        return "improve"
    return "discard"


def goal_outcome(
    *,
    goal: str,
    observations: Sequence[Any],
    threshold_field: Optional[str] = None,
) -> Mapping[str, Any]:
    """Terminal outcome summary over verified observations.

    ``goal_satisficed`` — the declared condition was observed true.
    ``goal_inconclusive`` — the declared condition was never observed at all.
    ``goal_threshold_unmet`` — observed but never true.
    "optimize" — no satisfice outcome applies.
    """
    if goal != GOAL_SATISFICE:
        return {
            "status": "optimize",
            "goal": goal,
            "satisfied": None,
            "observed": 0,
            "evidence": [],
        }
    evidence = [threshold_evidence(m, threshold_field) for m in observations]
    observed = [e for e in evidence if e["observed"]]
    satisfied = [e for e in evidence if e["satisfied"]]
    if satisfied:
        status = GOAL_SATISFICED
    elif not observed:
        status = GOAL_INCONCLUSIVE
    else:
        status = GOAL_THRESHOLD_UNMET
    return {
        "status": status,
        "goal": goal,
        "satisfied": bool(satisfied),
        "observed": len(observed),
        "evidence": (satisfied or observed)[:1],
    }
