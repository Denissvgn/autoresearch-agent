"""Multiobjective (Pareto) result and promotion semantics.

The declarative contract's scalar objective (one primary metric and one
direction) cannot express a genuine tradeoff: combining metrics into a
scalar proxy destroys the requirement. This module implements the
multiobjective extension: dominance over declared metrics with their own
directions, non-dominated frontiers, and promotion semantics that select
a SET — never a forced scalar winner. Dispatch keys on the declared
objective kind only; nothing here branches on a domain or skill id.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

HIGHER_IS_BETTER = "higher_is_better"
LOWER_IS_BETTER = "lower_is_better"


class MultiObjectiveError(ValueError):
    """Base error for multiobjective semantics (explicit, never silent)."""


class ScalarProxyRejected(MultiObjectiveError):
    """A scalar winner cannot stand in for a multiobjective requirement."""


@dataclass(frozen=True)
class ObjectiveMetric:
    """One declared objective metric: field name + direction."""

    field: str
    direction: str

    def __post_init__(self) -> None:
        if self.direction not in (HIGHER_IS_BETTER, LOWER_IS_BETTER):
            raise MultiObjectiveError(
                f"unknown objective direction {self.direction!r}"
            )


@dataclass(frozen=True)
class Candidate:
    """One measured candidate: identity + per-metric values."""

    candidate_id: str
    values: Mapping[str, Optional[float]]


def _finite(value: Optional[float]) -> bool:
    return value is not None and math.isfinite(value)


def _better(metric: ObjectiveMetric, a: float, b: float) -> bool:
    return a > b if metric.direction == HIGHER_IS_BETTER else a < b


def _no_worse(metric: ObjectiveMetric, a: float, b: float) -> bool:
    return a >= b if metric.direction == HIGHER_IS_BETTER else a <= b


def dominates(
    a: Candidate,
    b: Candidate,
    objectives: Sequence[ObjectiveMetric],
) -> bool:
    """True when ``a`` Pareto-dominates ``b`` on every declared metric."""
    strictly_better = False
    for metric in objectives:
        va = a.values.get(metric.field)
        vb = b.values.get(metric.field)
        if not (_finite(va) and _finite(vb)):
            return False
        if not _no_worse(metric, va, vb):  # type: ignore[arg-type]
            return False
        if _better(metric, va, vb):  # type: ignore[arg-type]
            strictly_better = True
    return strictly_better


def non_dominated(
    candidates: Sequence[Candidate],
    objectives: Sequence[ObjectiveMetric],
) -> list[Candidate]:
    """The Pareto frontier: candidates dominated by no other candidate.

    Candidates missing a declared metric value are excluded (explicitly:
    an unmeasured candidate cannot claim frontier membership).
    """
    required = {m.field for m in objectives}

    def complete(c: Candidate) -> bool:
        return all(_finite(c.values.get(f)) for f in required)

    eligible = [c for c in candidates if complete(c)]
    return [
        c
        for c in eligible
        if not any(
            dominates(other, c, objectives)
            for other in eligible
            if other is not c
        )
    ]


def promotion_frontier(
    candidates: Sequence[Candidate],
    objectives: Sequence[ObjectiveMetric],
) -> dict[str, Any]:
    """Promotion semantics for a multiobjective requirement.

    Returns the non-dominated SET as the promotion candidate. There is no
    single winner: selecting one would be a scalar proxy for a
    multiobjective requirement and is explicitly rejected.
    """
    if not objectives or len(objectives) < 2:
        raise MultiObjectiveError(
            "promotion_frontier requires at least two declared objectives"
        )
    frontier = non_dominated(candidates, objectives)
    return {
        "promotion_set": [c.candidate_id for c in frontier],
        "frontier_size": len(frontier),
        "evaluated": len(candidates),
        "objectives": [
            {"field": m.field, "direction": m.direction} for m in objectives
        ],
        "single_winner": None,
        "note": (
            "multiobjective promotion selects the non-dominated set; a "
            "single-winner selection would be a scalar proxy and is refused"
        ),
    }


def scalar_winner_rejected(objectives: Sequence[ObjectiveMetric]) -> None:
    """Explicit refusal: no scalar winner is derived from a frontier."""
    raise ScalarProxyRejected(
        "a scalar winner cannot represent a multiobjective requirement; "
        "use promotion_frontier's non-dominated set"
    )


def objective_metrics_from_spec(spec: Any) -> list[ObjectiveMetric]:
    """Build metrics from a declared ``ObjectiveSpec`` (generic dispatch)."""
    kind = getattr(spec, "kind", "scalar")
    if kind != "multiobjective":
        raise MultiObjectiveError(
            f"objective kind {kind!r} is not multiobjective; use the scalar "
            "comparator for scalar declarations"
        )
    return [
        ObjectiveMetric(field=m.field, direction=m.direction)
        for m in spec.metrics
    ]
