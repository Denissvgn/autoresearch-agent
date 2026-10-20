"""Tests for explicit goal and phase semantics.

Contract: optimize and satisfice goals decide explicitly (no expressions, no
plugins); a satisfice threshold crossing is accepted with its evidence and
produces a distinct terminal success, while exhaustion and a never-observed
condition stay distinct from success. Declarative phase rules evaluate against
verified in-phase observations and declared min/max observation requirements;
model prose and unrelated or stale evidence never advance a phase. Plugin
phase/resolver modes are rejected explicitly, never silently substituted.
"""

from __future__ import annotations

import json
import sys
import types
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List, Optional, cast
from unittest.mock import MagicMock

import pytest

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    _stub = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = cast(ModuleType, _stub)
from src.core.goal_semantics import (
    GOAL_INCONCLUSIVE,
    GOAL_SATISFICED,
    GOAL_THRESHOLD_UNMET,
    goal_decision,
    goal_outcome,
    threshold_evidence,
)
from src.core.research_phase_plan import _completed_phase_ids
from src.core.skill_runtime import (
    ManifestSkillRuntime,
    UnsupportedPhaseAdvancementError,
)


def _metrics(threshold: Optional[bool] = None, **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(extra)
    if threshold is not None:
        out["met_target"] = threshold
    return out


def _row(
    iteration: int,
    metrics: Dict[str, Any],
    *,
    phase: str = "validation",
    decision: str = "keep",
    duplicate_reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "iteration": iteration,
        "search_phase": phase,
        "decision": decision,
        "duplicate_reason": duplicate_reason,
        "primary_metric": metrics.get("primary_metric"),
        "metrics_json": json.dumps(metrics),
    }


def _goal_skill(
    *,
    goal: str = "satisfice",
    threshold_field: str = "met_target",
    phase_plan: Optional[List[Dict[str, Any]]] = None,
    advancement_mode: str = "declarative",
    phase_override_mode: Optional[str] = None,
) -> SimpleNamespace:
    metric_schema = SimpleNamespace(
        primary=SimpleNamespace(direction="higher_is_better", field="primary_metric"),
        significance=None,
        goal=goal,
        satisfice_threshold_field=threshold_field,
    )
    phases = []
    for spec in phase_plan or []:
        phases.append(SimpleNamespace(
            id=spec["id"],
            label=spec.get("label"),
            min_iterations=spec.get("min_iterations", 1),
            max_iterations=spec.get("max_iterations", 4),
            evidence_keys=tuple(spec.get("evidence_keys") or ()),
            next_action=spec.get("next_action"),
            stagnation_exempt=False,
            advancement=(
                SimpleNamespace(mode=phase_override_mode, plugin="phases.py")
                if phase_override_mode else None
            ),
        ))
    manifest = SimpleNamespace(
        metric_schema=metric_schema,
        phase_plan=phases,
        phase_advancement=SimpleNamespace(
            mode=advancement_mode,
            plugin="phases.py" if advancement_mode == "plugin" else None,
        ),
    )
    return SimpleNamespace(manifest=manifest)


# ---------------------------------------------------------------------------
# Optimize/satisfice decisions and threshold evidence
# ---------------------------------------------------------------------------


def test_threshold_evidence_is_explicit() -> None:
    assert threshold_evidence({"met_target": True}, "met_target")["satisfied"] is True
    assert threshold_evidence({"met_target": False}, "met_target")["observed"] is True
    assert threshold_evidence({}, "met_target")["observed"] is False  # never observed
    assert threshold_evidence({"met_target": "yes"}, "met_target")["satisfied"] is False
    assert threshold_evidence({}, None)["observed"] is False


def test_satisfice_decisions_skip_winner_comparison() -> None:
    # A satisfied observation is accepted regardless of ranking; an unsatisfied
    # one is not a solution even with a better metric.
    assert goal_decision(
        goal="satisfice", metrics=_metrics(True), threshold_field="met_target",
        gates_passed=True, primary_metric=0.1,
    ) == "keep"
    assert goal_decision(
        goal="satisfice", metrics=_metrics(True), threshold_field="met_target",
        gates_passed=False, primary_metric=0.1,
    ) == "improve"
    assert goal_decision(
        goal="satisfice", metrics=_metrics(False), threshold_field="met_target",
        gates_passed=True, primary_metric=99.0,
    ) == "discard"
    assert goal_decision(
        goal="satisfice", metrics={}, threshold_field="met_target",
        gates_passed=True, primary_metric=99.0,
    ) == "discard"


def test_optimize_decisions_stay_comparator_based() -> None:
    from src.core.objective_comparator import ObjectiveComparator

    comparator = ObjectiveComparator(direction="maximize")
    assert goal_decision(
        goal="optimize", comparator=comparator, primary_metric=120.0,
        incumbent=100.0, gates_passed=True,
    ) == "keep"
    assert goal_decision(
        goal="optimize", comparator=comparator, primary_metric=80.0,
        incumbent=100.0, gates_passed=True,
    ) == "discard"
    with pytest.raises(ValueError):
        goal_decision(goal="nonsense")


def test_goal_outcomes_keep_success_exhaustion_inconclusive_distinct() -> None:
    satisfied = goal_outcome(
        goal="satisfice", observations=[_metrics(False), _metrics(True)],
        threshold_field="met_target",
    )
    assert satisfied["status"] == GOAL_SATISFICED
    unmet = goal_outcome(
        goal="satisfice", observations=[_metrics(False)], threshold_field="met_target",
    )
    assert unmet["status"] == GOAL_THRESHOLD_UNMET
    inconclusive = goal_outcome(
        goal="satisfice", observations=[{"other": 1}], threshold_field="met_target",
    )
    assert inconclusive["status"] == GOAL_INCONCLUSIVE


# ---------------------------------------------------------------------------
# Terminal outcomes and the goal orchestration path
# ---------------------------------------------------------------------------


class _Store:
    def __init__(self, rows, session=None):
        self._rows = rows
        self._session = session or {}

    async def get_session(self, research_id: str):
        return {"id": research_id, **self._session}

    async def get_iterations(self, research_id: str):
        return self._rows


def _orch(rows, skill):
    from src.core.orchestrator import AgentOrchestrator

    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._store = _Store(rows)
    orchestrator._session_skills = {"res_goal": skill}
    return orchestrator


def _config(**overrides):
    from src.core.orchestrator import ResearchConfig

    values = {
        "id": "res_goal",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": "direction",
        "tag": "goal-semantics",
        "quick_mode": True,
        "workspace_path": "/tmp/goal-semantics",
        "max_iterations": 10,
        "max_budget_usd": 50.0,
    }
    values.update(overrides)
    return ResearchConfig(**values)


@pytest.mark.asyncio
async def test_threshold_crossing_accepts_and_nudges_termination() -> None:
    skill = _goal_skill()
    orch = _orch([_row(1, _metrics(False, primary_metric=0.5))], skill)
    decision = await orch._infer_decision(
        "res_goal", 0.5, True, metrics=_metrics(True, primary_metric=0.5),
    )
    assert decision == "keep", "satisfice accepts a satisfied observation"
    message = await orch._maybe_goal_satisfied_terminate(research_id="res_goal")
    assert message is None, "unsatisfied so far — no termination nudge"
    orch._store = _Store([_row(2, _metrics(True, primary_metric=0.5))])
    message = await orch._maybe_goal_satisfied_terminate(research_id="res_goal")
    assert message is not None and "GOAL_SATISFICED" in message
    assert "TERMINATE_REQUEST" in message


@pytest.mark.asyncio
async def test_rejected_rows_cannot_satisfy_the_goal() -> None:
    skill = _goal_skill()
    rows = [_row(1, _metrics(True), duplicate_reason="dup")]
    orch = _orch(rows, skill)
    message = await orch._maybe_goal_satisfied_terminate(research_id="res_goal")
    assert message is None, "a rejected duplicate is not a verified observation"
    # A failed run carrying the threshold claim is not a verified observation
    # either — only verified results satisfy the goal.
    failed = [_row(1, _metrics(True))]
    failed[0]["status"] = "failed"
    orch._store = _Store(failed)
    message = await orch._maybe_goal_satisfied_terminate(research_id="res_goal")
    assert message is None, "a failed run cannot satisfy the goal"


@pytest.mark.asyncio
async def test_terminal_success_reflects_the_declared_condition() -> None:
    skill = _goal_skill()
    orch = _orch([_row(1, _metrics(True))], skill)
    reason = await orch._derive_terminal_reason(
        research_id="res_goal", final_status="completed", iteration_count=2,
        total_cost=1.0, config=_config(), timed_out=False, policy_aborted=False,
    )
    assert reason == GOAL_SATISFICED


@pytest.mark.asyncio
async def test_exhaustion_stays_distinct_from_success() -> None:
    skill = _goal_skill()
    orch = _orch([_row(1, _metrics(False))], skill)
    reason = await orch._derive_terminal_reason(
        research_id="res_goal", final_status="completed", iteration_count=10,
        total_cost=1.0, config=_config(), timed_out=False, policy_aborted=False,
    )
    assert reason == "max_iterations_reached", "never-satisfied is not success"


@pytest.mark.asyncio
async def test_inconclusive_outcome_is_distinct_from_success_and_exhaustion() -> None:
    skill = _goal_skill()
    orch = _orch([_row(1, {"primary_metric": 0.5})], skill)
    reason = await orch._derive_terminal_reason(
        research_id="res_goal", final_status="completed", iteration_count=2,
        total_cost=1.0, config=_config(), timed_out=False, policy_aborted=False,
    )
    assert reason == GOAL_INCONCLUSIVE



# ---------------------------------------------------------------------------
# Declarative phase predicates
# ---------------------------------------------------------------------------


def _phase_spec(pid, *, keys=(), min_iterations=1):
    return {
        "id": pid,
        "label": pid,
        "min_iterations": min_iterations,
        "max_iterations": 6,
        "evidence_keys": keys,
    }


def test_phase_requires_in_phase_verified_evidence() -> None:
    phases = [_phase_spec("threshold_probe", keys=("probe_passed",))]
    in_phase = [_row(1, {"probe_passed": True}, phase="threshold_probe")]
    completed = _completed_phase_ids(in_phase, [], [], "direction", phases=phases)
    assert "threshold_probe" in completed


def test_stale_unrelated_and_prose_evidence_never_advance_phases() -> None:
    phases = [_phase_spec("threshold_probe", keys=("probe_passed",))]
    # Stale: the key was emitted in an earlier/other phase's row.
    stale = [_row(1, {"probe_passed": True}, phase="baseline_capture")]
    assert "threshold_probe" not in _completed_phase_ids(
        stale, [], [], "direction", phases=phases,
    )
    # Model prose: a description claiming completion without the evidence key.
    prose = [_row(1, {"description": "probe done, all good"}, phase="threshold_probe")]
    assert "threshold_probe" not in _completed_phase_ids(
        prose, [], [], "direction", phases=phases,
    )
    # Rejected duplicates never count even carrying the key.
    rejected = [
        _row(1, {"probe_passed": True}, phase="threshold_probe", duplicate_reason="dup")
    ]
    assert "threshold_probe" not in _completed_phase_ids(
        rejected, [], [], "direction", phases=phases,
    )


def test_repeat_observations_satisfy_the_declared_minimum() -> None:
    phases = [_phase_spec("threshold_probe", keys=("probe_passed",), min_iterations=2)]
    one = [_row(1, {"probe_passed": True}, phase="threshold_probe")]
    assert "threshold_probe" not in _completed_phase_ids(
        one, [], [], "direction", phases=phases,
    ), "one observation does not meet the dwell floor of two"
    two = one + [_row(2, {"probe_passed": True}, phase="threshold_probe")]
    assert "threshold_probe" in _completed_phase_ids(
        two, [], [], "direction", phases=phases,
    ), "a repeat observation satisfies the declared minimum"


def test_declared_validation_phase_follows_its_rule() -> None:
    phases = [_phase_spec("validation", keys=("soak_test_passed",))]
    unmet = [
        _row(1, {"primary_metric": 0.5}, phase="validation"),
        _row(2, {"primary_metric": 0.6}, phase="validation"),
    ]
    assert "validation" in _completed_phase_ids(
        unmet, [], [], "direction",
    ), "the legacy validation cardinality rule is preserved"
    assert "validation" in _completed_phase_ids(
        [_row(1, {"soak_test_passed": True}, phase="validation")],
        [], [], "direction", phases=phases,
    )


# ---------------------------------------------------------------------------
# Unsupported plugin modes
# ---------------------------------------------------------------------------


def test_plugin_phase_modes_are_rejected_explicitly() -> None:
    from src.core.skill_manifest import ResearchSkillManifest

    base = {
        "schema_version": "research_skill.v1",
        "id": "plugin-skill",
        "version": "1.0.0",
        "category": "optimization",
        "display_name": "Plugin",
        "description": "plugin mode rejection case",
        "llm": {"provider": "anthropic", "primary_model": "m"},
        "workspace": {"session_path_template": "runs/{skill_id}"},
        "variants": {"static": ["v1"]},
        "param_schema": {"type": "object"},
        "metric_schema": {
            "primary": {"field": "m", "label": "M", "direction": "higher_is_better"},
        },
        "decision_vocabulary": {"base": ["keep"]},
        "phase_plan": [
            {"id": "p1", "min_iterations": 1, "max_iterations": 2, "evidence_keys": ["k"]},
        ],
        "command_policy": {},
        "output_parser": {"format": "delimited_kv"},
        "preflight": [],
        "promotion_target": {
            "primary": {"kind": "file_path", "path_template": "/tmp/x"},
        },
        "phase_advancement": {"mode": "plugin", "plugin": "phases.py"},
    }
    manifest = ResearchSkillManifest.model_validate(base)
    runtime = ManifestSkillRuntime(manifest, MagicMock())
    with pytest.raises(UnsupportedPhaseAdvancementError):
        runtime.phase_plan()
    with pytest.raises(UnsupportedPhaseAdvancementError):
        runtime.phase_advancement_rule("p1")

