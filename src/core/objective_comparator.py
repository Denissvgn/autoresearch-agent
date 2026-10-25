"""One objective comparator for every winner-selection path.

Before this module, each path kept its own ``primary_metric > best`` rule, so a
minimization objective (latency, loss, cost) selected the *worst* winner in the
keep/discard decision, both stores' best updates, and the displayed rankings.
Every path that answers "is this result better than that one?" now resolves a
single :class:`ObjectiveComparator` and compares through it.

Semantics (resolved once, honored everywhere):

* ``direction`` — ``minimize`` / ``maximize``, from the resolved objective
  policy (the skill's ``metric_schema.primary.direction`` vocabulary maps via
  ``objective_policy_from_skill_metric`` — the single place that knows both).
* ``epsilon`` — the *declared* tolerance: a policy's ``tie_tolerance`` wins
  when declared (> 0), else the caller's operational epsilon, else exact
  comparison (``0.0``) when nothing is declared.
* **Ties preserve the existing eligible winner.** A result beats the incumbent
  only by *more than* ``epsilon``; within ``epsilon`` the incumbent — the
  earlier, already selected result — is kept.
* **Absent/nonfinite metrics never win.** ``None``/NaN/±inf are
  ``incomparable``: they cannot beat anything and cannot become best.
* **Gate eligibility is the promotable frontier.** A row is eligible for best
  selection only with passing training gates and a present, finite metric.

Historical rows: :func:`reconcile_historical_best` re-derives a session's best
under its *known* objective and flags, never guesses, ambiguous legacy rows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Literal, Mapping, Optional, Sequence

from src.core.execution_contracts import ObjectiveDirection

Comparison = Literal["better", "tie", "worse", "incomparable"]

__all__ = [
    "Comparison",
    "ObjectiveComparator",
    "ObjectiveContextError",
    "ObjectiveDirection",
    "objective_comparator_for_manifest",
    "objective_comparator_for_skill_id",
    "rank_rows",
    "reconcile_historical_best",
    "select_best_row",
]


class ObjectiveContextError(ValueError):
    """Raised when a comparison needs objective context that is not declared."""


def _finite(value: Any) -> Optional[float]:
    """The value as a finite float, or None when absent/nonfinite/non-numeric."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


@dataclass(frozen=True)
class ObjectiveComparator:
    """The one rule for "is this result better than that one?"."""

    direction: ObjectiveDirection = "maximize"
    epsilon: float = 0.0
    metric_field: str = "primary_metric"

    def __post_init__(self) -> None:
        if self.direction not in ("minimize", "maximize"):
            raise ObjectiveContextError(
                f"unknown objective direction {self.direction!r}; "
                "expected 'minimize' or 'maximize'"
            )
        try:
            epsilon = float(self.epsilon)
        except (TypeError, ValueError) as exc:
            raise ObjectiveContextError(
                f"objective epsilon must be a number, got {self.epsilon!r}"
            ) from exc
        if not math.isfinite(epsilon) or epsilon < 0.0:
            raise ObjectiveContextError(
                f"objective epsilon must be finite and >= 0, got {self.epsilon!r}"
            )
        object.__setattr__(self, "epsilon", epsilon)

    @classmethod
    def resolve(
        cls,
        *,
        policy: Any = None,
        direction: Optional[str] = None,
        epsilon: Optional[float] = None,
        metric_field: str = "primary_metric",
    ) -> "ObjectiveComparator":
        """Resolve the one comparator for a decision path.

        Epsilon resolution (declared first, exact when absent): a policy's
        declared ``tie_tolerance`` (> 0) wins over the caller's operational
        epsilon; with neither declared the comparison is exact (``0.0``).
        """
        chosen_direction = getattr(policy, "direction", None) or direction
        if chosen_direction not in ("minimize", "maximize"):
            raise ObjectiveContextError(
                "objective context is unknown: resolve a declared "
                f"direction first (got {chosen_direction!r})"
            )
        declared = _finite(getattr(policy, "tie_tolerance", None))
        if declared is not None and declared > 0.0:
            chosen_epsilon: float = declared
        elif epsilon is not None:
            chosen_epsilon = float(epsilon)
        else:
            chosen_epsilon = 0.0
        return cls(
            direction=chosen_direction,  # type: ignore[arg-type]
            epsilon=chosen_epsilon,
            metric_field=getattr(policy, "metric_field", None) or metric_field,
        )

    def orient(self, candidate: Any, incumbent: Any) -> Optional[float]:
        """Signed gain of the candidate over the incumbent (+ = better).

        None when either side is absent or nonfinite — those pairs are
        ``incomparable``, never silently equal.
        """
        cand = _finite(candidate)
        inc = _finite(incumbent)
        if cand is None or inc is None:
            return None
        return (cand - inc) if self.direction == "maximize" else (inc - cand)

    def compare(self, candidate: Any, incumbent: Any) -> Comparison:
        """better / tie / worse / incomparable, ties within ``epsilon``."""
        if _finite(candidate) is None:
            return "incomparable"
        if _finite(incumbent) is None:
            # Any finite result beats an absent incumbent and establishes best.
            return "better"
        gain = self.orient(candidate, incumbent)
        assert gain is not None
        if gain > self.epsilon:
            return "better"
        if gain < -self.epsilon:
            return "worse"
        return "tie"

    def is_better(self, candidate: Any, incumbent: Any) -> bool:
        """Strict improvement beyond ``epsilon`` — the only way to move best."""
        return self.compare(candidate, incumbent) == "better"


