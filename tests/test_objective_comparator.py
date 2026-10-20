"""Tests for the one objective comparator shared by every winner-selection path.

Contract: winner selection resolves a single comparator from the declared
objective (direction + declared epsilon) and every path compares through it.
Minimization and maximization select their own winners; ties within epsilon
preserve the existing eligible winner; absent/nonfinite metrics never win;
failed-gate rows are never promotable bests; ambiguous historical objective
data is flagged, never guessed.
"""

from __future__ import annotations

import sys
import types
import uuid
from collections.abc import Mapping, Sequence
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, Optional, cast

import pytest

# The orchestrator imports the anthropic SDK at module level; keep the test
# import surface identical to the existing orchestrator suites.
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
from src.core.objective_comparator import (
    ObjectiveComparator,
    ObjectiveContextError,
    objective_comparator_for_manifest,
    rank_rows,
    reconcile_historical_best,
    select_best_row,
)
from src.core.results_store import ResultsStore


def _skill(direction: str, field: str = "primary_metric") -> SimpleNamespace:
    primary = SimpleNamespace(direction=direction, field=field)
    return SimpleNamespace(
        manifest=SimpleNamespace(metric_schema=SimpleNamespace(primary=primary)),
    )


class _FakeRegistry:
    def __init__(self, skills: Dict[str, SimpleNamespace]) -> None:
        self._skills = skills

    def get(self, skill_id: str) -> SimpleNamespace:
        if skill_id not in self._skills:
            raise KeyError(skill_id)
        return self._skills[skill_id]


async def _seed_session(
    store: ResultsStore,
    research_id: str,
    *,
    best_iteration: Optional[int] = None,
    best_metric: Optional[float] = None,
) -> None:
    await store.create_session(
        session_id=research_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="objective-comparator",
        quick_mode=False,
        max_iterations=50,
        max_budget_usd=50.0,
        focus_hint=None,
        workspace_path="/tmp/ws",
    )
    if best_iteration is not None or best_metric is not None:
        await store.update_session(
            research_id, best_iteration=best_iteration, best_metric=best_metric,
        )


# ---------------------------------------------------------------------------
# Comparator semantics
# ---------------------------------------------------------------------------


def test_lower_metric_improves_and_higher_regresses_under_minimization() -> None:
    """The minimization acceptance case: 100 -> 80 improves, 100 -> 120 regresses."""
    comparator = ObjectiveComparator(direction="minimize")
    assert comparator.compare(80.0, 100.0) == "better"
    assert comparator.compare(120.0, 100.0) == "worse"
    assert comparator.is_better(80.0, 100.0) is True
    assert comparator.is_better(120.0, 100.0) is False


def test_maximization_behavior_remains_correct() -> None:
    comparator = ObjectiveComparator(direction="maximize")
    assert comparator.compare(120.0, 100.0) == "better"
    assert comparator.compare(80.0, 100.0) == "worse"


def test_ties_within_epsilon_preserve_the_existing_eligible_winner() -> None:
    comparator = ObjectiveComparator(direction="minimize", epsilon=1e-4)
    assert comparator.compare(100.00005, 100.0) == "tie"
    assert comparator.is_better(100.00005, 100.0) is False
    rows: list[dict[str, Any]] = [
        {"iteration": 1, "metric": 100.0},
        {"iteration": 2, "metric": 100.00005},
    ]
    winner = select_best_row(
        rows, comparator, value=lambda row: row["metric"],
    )
    assert winner == {"iteration": 1, "metric": 100.0}


def test_exact_comparison_when_no_epsilon_is_declared() -> None:
    comparator = ObjectiveComparator(direction="minimize")
    assert comparator.epsilon == 0.0
    assert comparator.compare(100.00005, 100.0) == "worse"
    assert comparator.compare(100.0, 100.0) == "tie"


