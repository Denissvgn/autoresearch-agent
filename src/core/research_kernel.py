"""The research kernel: lifecycle decisions without harness types.

The kernel owns the research lifecycle decisions — attempt scheduling,
objective/phase adjudication, budgets, verified evidence, and promotion
eligibility — behind stable value contracts, so different agent harnesses
and research domains can share one loop.

Boundary: provider conversation, tool serialization, context compaction,
and model retry behavior live in the built-in driver (``orchestrator`` /
``llm_provider``), never here. This module and its transitive imports must
not depend on provider SDKs or message-block types; ``tests/test_kernel_
boundary.py`` enforces the import boundary.
"""
from __future__ import annotations

import time as _time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, Sequence

from src.core.significance import qualification_status

# ---------------------------------------------------------------------------
# Stable value contracts — plain values, no harness or provider types.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AttemptPlan:
    """The kernel's scheduling decision for the next attempt slot."""

    action: str  # "run" | "retry_after" | "stop"
    attempt_index: int
    wait_seconds: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class ObjectiveDecision:
    """The adjudicated verdict and phase decision for one attempt."""

    verdict: str
    plan: str  # "continue" | "stop"
    phase_id: Optional[str] = None
    phase_action: str = "stay"  # "advance" | "stay" | "block"
    reason: str = ""


@dataclass(frozen=True)
class BudgetDecision:
    """Which declared budgets bound the run, and whether one is exhausted."""

    within_budget: bool
    exhausted: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceDecision:
    """The verification state of one evaluator result."""

    status: str  # "verified" | "unverified" | "rejected"
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PromotionDecision:
    """Promotion eligibility for the run's best candidate."""

    eligible: bool
    status: str
    reasons: tuple[str, ...] = ()
    best_iteration: Optional[int] = None


@dataclass(frozen=True)
class AttemptResult:
    """What a driver reports back for one attempt — stable and harness-free."""

    iteration: int
    outcome: str  # the attempt-outcome vocabulary (see plan_attempt)
    metric: Optional[float] = None
    metrics: Mapping[str, Any] = field(default_factory=dict)
    verdict: str = ""
    gate_passed: bool = False
    duplicate_of: Optional[int] = None
    phase_id: Optional[str] = None
    phase_advanced: Optional[bool] = None


@dataclass(frozen=True)
class ResearchOutcome:
    """The completed lifecycle: attempts run and the final decisions."""

    completed: bool
    attempts: tuple[AttemptResult, ...] = ()
    plan: Optional[AttemptPlan] = None
    objective: Optional[ObjectiveDecision] = None
    budget: Optional[BudgetDecision] = None
    promotion: Optional[PromotionDecision] = None


# ---------------------------------------------------------------------------
# Kernel operations — one per extracted responsibility.
# ---------------------------------------------------------------------------


def plan_attempt(
    *,
    attempt_index: int,
    outcome: str,
    max_attempts: Optional[int] = None,
    retry_state: Optional[str] = None,
    next_attempt_after: Optional[float] = None,
    now: Optional[float] = None,
) -> AttemptPlan:
    """Attempt scheduling: what the next attempt slot should do.

    ``outcome`` is the attempt-outcome vocabulary (``completed``,
    ``declined``, ``pruned``, ``rejected_duplicate``, ``consistency_blocked``,
    ``failed``). Transient failures may retry within the attempt budget;
    a consistency block is never retried as transient — the blocker is an
    operator concern, not a scheduling one.
    """
    if max_attempts is not None and attempt_index >= max_attempts:
        return AttemptPlan(
            action="stop",
            attempt_index=attempt_index,
            reason="attempt budget exhausted",
        )
    if outcome == "failed":
        if retry_state in {"exhausted", "abandoned"}:
            return AttemptPlan(
                action="stop",
                attempt_index=attempt_index,
                reason=f"retry {retry_state}",
            )
        wait = 0.0
        if next_attempt_after is not None:
            current = _time.time() if now is None else now
            wait = max(0.0, float(next_attempt_after) - current)
        return AttemptPlan(
            action="retry_after",
            attempt_index=attempt_index + 1,
            wait_seconds=wait,
            reason="transient failure",
        )
    if outcome == "consistency_blocked":
        return AttemptPlan(
            action="stop",
            attempt_index=attempt_index,
            reason="consistency blocker requires resolution, not retry",
        )
    return AttemptPlan(
        action="run",
        attempt_index=attempt_index + 1,
        reason=f"outcome {outcome} continues the schedule",
    )