def select_best_row(
    rows: Iterable[Mapping[str, Any]],
    comparator: ObjectiveComparator,
    *,
    value: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    eligible: Optional[Callable[[Mapping[str, Any]], bool]] = None,
) -> Optional[Mapping[str, Any]]:
    """The best row under ``comparator``, or None.

    Rows fold in iteration order (stable): the existing eligible winner is
    preserved unless a later row *beats* it — the same rule as the incremental
    stored-best update, so recomputation and live updates agree. Ineligible
    rows (failed gates, absent/nonfinite metrics) never win.
    """
    get_value = value or (lambda row: row.get(comparator.metric_field))
    is_eligible = eligible or (lambda row: _finite(get_value(row)) is not None)
    winner: Optional[Mapping[str, Any]] = None
    for row in rows:
        if not is_eligible(row):
            continue
        if winner is None:
            winner = row
            continue
        if comparator.is_better(get_value(row), get_value(winner)):
            winner = row
    return winner


def rank_rows(
    rows: Iterable[Mapping[str, Any]],
    comparator: ObjectiveComparator,
    *,
    value: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    eligible: Optional[Callable[[Mapping[str, Any]], bool]] = None,
) -> List[Mapping[str, Any]]:
    """Stable best-first ranking; ties keep input order, incomparable last."""
    get_value = value or (lambda row: row.get(comparator.metric_field))
    is_eligible = eligible or (lambda row: _finite(get_value(row)) is not None)
    scored = [row for row in rows if is_eligible(row)]
    rest = [row for row in rows if not is_eligible(row)]

    from functools import cmp_to_key

    def _cmp(a: Mapping[str, Any], b: Mapping[str, Any]) -> int:
        verdict = comparator.compare(get_value(a), get_value(b))
        if verdict == "better":
            return -1
        if verdict == "worse":
            return 1
        return 0

    return sorted(scored, key=cmp_to_key(_cmp)) + rest


def objective_comparator_for_manifest(
    manifest: Any,
    *,
    epsilon: Optional[float] = None,
    metric_field: str = "primary_metric",
) -> ObjectiveComparator:
    """The comparator a skill manifest declares.

    Raises :class:`ObjectiveContextError` when the manifest declares no
    objective direction — unknown objective context is rejected, not defaulted.
    """
    from src.core.execution_contracts import objective_policy_from_skill_metric

    metric_schema = getattr(manifest, "metric_schema", None)
    primary = getattr(metric_schema, "primary", None)
    direction = getattr(primary, "direction", None)
    if direction not in ("higher_is_better", "lower_is_better"):
        raise ObjectiveContextError(
            "skill manifest declares no usable metric_schema.primary.direction"
        )
    policy = objective_policy_from_skill_metric(
        metric_field=getattr(primary, "field", None) or metric_field,
        direction=direction,
    )
    return ObjectiveComparator.resolve(policy=policy, epsilon=epsilon)