def test_declared_policy_tolerance_precedes_operational_epsilon() -> None:
    policy = SimpleNamespace(
        direction="minimize", metric_field="p95_latency_ms", tie_tolerance=0.5,
    )
    comparator = ObjectiveComparator.resolve(policy=policy, epsilon=1e-4)
    assert comparator.epsilon == 0.5
    assert comparator.direction == "minimize"
    assert comparator.metric_field == "p95_latency_ms"
    fallback = ObjectiveComparator.resolve(
        policy=SimpleNamespace(direction="maximize", tie_tolerance=0.0),
        epsilon=1e-4,
    )
    assert fallback.epsilon == 1e-4


def test_absent_and_nonfinite_metrics_never_win() -> None:
    comparator = ObjectiveComparator(direction="minimize")
    assert comparator.compare(None, 100.0) == "incomparable"
    assert comparator.compare(float("nan"), 100.0) == "incomparable"
    assert comparator.compare(float("inf"), 100.0) == "incomparable"
    assert comparator.is_better(float("inf"), 100.0) is False
    # Any finite result beats an absent incumbent and establishes the best.
    assert comparator.compare(100.0, None) == "better"
    rows: list[dict[str, Any]] = [
        {"iteration": 1, "metric": float("inf")},
        {"iteration": 2, "metric": 5.0},
        {"iteration": 3, "metric": None},
    ]
    winner = select_best_row(rows, comparator, value=lambda row: row["metric"])
    assert winner == {"iteration": 2, "metric": 5.0}


def test_unknown_objective_context_is_rejected_not_guessed() -> None:
    with pytest.raises(ObjectiveContextError):
        ObjectiveComparator(direction="sideways")  # type: ignore[arg-type]
    with pytest.raises(ObjectiveContextError):
        ObjectiveComparator.resolve(direction=None)
    with pytest.raises(ObjectiveContextError):
        objective_comparator_for_manifest(SimpleNamespace())
    with pytest.raises(ObjectiveContextError):
        ObjectiveComparator(epsilon=-1.0)


def test_manifest_vocabulary_maps_through_the_contract_bridge() -> None:
    lower = objective_comparator_for_manifest(_skill("lower_is_better").manifest)
    higher = objective_comparator_for_manifest(_skill("higher_is_better").manifest)
    assert (lower.direction, higher.direction) == ("minimize", "maximize")


# ---------------------------------------------------------------------------
# Decision path (keep/improve/discard)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keep_discard_decision_honors_minimization(tmp_path) -> None:
    """Under a minimize objective, 100 -> 80 keeps and 100 -> 120 discards."""
    from src.core.orchestrator import AgentOrchestrator

    store = ResultsStore(str(tmp_path / "decision.sqlite"))
    await store.initialize()
    rid = "res_minimize_decision"
    await _seed_session(store, rid, best_iteration=1, best_metric=100.0)
    orch = AgentOrchestrator(store)
    orch._session_skills[rid] = _skill("lower_is_better")
    assert await orch._infer_decision(rid, 80.0, True) == "keep"
    assert await orch._infer_decision(rid, 120.0, True) == "discard"
    assert await orch._infer_decision(rid, 80.0, False) == "improve"
    assert await orch._infer_decision(rid, None, True) == "discard"


@pytest.mark.asyncio
async def test_keep_discard_decision_honors_maximization(tmp_path) -> None:
    from src.core.orchestrator import AgentOrchestrator

    store = ResultsStore(str(tmp_path / "decision_max.sqlite"))
    await store.initialize()
    rid = "res_maximize_decision"
    await _seed_session(store, rid, best_iteration=1, best_metric=100.0)
    orch = AgentOrchestrator(store)
    orch._session_skills[rid] = _skill("higher_is_better")
    assert await orch._infer_decision(rid, 120.0, True) == "keep"
    assert await orch._infer_decision(rid, 80.0, True) == "discard"


# ---------------------------------------------------------------------------
# Stored bests: update + selection (the cross-store comparison matrix)
# ---------------------------------------------------------------------------


