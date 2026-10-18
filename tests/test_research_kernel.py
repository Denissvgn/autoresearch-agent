"""Kernel boundary and characterization tests.

The research kernel must complete a research lifecycle with a deterministic
driver and must never depend on provider SDKs or message-block types. The
import-boundary test enforces that harness types cannot leak back into the
kernel, and the parity tests pin the supported decision semantics.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core import research_kernel as kernel
from src.core.research_kernel import (
    AttemptPlan,
    AttemptResult,
    decide_budget,
    decide_objective,
    decide_promotion,
    improves_on_best,
    plan_attempt,
    run_kernel_lifecycle,
    verify_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Harness and provider types that must never reach the kernel closure:
# provider conversation and retry (llm_provider/anthropic), tool
# serialization (execution_request), message-block parsing (output_parser),
# context compaction (iteration_context), and the built-in loop itself.
DENIED_MODULES = frozenset(
    {
        "anthropic",
        "src.core.llm_provider",
        "src.core.execution_request",
        "src.core.output_parser",
        "src.core.iteration_context",
        "src.core.orchestrator",
        "src.core.skill_runtime",
        "src.core.manifest_skill_runtime",
    }
)


def _imported_modules(path: Path, *, include_local: bool) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()

    def record(nodes) -> None:
        for node in nodes:
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)

    # module-level edges (including the typing-only block) define what
    # importing this module drags in
    for node in tree.body:
        record([node])
        if isinstance(node, ast.If):
            record(ast.walk(node))
    if include_local:
        record(ast.walk(tree))
    return {module for module in found if module.startswith("src.")}


def _transitive_closure(root_module: str) -> set[str]:
    seen: set[str] = set()
    frontier = [root_module]
    while frontier:
        module = frontier.pop()
        if module in seen:
            continue
        seen.add(module)
        path = REPO_ROOT / Path(*module.split(".")).with_suffix(".py")
        if not path.exists():
            continue
        # the kernel's own modules count every import; deeper services count
        # only their import-time edges
        include_local = module in {
            "src.core.research_kernel",
            "src.core.skill_host_services",
        }
        for imported in _imported_modules(path, include_local=include_local):
            frontier.append(imported)
    return seen


def test_kernel_import_closure_excludes_harness_types():
    for root in ("src.core.research_kernel", "src.core.skill_host_services"):
        closure = _transitive_closure(root)
        leaked = sorted(closure & DENIED_MODULES)
        assert not leaked, f"{root} reaches harness types: {leaked}"


def test_kernel_module_names_no_provider_symbols():
    source = (
        REPO_ROOT / "src" / "core" / "research_kernel.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    assert not names & {"Anthropic", "Message", "ContentBlock", "Usage"}


# ---------------------------------------------------------------------------
# Characterization: the kernel decisions match the existing semantics.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("max_iterations", "count", "expected"),
    [(3, 2, False), (3, 3, True), (0, 5, False), (None, 5, False)],
)
def test_budget_parity_with_iteration_budget(max_iterations, count, expected):
    from src.core.research_state import _iteration_budget_reached

    session = {"max_iterations": max_iterations}
    iterations = [{"iteration": i} for i in range(count)]
    decision = decide_budget(session=session, iterations=iterations)
    assert decision.within_budget is not expected
    assert _iteration_budget_reached(dict(session), list(iterations)) is (
        expected
    )


def test_budget_labels_report_declared_caps_honestly():
    decision = decide_budget(
        session={"max_iterations": 2, "max_budget_usd": 7.5},
        iterations=[{"iteration": 1}, {"iteration": 2}],
    )
    assert decision.within_budget is False
    assert decision.exhausted == ("iterations",)
    assert "max_budget_usd=7.5" in decision.labels


@pytest.mark.parametrize(
    ("metric", "best", "direction", "expected"),
    [
        (1.0, 0.5, "maximize", True),
        (0.4, 0.5, "maximize", False),
        (0.4, 0.5, "minimize", True),
        (1.0, 0.5, "minimize_drawdown", False),
        (1.0, None, "minimize", True),
        (None, 0.5, "maximize", False),
    ],
)
def test_winner_direction_parity(metric, best, direction, expected):
    assert improves_on_best(metric, best, direction) is expected


def test_plan_attempt_scheduling_semantics():
    # transient failure retries with its scheduled wait
    plan = plan_attempt(
        attempt_index=1,
        outcome="failed",
        next_attempt_after=200.0,
        now=100.0,
    )
    assert plan.action == "retry_after"
    assert plan.attempt_index == 2
    assert plan.wait_seconds == 100.0
    # exhausted retries stop; a consistency block is never retried as such
    stopped = plan_attempt(
        attempt_index=1, outcome="failed", retry_state="exhausted"
    )
    assert stopped.action == "stop"
    blocked = plan_attempt(attempt_index=1, outcome="consistency_blocked")
    assert blocked.action == "stop"
    # successful attempts continue the schedule within the budget
    assert plan_attempt(attempt_index=1, outcome="completed").action == "run"
    budgeted = plan_attempt(
        attempt_index=3, outcome="completed", max_attempts=3
    )
    assert budgeted.action == "stop"


def test_evidence_parity_with_result_receipt():
    from src.core.result_authority import issue_result_receipt

    payload = {"research_id": "res_k", "iteration": 1, "result": {"x": 1}}
    receipt = issue_result_receipt(
        payload=payload,
        attempt_id="res_k:1",
        candidate_digest="a" * 64,
        evaluator_digest="b" * 64,
        dataset_digests=["c" * 64],
        ownership_epoch=1,
        sequence=1,
        key="k",
    )
    verified = verify_evidence(receipt=receipt, payload=payload, key="k")
    assert verified.status == "verified"
    tampered = dict(payload)
    tampered["result"] = {"x": 2}
    rejected = verify_evidence(receipt=receipt, payload=tampered, key="k")
    assert rejected.status == "rejected"
    assert rejected.reasons


def test_promotion_parity_with_qualification_status():
    class Config:
        min_samples = 2
        planned_repeats = 3
        holdout_required = False

    qualified = decide_promotion(
        candidate=[0.1, 0.2], config=Config(), verdict="significant"
    )
    assert qualified.eligible is True
    assert qualified.status == "qualified"
    thin = decide_promotion(candidate=[0.1], config=Config())
    assert thin.eligible is False
    assert thin.status == "insufficient_samples"
    blocked = decide_promotion(
        candidate=[0.1, 0.2], config=Config(), promotion_blocked=True
    )
    assert blocked.eligible is False
    assert blocked.status == "blocked"


# ---------------------------------------------------------------------------
# The lifecycle completes with a deterministic driver.
# ---------------------------------------------------------------------------


class DeterministicDriver:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    def run_attempt(self, plan, *, attempt_index, context):
        self.calls += 1
        outcome, metric = self._outcomes.pop(0)
        return AttemptResult(
            iteration=attempt_index, outcome=outcome, metric=metric
        )


def test_kernel_completes_lifecycle_with_deterministic_driver():
    driver = DeterministicDriver(
        [("completed", 0.1), ("completed", 0.3), ("completed", 0.2)]
    )
    outcome = run_kernel_lifecycle(
        driver,
        session={"max_iterations": 3},
        max_attempts=8,
        candidate_samples=[0.1, 0.3, 0.2],
    )
    assert outcome.completed is True
    assert [a.outcome for a in outcome.attempts] == ["completed"] * 3
    assert outcome.budget is not None
    assert outcome.budget.within_budget is False
    assert outcome.budget.exhausted == ("iterations",)
    assert outcome.plan is not None and outcome.plan.action == "stop"
    assert outcome.promotion is not None


def test_kernel_lifecycle_retries_then_stops_on_consistency_block():
    driver = DeterministicDriver(
        [("failed", None), ("consistency_blocked", None)]
    )
    outcome = run_kernel_lifecycle(
        driver, session={"max_iterations": 8}, max_attempts=8
    )
    assert outcome.completed is True
    assert [a.outcome for a in outcome.attempts] == [
        "failed",
        "consistency_blocked",
    ]
    assert outcome.plan is not None
    assert outcome.plan.action == "stop"
    assert "consistency" in outcome.plan.reason


def test_skill_runtime_host_seam_is_protocol_shaped():
    """The skill runtime reaches its context only through SkillHostServices."""
    from src.core.skill_runtime import ManifestSkillRuntime

    host = SimpleNamespace(
        load_claude_md=lambda: "host instructions",
        load_research_resume=lambda config: "resume",
        build_phase_contract_block=lambda config: "contract",
        research_resume_path=lambda config: "/tmp/resume.md",
    )
    manifest = SimpleNamespace(
        id="prompt-engineering",
        llm=SimpleNamespace(system_prompt="SKILL.md"),
    )
    runtime = ManifestSkillRuntime(manifest, host)
    prompt = runtime.system_prompt()
    assert "host instructions" in prompt
    assert "---" in prompt