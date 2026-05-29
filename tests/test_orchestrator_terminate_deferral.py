"""DM-2 — defer TERMINATE_REQUEST when budget remains and best is fresh.

Run res_be66790e192e: agent emitted TERMINATE_REQUEST at iter 12 of a
50-iteration budget (24% used), last-best at iter 7 (gap=5), having
tried only 5 distinct configs. The orchestrator must reject the
terminate and inject a continuation nudge unless EITHER:
  * effective iteration count >= 50% of ``max_iterations`` (hard floor)
  * OR best_gap >= 5 (genuine stagnation already past the
    ``global_stagnation_window`` nudge).

Mirrors the existing global-stagnation test pattern; uses ResultsStore
directly so the helper exercises real session/iteration rows.
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

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
    sys.modules["anthropic"] = _stub

from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.results_store import ResultsStore


async def _new_store(tmp_path: Path) -> ResultsStore:
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    return store


async def _create_session(
    store: ResultsStore,
    sid: str,
    ws: Path,
    *,
    best_iteration: int | None,
    best_metric: float | None,
    max_iterations: int = 50,
) -> None:
    await store.create_session(
        session_id=sid,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag=sid,
        workspace_path=str(ws),
        max_iterations=max_iterations,
        max_budget_usd=100.0,
        quick_mode=False,
        focus_hint=None,
    )
    if best_iteration is not None:
        await store.update_session(
            sid,
            best_iteration=best_iteration,
            best_metric=best_metric,
        )


def _config(sid: str, *, max_iterations: int = 50) -> ResearchConfig:
    return ResearchConfig(
        id=sid,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        max_iterations=max_iterations,
    )


# --------------------------------------------------------------------------- #
# Core: the res_be66 scenario — defer at iter 12/50 with best_gap=5.
# Hmm — best_gap=5 actually exactly hits the floor, so we use gap=2 here
# (best at iter 10) to be unambiguously below the threshold.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_defers_terminate_when_budget_low_and_best_is_fresh(
    tmp_path: Path,
) -> None:
    store = await _new_store(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    await _create_session(
        store, "res_be66", ws,
        best_iteration=10,
        best_metric=0.40,
        max_iterations=50,
    )

    orchestrator = AgentOrchestrator(store)
    cfg = _config("res_be66")

    deferral = await orchestrator._should_defer_terminate(
        research_id="res_be66",
        iteration_count=12,  # iter 12/50 — 24% used
        duplicate_rejected_count=0,
        config=cfg,
    )

    assert deferral is not None
    assert "iters_used=12/50" in deferral["reason"]
    assert "best_gap=2" in deferral["reason"]
    # The nudge text should reference unexplored levers + the thresholds.
    assert "TERMINATE_REQUEST_DEFERRED" in deferral["text"]
    assert "25" in deferral["text"]  # 50% of 50 iterations = 25
    assert "5" in deferral["text"]   # best-gap floor


# --------------------------------------------------------------------------- #
# Honor: past the 50% budget floor → terminate is accepted.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_honors_terminate_when_budget_past_half(tmp_path: Path) -> None:
    store = await _new_store(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    await _create_session(
        store, "res_half", ws,
        best_iteration=20,
        best_metric=0.40,
        max_iterations=50,
    )

    orchestrator = AgentOrchestrator(store)
    cfg = _config("res_half")

    deferral = await orchestrator._should_defer_terminate(
        research_id="res_half",
        iteration_count=30,  # 60% of budget — past the floor
        duplicate_rejected_count=0,
        config=cfg,
    )

    assert deferral is None  # honor, no nudge


# --------------------------------------------------------------------------- #
# Honor: best_gap past the floor — genuine stagnation, terminate is fair.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_honors_terminate_when_best_gap_past_floor(tmp_path: Path) -> None:
    store = await _new_store(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    await _create_session(
        store, "res_stale", ws,
        best_iteration=3,
        best_metric=0.40,
        max_iterations=50,
    )

    orchestrator = AgentOrchestrator(store)
    cfg = _config("res_stale")

    # iter 12, best at 3 → gap=9 >= floor of 5 → honor.
    deferral = await orchestrator._should_defer_terminate(
        research_id="res_stale",
        iteration_count=12,
        duplicate_rejected_count=0,
        config=cfg,
    )
    assert deferral is None


# --------------------------------------------------------------------------- #
# Honor: no best_iteration yet (e.g. baseline crashed) — informed quit.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_honors_terminate_when_no_best_iteration_yet(
    tmp_path: Path,
) -> None:
    store = await _new_store(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    await _create_session(
        store, "res_zero", ws,
        best_iteration=None,
        best_metric=None,
        max_iterations=50,
    )

    orchestrator = AgentOrchestrator(store)
    cfg = _config("res_zero")

    deferral = await orchestrator._should_defer_terminate(
        research_id="res_zero",
        iteration_count=4,
        duplicate_rejected_count=0,
        config=cfg,
    )
    assert deferral is None


# --------------------------------------------------------------------------- #
# Duplicate-rejected iterations don't consume budget — defer should see
# the *effective* count, not the raw record count.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_duplicate_rejected_iterations_do_not_consume_budget(
    tmp_path: Path,
) -> None:
    store = await _new_store(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    await _create_session(
        store, "res_dups", ws,
        best_iteration=8,
        best_metric=0.40,
        max_iterations=50,
    )

    orchestrator = AgentOrchestrator(store)
    cfg = _config("res_dups")

    # raw=30, rejected=22 → effective=8 → still well under 50% floor,
    # gap = 8 - 8 = 0 → defer.
    deferral = await orchestrator._should_defer_terminate(
        research_id="res_dups",
        iteration_count=30,
        duplicate_rejected_count=22,
        config=cfg,
    )
    assert deferral is not None
    assert "iters_used=8/50" in deferral["reason"]


# --------------------------------------------------------------------------- #
# Constants locked — keep the protective floor explicit and reviewable.
# --------------------------------------------------------------------------- #
def test_dm2_thresholds_locked() -> None:
    assert AgentOrchestrator._DM2_BUDGET_DEFER_FRACTION == 0.5
    assert AgentOrchestrator._DM2_BEST_GAP_DEFER_FLOOR == 5