async def _run_best_matrix(store: Any, rid: str) -> Dict[str, Any]:
    """Seed one minimization session and return every winner-selection view."""
    objective = ObjectiveComparator(direction="minimize", epsilon=1e-4)
    await _seed_session(store, rid)
    for iteration, metric, decision, gates in (
        (1, 100.0, "keep", True),
        (2, 80.0, "keep", True),
        (3, 120.0, "keep", True),
        (4, 80.00005, "keep", True),
        (5, 70.0, "improve", False),
        (6, float("inf"), "keep", True),
    ):
        await store.add_iteration(
            research_id=rid,
            iteration=iteration,
            primary_metric=metric,
            metric_name="p95_latency_ms",
            all_gates_passed=gates,
            decision=decision,
            description=None,
            config_snapshot=None,
            metrics_json="{}",
            training_time_s=1.0,
            objective=objective,
            metric_improvement_epsilon=1e-4,
        )
    session = await store.get_session(rid)
    best = await store.get_best_iteration(rid, objective=objective)
    legacy_best = await store.get_best_iteration(rid)
    return {
        "stored_best_iteration": session["best_iteration"],
        "stored_best_metric": session["best_metric"],
        "selected_iteration": (best or {}).get("iteration"),
        "legacy_selected_iteration": (legacy_best or {}).get("iteration"),
    }


@pytest.mark.asyncio
async def test_sqlite_best_update_and_selection_honor_minimization(tmp_path) -> None:
    store = ResultsStore(str(tmp_path / "best_matrix.sqlite"))
    await store.initialize()
    outcome = await _run_best_matrix(store, "res_best_matrix")
    # 100 -> 80 moves best; 120 does not; 80.00005 is within epsilon (tie);
    # 70 has failed gates (never promotable) and inf is nonfinite (never wins).
    assert outcome["stored_best_iteration"] == 2
    assert outcome["stored_best_metric"] == pytest.approx(80.0)
    assert outcome["selected_iteration"] == 2
    # The same rows under the legacy maximize default select the other extreme,
    # proving the comparator is what selects.
    assert outcome["legacy_selected_iteration"] == 3


@pytest.mark.asyncio
async def test_best_selection_ties_keep_earliest_and_gates_are_eligible(tmp_path) -> None:
    store = ResultsStore(str(tmp_path / "best_ties.sqlite"))
    await store.initialize()
    rid = "res_best_ties"
    await _seed_session(store, rid)
    objective = ObjectiveComparator(direction="maximize")
    for iteration, metric, gates in (
        (1, 0.5, True),
        (2, 0.5, True),
        (3, 0.9, False),
    ):
        await store.add_iteration(
            research_id=rid,
            iteration=iteration,
            primary_metric=metric,
            metric_name="score",
            all_gates_passed=gates,
            decision="keep",
            description=None,
            config_snapshot=None,
            metrics_json="{}",
            training_time_s=1.0,
            objective=objective,
        )
    best = await store.get_best_iteration(rid, objective=objective)
    assert best["iteration"] == 1  # exact tie keeps the earliest eligible winner


@pytest.mark.asyncio
async def test_postgres_best_selection_matches_the_sqlite_matrix(tmp_path) -> None:
    """Cross-store parity: Postgres picks the same winner as the SQLite matrix.

    Skips when no test DSN is configured (same contract as the parity suite).
    """
    import asyncpg

    from src.core.postgres_state_store import PostgresStateStore

    raw = __import__("os").getenv("AUTORESEARCH_DATABASE_URL") or __import__("os").getenv(
        "DATABASE_URL"
    )
    if not raw:
        pytest.skip("AUTORESEARCH_DATABASE_URL unset")
    base = raw.replace("postgresql+asyncpg://", "postgresql://")
    dbname = f"autoresearch_objective_{uuid.uuid4().hex[:12]}"
    admin_dsn = base.rsplit("/", 1)[0] + "/postgres"
    admin = await asyncpg.connect(admin_dsn)
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        await admin.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await admin.close()
    store = PostgresStateStore(base.rsplit("/", 1)[0] + f"/{dbname}")
    await store.initialize()
    try:
        outcome = await _run_best_matrix(store, "res_best_matrix_pg")
    finally:
        await store.close()
        cleanup = await asyncpg.connect(admin_dsn)
        try:
            await cleanup.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        finally:
            await cleanup.close()
    assert outcome["stored_best_iteration"] == 2
    assert outcome["selected_iteration"] == 2
    assert outcome["legacy_selected_iteration"] == 3


