"""Fix F: per-iteration API cost attribution.

`_record_iteration` used to leave every row's ``api_cost_usd`` at 0.0 — only
the session total was stored, so spend could not be attributed to iterations.
It now records the as-yet-unattributed portion of the cumulative cost, which is
ordering-independent: the turn's cost lands on the first iteration recorded
that turn.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from src.core.orchestrator import AgentOrchestrator
from src.core.results_store import ResultsStore


async def _create_session(store: ResultsStore, session_id: str) -> None:
    await store.create_session(
        session_id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag=session_id,
        quick_mode=True,
        max_iterations=10,
        max_budget_usd=5.0,
        focus_hint=None,
        workspace_path="/tmp/ws",
    )


def _marker(metric: float, cfg: str, phase: str = "tabular_sweeps") -> Dict[str, Any]:
    return {
        "primary_metric": metric,
        "metric_name": "auc",
        "all_gates_passed": True,
        "decision": "keep",
        "description": "iter",
        "config_snapshot": cfg,
        "training_time_s": 100.0,
        "search_phase": phase,
    }


@pytest.mark.asyncio
async def test_per_iteration_cost_is_delta_of_cumulative(tmp_path: Path) -> None:
    store = ResultsStore(str(tmp_path / "db_cost.sqlite"))
    await store.initialize()
    await _create_session(store, "res_cost")
    orch = AgentOrchestrator(store)

    # cumulative grows turn over turn; each iteration gets the new delta.
    await orch._record_iteration("res_cost", 1, _marker(0.60, "a: 1\n"), 0.30)
    await orch._record_iteration("res_cost", 2, _marker(0.61, "a: 2\n"), 0.50)
    await orch._record_iteration("res_cost", 3, _marker(0.62, "a: 3\n"), 1.05)

    r1 = await store.get_iteration("res_cost", 1)
    r2 = await store.get_iteration("res_cost", 2)
    r3 = await store.get_iteration("res_cost", 3)

    assert r1["api_cost_usd"] == pytest.approx(0.30)
    assert r2["api_cost_usd"] == pytest.approx(0.20)
    assert r3["api_cost_usd"] == pytest.approx(0.55)
    # Per-iteration costs reconcile to the final cumulative.
    total = r1["api_cost_usd"] + r2["api_cost_usd"] + r3["api_cost_usd"]
    assert total == pytest.approx(1.05)


@pytest.mark.asyncio
async def test_sibling_iterations_same_turn_do_not_double_count(tmp_path: Path) -> None:
    """Two iterations recorded in one turn share the same cumulative — the
    second must attribute 0, not re-bill the turn cost."""
    store = ResultsStore(str(tmp_path / "db_cost2.sqlite"))
    await store.initialize()
    await _create_session(store, "res_cost2")
    orch = AgentOrchestrator(store)

    await orch._record_iteration("res_cost2", 1, _marker(0.60, "a: 1\n"), 0.40)
    # same cumulative (no new turn cost) → delta 0
    await orch._record_iteration("res_cost2", 2, _marker(0.61, "a: 2\n"), 0.40)

    r1 = await store.get_iteration("res_cost2", 1)
    r2 = await store.get_iteration("res_cost2", 2)
    assert r1["api_cost_usd"] == pytest.approx(0.40)
    assert r2["api_cost_usd"] == pytest.approx(0.0)