def objective_comparator_for_skill_id(
    skill_id: Optional[str],
    *,
    epsilon: Optional[float] = None,
    default: Optional[ObjectiveComparator] = None,
) -> ObjectiveComparator:
    """The comparator for a session's skill id (legacy ``model_type`` alias ok).

    Falls back to ``default`` (never a guess) when the skill cannot be
    resolved; pass ``default=None`` to reject instead.
    """
    if not skill_id:
        if default is not None:
            return default
        raise ObjectiveContextError("no skill id to resolve an objective from")
    try:
        from src.core.skill_registry import default_registry

        skill = default_registry.get(skill_id)
    except Exception:
        skill = None
    if skill is None:
        # A legacy ``model_type`` session name IS objective provenance — map it
        # through the alias bridge before treating the context as unknown.
        try:
            from src.core.legacy_alias import model_type_to_skill_id

            skill = default_registry.get(model_type_to_skill_id(skill_id))
        except Exception:
            skill = None
    manifest = getattr(skill, "manifest", None)
    if manifest is None:
        if default is not None:
            return default
        raise ObjectiveContextError(
            f"skill {skill_id!r} does not resolve to a manifest with an objective"
        )
    return objective_comparator_for_manifest(manifest, epsilon=epsilon)


def reconcile_historical_best(
    *,
    session: Mapping[str, Any],
    iterations: Sequence[Mapping[str, Any]],
    comparator: Optional[ObjectiveComparator] = None,
) -> Mapping[str, Any]:
    """Reconcile a session's stored best rows under their known objective.

    Historical rows are migrated only when the objective is known (explicit
    comparator or a resolvable skill manifest); ambiguous legacy objective
    data is **flagged, never guessed**. The result is advisory: applying the
    migration is a separate, explicit act.
    """
    flags: List[str] = []
    source: Optional[str] = None
    if comparator is not None:
        source = "explicit"
    else:
        skill_id = session.get("skill_id") or session.get("model_type")
        try:
            comparator = objective_comparator_for_skill_id(skill_id, default=None)
            source = "skill_manifest"
        except ObjectiveContextError:
            comparator = None
            flags.append("objective_direction_unknown")
    stored = {
        "best_iteration": session.get("best_iteration"),
        "best_metric": session.get("best_metric"),
    }
    if comparator is None:
        return {
            "research_id": session.get("id"),
            "status": "ambiguous_objective",
            "objective": {"direction": None, "epsilon": None, "source": None},
            "stored": stored,
            "recomputed": None,
            "flags": flags,
        }

    def _promotable(row: Mapping[str, Any]) -> bool:
        gates = row.get("all_gates_passed")
        return gates in (True, 1) and _finite(row.get("primary_metric")) is not None

    ordered = sorted(iterations, key=lambda row: row.get("iteration") or 0)
    winner = select_best_row(ordered, comparator, eligible=_promotable)
    objective = {
        "direction": comparator.direction,
        "epsilon": comparator.epsilon,
        "source": source,
    }
    if winner is None:
        return {
            "research_id": session.get("id"),
            "status": "no_eligible",
            "objective": objective,
            "stored": stored,
            "recomputed": None,
            "flags": flags + ["no_gates_passing_metric_rows"],
        }

    recomputed = {
        "best_iteration": winner.get("iteration"),
        "best_metric": winner.get("primary_metric"),
    }
    consistent = (
        stored["best_iteration"] == recomputed["best_iteration"]
        and comparator.compare(stored["best_metric"], recomputed["best_metric"])
        == "tie"
    )
    if not consistent:
        flags.append("stored_best_differs_from_recomputed")
    return {
        "research_id": session.get("id"),
        "status": "consistent" if consistent else "reconciled",
        "objective": objective,
        "stored": stored,
        "recomputed": recomputed,
        "flags": flags,
    }