@pytest.mark.asyncio
async def test_stagnation_gap_tracks_the_direction_aware_best(tmp_path) -> None:
    from src.core.orchestrator import AgentOrchestrator

    store = ResultsStore(str(tmp_path / "stagnation.sqlite"))
    await store.initialize()
    rid = "res_minimize_stagnation"
    await _seed_session(store, rid)
    orch = AgentOrchestrator(store)
    orch._session_skills[rid] = _skill("lower_is_better")
    objective = ObjectiveComparator(direction="minimize", epsilon=1e-4)
    for iteration, metric in ((1, 100.0), (2, 90.0), (3, 95.0), (4, 96.0)):
        decision = await orch._infer_decision(rid, metric, True)
        await store.add_iteration(
            research_id=rid,
            iteration=iteration,
            primary_metric=metric,
            metric_name="p95_latency_ms",
            all_gates_passed=True,
            decision=decision,
            description=None,
            config_snapshot=None,
            metrics_json="{}",
            training_time_s=1.0,
            objective=objective,
        )
    session = await store.get_session(rid)
    assert session["best_iteration"] == 2  # 90 is the best latency; 95/96 regressed
    assert await orch._maybe_global_stagnation_terminate(
        research_id=rid, iteration_count=5,
    ) is None
    message = await orch._maybe_global_stagnation_terminate(
        research_id=rid, iteration_count=14,
    )
    assert message is not None and "GLOBAL_STAGNATION" in message
    assert "beyond the session best" in message


# ---------------------------------------------------------------------------
# Promotion eligibility (the minimization promotion preview)
# ---------------------------------------------------------------------------


def _baseline_row(metric: float) -> Dict[str, Any]:
    return {
        "id": 1,
        "research_id": "res_previous",
        "iteration": 3,
        "best_metric": metric,
        "best_metric_name": "p95_latency_ms",
        "composite_formula_version": "v1",
        "promoted_at": "2026-01-01T00:00:00Z",
    }


async def _promotion_verdict(
    comparator: ObjectiveComparator, candidate: float, baseline: float,
) -> Dict[str, Any]:
    from src.core.config_promoter import ConfigPromoter

    promoter = ConfigPromoter(SimpleNamespace())

    async def _fake_baseline(**kwargs: Any) -> Dict[str, Any]:
        return _baseline_row(baseline)

    promoter._latest_eligible_development_baseline = _fake_baseline  # type: ignore[assignment]
    return await promoter._build_quality_baseline_evaluation(
        research_id="res_candidate",
        best_iteration={
            "iteration": 7,
            "primary_metric": candidate,
            "metric_name": "p95_latency_ms",
            "composite_formula_version": "v1",
            "metrics_json": "{}",
        },
        model_type="direction",
        instrument="DOGE_USDT",
        timeframe="15m",
        comparator=comparator,
    )


@pytest.mark.asyncio
async def test_promotion_preview_blocks_minimization_regression() -> None:
    minimize = ObjectiveComparator(direction="minimize", epsilon=1e-4)
    improved = await _promotion_verdict(minimize, 80.0, 100.0)
    assert improved["passed"] is True
    assert improved["comparison"]["direction"] == "minimize"
    regressed = await _promotion_verdict(minimize, 120.0, 100.0)
    assert regressed["passed"] is False
    assert regressed["blockers"]
    assert regressed["comparison"]["direction"] == "minimize"


@pytest.mark.asyncio
async def test_promotion_preview_keeps_maximization_behavior() -> None:
    maximize = ObjectiveComparator(direction="maximize", epsilon=1e-4)
    improved = await _promotion_verdict(maximize, 120.0, 100.0)
    assert improved["passed"] is True
    regressed = await _promotion_verdict(maximize, 80.0, 100.0)
    assert regressed["passed"] is False