def decide_objective(
    *,
    verdict: str,
    metric: Optional[float] = None,
    best_metric: Optional[float] = None,
    direction: str = "maximize",
    phase_id: Optional[str] = None,
    phase_advanced: Optional[bool] = None,
    stop_requested: bool = False,
) -> ObjectiveDecision:
    """Objective/phase adjudication for one attempt.

    The verdict decides whether the schedule continues; the objective
    direction governs whether an attempt improves on the best so far; the
    phase decision records whether the run's phase advances.
    """
    plan = "stop" if stop_requested else "continue"
    reason = "operator stop" if stop_requested else f"verdict {verdict}"
    phase_action = "stay"
    if phase_id is not None and phase_advanced is True:
        phase_action = "advance"
    elif phase_id is not None and phase_advanced is False:
        phase_action = "block"
    return ObjectiveDecision(
        verdict=verdict,
        plan=plan,
        phase_id=phase_id,
        phase_action=phase_action,
        reason=reason,
    )


def improves_on_best(
    metric: Optional[float],
    best_metric: Optional[float],
    direction: str = "maximize",
) -> bool:
    """Direction-correct winner selection (minimize objectives invert)."""
    if metric is None:
        return False
    if best_metric is None:
        return True
    if direction.startswith("minimize"):
        return metric < best_metric
    return metric > best_metric


def decide_budget(
    *,
    session: Mapping[str, Any],
    iterations: Sequence[Mapping[str, Any]],
    cost_usd: Optional[float] = None,
    elapsed_s: Optional[float] = None,
) -> BudgetDecision:
    """Budget adjudication over the declared caps.

    The iteration cap is authoritative; monetary and wall-clock caps are
    reported with honest labels (an advisory monetary limit never claims
    to be a hard ceiling).
    """
    exhausted: list[str] = []
    labels: list[str] = []

    max_iterations = _first_number(session.get("max_iterations"))
    if max_iterations is not None and max_iterations > 0:
        labels.append(f"max_iterations={int(max_iterations)}")
        if len(iterations) >= int(max_iterations):
            exhausted.append("iterations")

    max_budget = _first_number(session.get("max_budget_usd"))
    if max_budget is not None:
        labels.append(f"max_budget_usd={max_budget}")
        if cost_usd is not None and cost_usd >= max_budget:
            exhausted.append("budget")

    timeout_s = _first_number(session.get("timeout_s"))
    if timeout_s is not None and timeout_s > 0:
        labels.append(f"timeout_s={timeout_s}")
        if elapsed_s is not None and elapsed_s >= timeout_s:
            exhausted.append("time")

    return BudgetDecision(
        within_budget=not exhausted,
        exhausted=tuple(exhausted),
        labels=tuple(labels),
    )


def verify_evidence(
    *,
    receipt: Mapping[str, Any],
    payload: Mapping[str, Any],
    key: Optional[str],
    attempt_id: Optional[str] = None,
) -> EvidenceDecision:
    """Verified evidence: a result's authority is proven, never asserted."""
    from src.core.result_authority import verify_result_receipt

    problems = verify_result_receipt(
        receipt, payload=payload, attempt_id=attempt_id, key=key
    )
    return EvidenceDecision(
        status="verified" if not problems else "rejected",
        reasons=tuple(str(problem) for problem in problems),
    )