# ---------------------------------------------------------------------------
# Aggregate queries / displayed rankings
# ---------------------------------------------------------------------------


def test_ranking_orders_by_declared_direction_stably() -> None:
    rows: list[dict[str, Any]] = [
        {"id": "a", "best_metric": 100.0},
        {"id": "b", "best_metric": 80.0},
        {"id": "c", "best_metric": None},
        {"id": "d", "best_metric": 120.0},
    ]
    minimize = ObjectiveComparator(direction="minimize")
    assert [r["id"] for r in rank_rows(rows, minimize, value=lambda r: r["best_metric"])] == [
        "b",
        "a",
        "d",
        "c",
    ]
    maximize = ObjectiveComparator(direction="maximize")
    assert [r["id"] for r in rank_rows(rows, maximize, value=lambda r: r["best_metric"])] == [
        "d",
        "a",
        "b",
        "c",
    ]


# ---------------------------------------------------------------------------
# Historical reconciliation
# ---------------------------------------------------------------------------


def _historical_rows() -> list[Dict[str, Any]]:
    return [
        {"iteration": 1, "primary_metric": 100.0, "all_gates_passed": True},
        {"iteration": 2, "primary_metric": 80.0, "all_gates_passed": True},
        {"iteration": 3, "primary_metric": 120.0, "all_gates_passed": True},
        {"iteration": 4, "primary_metric": 70.0, "all_gates_passed": False},
    ]


def test_reconciliation_uses_the_known_objective() -> None:
    session = {"id": "res_hist", "best_iteration": 3, "best_metric": 120.0}
    report = reconcile_historical_best(
        session=session,
        iterations=_historical_rows(),
        comparator=ObjectiveComparator(direction="minimize"),
    )
    assert report["status"] == "reconciled"
    assert report["objective"]["direction"] == "minimize"
    assert report["recomputed"] == {"best_iteration": 2, "best_metric": 80.0}
    assert "stored_best_differs_from_recomputed" in report["flags"]


def test_reconciliation_flags_ambiguous_objective_without_guessing() -> None:
    session = {
        "id": "res_legacy",
        "skill_id": "skill-that-does-not-exist",
        "best_iteration": 3,
        "best_metric": 120.0,
    }
    report = reconcile_historical_best(
        session=session, iterations=_historical_rows(),
    )
    assert report["status"] == "ambiguous_objective"
    assert report["recomputed"] is None  # never guessed
    assert report["objective"]["direction"] is None
    assert "objective_direction_unknown" in report["flags"]


def test_reconciliation_reports_consistent_and_no_eligible() -> None:
    minimize = ObjectiveComparator(direction="minimize")
    consistent = reconcile_historical_best(
        session={"id": "res_ok", "best_iteration": 2, "best_metric": 80.0},
        iterations=_historical_rows(),
        comparator=minimize,
    )
    assert consistent["status"] == "consistent"
    assert consistent["flags"] == []
    no_eligible = reconcile_historical_best(
        session={"id": "res_empty"},
        iterations=[{"iteration": 1, "primary_metric": None, "all_gates_passed": False}],
        comparator=minimize,
    )
    assert no_eligible["status"] == "no_eligible"
    assert "no_gates_passing_metric_rows" in no_eligible["flags"]


# ---------------------------------------------------------------------------
# Operator command
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconcile_bests_command_reports_flags_and_applies(
    tmp_path, monkeypatch, capsys,
) -> None:
    from src.cli import build_parser, cmd_reconcile_bests

    db_path = str(tmp_path / "reconcile.db")
    store = ResultsStore(db_path)
    await store.initialize()
    await _seed_session(store, "res_reconcilable", best_iteration=3, best_metric=120.0)
    await _seed_session(store, "res_ambiguous", best_iteration=1, best_metric=1.0)
    # The legacy row carries no resolvable objective provenance at all.
    await store.update_session("res_ambiguous", model_type="legacy-no-objective")
    for rid in ("res_reconcilable", "res_ambiguous"):
        for row in _historical_rows():
            await store.add_iteration(
                research_id=rid,
                iteration=row["iteration"],
                primary_metric=row["primary_metric"],
                metric_name="p95_latency_ms",
                all_gates_passed=row["all_gates_passed"],
                decision="keep",
                description=None,
                config_snapshot=None,
                metrics_json="{}",
                training_time_s=1.0,
                objective=ObjectiveComparator(direction="minimize"),
            )
    await store.close()
    monkeypatch.setattr(
        "src.core.skill_registry.default_registry",
        _FakeRegistry({"direction": _skill("lower_is_better")}),
    )

    parser = build_parser()
    assert await cmd_reconcile_bests(
        parser.parse_args(["reconcile-bests", "--db", db_path])
    ) == 0
    out = capsys.readouterr().out
    assert "res_reconcilable: reconciled" in out
    assert "res_ambiguous: ambiguous_objective" in out
    assert "objective_direction_unknown" in out
    assert "(dry-run)" in out

    assert await cmd_reconcile_bests(
        parser.parse_args(["reconcile-bests", "--db", db_path, "--apply"])
    ) == 0
    assert "(applied)" in capsys.readouterr().out
    reopened = ResultsStore(db_path)
    await reopened.initialize()
    try:
        fixed = await reopened.get_session("res_reconcilable")
        untouched = await reopened.get_session("res_ambiguous")
    finally:
        await reopened.close()
    assert fixed["best_iteration"] == 2
    assert fixed["best_metric"] == pytest.approx(80.0)
    assert untouched["best_iteration"] == 1  # ambiguous rows are never migrated


# ---------------------------------------------------------------------------
# Review regressions: every winner-selection helper, and alias provenance
# ---------------------------------------------------------------------------


def test_prior_best_selection_honors_direction() -> None:
    from src.core.research_phase_plan import _prior_best_metrics

    rows: list[dict[str, Any]] = [
        {
            "iteration": it,
            "primary_metric": value,
            "decision": "keep",
            "search_phase": "tabular_sweeps",
            "metrics_json": '{"primary_metric": %s}' % value,
        }
        for it, value in ((1, 100.0), (2, 80.0), (3, 120.0))
    ]
    minimize = ObjectiveComparator(direction="minimize")
    assert _prior_best_metrics(rows, comparator=minimize)["primary_metric"] == 80.0
    assert _prior_best_metrics(rows)["primary_metric"] == 120.0  # legacy default


def test_production_champion_and_best_line_honor_direction() -> None:
    from src.core.iteration_context import _best_line
    from src.core.research_state import _best_candidate_row

    rows: list[dict[str, Any]] = [
        {"iteration": 1, "primary_metric": 100.0, "decision": "keep",
         "all_gates_passed": True},
        {"iteration": 2, "primary_metric": 80.0, "decision": "keep",
         "all_gates_passed": True},
        {"iteration": 3, "primary_metric": 120.0, "decision": "keep",
         "all_gates_passed": True},
    ]
    minimize = ObjectiveComparator(direction="minimize")
    champion = _best_candidate_row(rows, comparator=minimize)
    assert champion["iteration"] == 2
    assert _best_line(rows, comparator=minimize).startswith("iteration 2")
    maximize = ObjectiveComparator(direction="maximize")
    assert _best_candidate_row(rows, comparator=maximize)["iteration"] == 3
    assert _best_line(rows, comparator=maximize).startswith("iteration 3")


def test_legacy_model_type_alias_resolves_the_objective(monkeypatch) -> None:
    """A legacy model_type session name is objective provenance, not a guess."""
    from src.core.objective_comparator import objective_comparator_for_skill_id

    monkeypatch.setattr(
        "src.core.skill_registry.default_registry",
        _FakeRegistry({"ml-direction": _skill("lower_is_better")}),
    )
    comparator = objective_comparator_for_skill_id("direction")
    assert comparator.direction == "minimize"