def decide_promotion(
    *,
    candidate: Sequence[float],
    reference: Optional[Sequence[float]] = None,
    config: Any = None,
    verdict: Optional[str] = None,
    holdout_evidence: Optional[bool] = None,
    promotion_blocked: bool = False,
    best_iteration: Optional[int] = None,
) -> PromotionDecision:
    """Promotion eligibility: qualification first, then blockers."""
    if promotion_blocked:
        return PromotionDecision(
            eligible=False,
            status="blocked",
            reasons=("promotion is blocked",),
            best_iteration=best_iteration,
        )
    status = qualification_status(
        candidate=candidate,
        reference=reference,
        config=config,
        verdict=verdict,
        holdout_evidence=holdout_evidence,
    )
    eligible = bool(status.get("qualifies")) and status.get("status") == (
        "qualified"
    )
    reasons: tuple[str, ...] = ()
    if not eligible:
        reasons = (str(status.get("status")),)
    return PromotionDecision(
        eligible=eligible,
        status=str(status.get("status")),
        reasons=reasons,
        best_iteration=best_iteration,
    )


def _first_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# The driver boundary: harness work enters the kernel only through here.
# ---------------------------------------------------------------------------


class KernelDriver(Protocol):
    """What a harness must provide to run a research lifecycle.

    Provider conversation, tool serialization, context compaction, and
    model retry behavior stay behind this boundary; the kernel sees only
    the stable ``AttemptResult`` value contract.
    """

    def run_attempt(
        self,
        plan: AttemptPlan,
        *,
        attempt_index: int,
        context: Mapping[str, Any],
    ) -> AttemptResult: ...


def run_kernel_lifecycle(
    driver: KernelDriver,
    *,
    session: Mapping[str, Any],
    max_attempts: int = 8,
    candidate_samples: Optional[Sequence[float]] = None,
    reference_samples: Optional[Sequence[float]] = None,
    promotion_config: Any = None,
    context: Optional[Mapping[str, Any]] = None,
) -> ResearchOutcome:
    """Complete one research lifecycle through the kernel's decisions.

    The driver performs each attempt; the kernel schedules attempts,
    adjudicates the objective, bounds the budget, and decides promotion
    eligibility. Deterministic drivers make the whole lifecycle
    reproducible without any provider dependency.
    """
    attempts: list[AttemptResult] = []
    plan = plan_attempt(attempt_index=0, outcome="start")
    objective: Optional[ObjectiveDecision] = None
    best_metric: Optional[float] = None

    while plan.action in {"run", "retry_after"} and plan.attempt_index < (
        max_attempts
    ):
        result = driver.run_attempt(
            plan,
            attempt_index=plan.attempt_index,
            context=context or {},
        )
        attempts.append(result)
        if result.metric is not None:
            if improves_on_best(result.metric, best_metric, "maximize"):
                best_metric = result.metric
        objective = decide_objective(
            verdict=result.verdict or result.outcome,
            phase_id=result.phase_id,
            phase_advanced=result.phase_advanced,
        )
        if objective.plan == "stop":
            plan = AttemptPlan(
                action="stop",
                attempt_index=plan.attempt_index,
                reason=objective.reason,
            )
            break
        budget = decide_budget(
            session=session,
            iterations=[{"iteration": a.iteration} for a in attempts],
        )
        if not budget.within_budget:
            plan = AttemptPlan(
                action="stop",
                attempt_index=plan.attempt_index,
                reason=f"budget exhausted: {','.join(budget.exhausted)}",
            )
            break
        plan = plan_attempt(
            attempt_index=plan.attempt_index,
            outcome=result.outcome,
            max_attempts=max_attempts,
        )

    budget = decide_budget(
        session=session,
        iterations=[{"iteration": a.iteration} for a in attempts],
    )
    promotion = decide_promotion(
        candidate=tuple(candidate_samples or ()),
        reference=tuple(reference_samples) if reference_samples else None,
        config=promotion_config,
    )
    return ResearchOutcome(
        completed=True,
        attempts=tuple(attempts),
        plan=plan,
        objective=objective,
        budget=budget,
        promotion=promotion,
    )
