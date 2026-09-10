"""AR-7: Tests for _maybe_global_stagnation_terminate.

Defect D7: Sessions with no metric improvement for many consecutive iterations
kept running experiments until max_iterations or budget was exhausted, with no
prompt to the LLM to terminate gracefully.

Fix: after each tool-call round, the orchestrator calls
``_maybe_global_stagnation_terminate``.  When the session's
``best_iteration`` is more than ``settings.global_stagnation_window``
iterations behind the current iteration count, a ``GLOBAL_STAGNATION`` system
message is injected into ``tool_results`` demanding a ``TERMINATE_REQUEST:``.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

# ---------------------------------------------------------------------------
# Stub Anthropic SDK (same pattern as other orchestrator tests)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(research_id: str) -> ResearchConfig:
    return ResearchConfig(
        id=research_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="ar7-test",
        max_iterations=100,
        max_budget_usd=50.0,
        workspace_path="/ws",
    )


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
        tag="ar7-test",
        quick_mode=False,
        max_iterations=100,
        max_budget_usd=50.0,
        focus_hint=None,
        workspace_path="/ws",
    )
    if best_iteration is not None or best_metric is not None:
        await store.update_session(
            research_id,
            best_iteration=best_iteration,
            best_metric=best_metric,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_global_stagnation_injects_terminate_warning_after_window(
    tmp_path: Path,
) -> None:
    """AR-7 core: stagnation nudge fires after global_stagnation_window iterations.

    Default window is 12.  If best_iteration=1 and iteration_count=13,
    the gap is 12 >= window, so the method must return a non-None message
    containing 'GLOBAL_STAGNATION' and 'TERMINATE_REQUEST'.
    """
    store = ResultsStore(str(tmp_path / "ar7_stagnation.sqlite"))
    await store.initialize()
    rid = "res_ar7_stagnation"
    await _seed_session(store, rid, best_iteration=1, best_metric=0.6394)

    orch = AgentOrchestrator(store)

    result = await orch._maybe_global_stagnation_terminate(
        research_id=rid,
        iteration_count=13,  # gap = 13 - 1 = 12 >= default window 12
    )

    assert result is not None, (
        "Gap of 12 iterations at default window=12 must trigger the stagnation nudge"
    )
    assert "GLOBAL_STAGNATION" in result
    assert "TERMINATE_REQUEST" in result
    assert "0.6394" in result or "0.6394" in result  # best metric present in message
    # Should mention how many iterations since best
    assert "12" in result


@pytest.mark.asyncio
async def test_global_stagnation_does_not_fire_before_window(
    tmp_path: Path,
) -> None:
    """AR-7: no nudge when gap < window (still within improvement horizon)."""
    store = ResultsStore(str(tmp_path / "ar7_nofire.sqlite"))
    await store.initialize()
    rid = "res_ar7_nofire"
    await _seed_session(store, rid, best_iteration=1, best_metric=0.6394)

    orch = AgentOrchestrator(store)

    result = await orch._maybe_global_stagnation_terminate(
        research_id=rid,
        iteration_count=12,  # gap = 12 - 1 = 11 < 12
    )

    assert result is None, "Gap of 11 is less than default window 12 — must NOT fire"


@pytest.mark.asyncio
async def test_global_stagnation_resets_after_metric_improvement(
    tmp_path: Path,
) -> None:
    """AR-7: window re-arms from the new best_iteration after improvement.

    Improvement at iteration 5 sets best_iteration=5.
    At iteration 16 (gap=11 < 12): no nudge.
    At iteration 17 (gap=12 >= 12): nudge fires.
    """
    store = ResultsStore(str(tmp_path / "ar7_reset.sqlite"))
    await store.initialize()
    rid = "res_ar7_reset"
    # Simulates improvement recorded at iteration 5
    await _seed_session(store, rid, best_iteration=5, best_metric=0.7100)

    orch = AgentOrchestrator(store)

    # Just before window: gap = 16 - 5 = 11 → no nudge
    result_no_fire = await orch._maybe_global_stagnation_terminate(
        research_id=rid,
        iteration_count=16,
    )
    assert result_no_fire is None, "Gap 11 < window 12 — must NOT fire after reset"

    # At window boundary: gap = 17 - 5 = 12 → nudge fires
    result_fire = await orch._maybe_global_stagnation_terminate(
        research_id=rid,
        iteration_count=17,
    )
    assert result_fire is not None, "Gap 12 >= window 12 — must fire after reset"
    assert "GLOBAL_STAGNATION" in result_fire


@pytest.mark.asyncio
async def test_global_stagnation_window_configurable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AR-7: global_stagnation_window is read from settings; override via monkeypatch.

    With window=5: gap=5 fires; gap=4 does not.
    """
    import src.core.orchestrator as orch_module

    # Patch the settings object used inside the orchestrator module.
    monkeypatch.setattr(orch_module.settings, "global_stagnation_window", 5)

    store = ResultsStore(str(tmp_path / "ar7_window.sqlite"))
    await store.initialize()
    rid = "res_ar7_window"
    await _seed_session(store, rid, best_iteration=1, best_metric=0.6000)

    orch = AgentOrchestrator(store)

    # gap = 5 - 1 = 4 < 5 → no nudge
    result_no_fire = await orch._maybe_global_stagnation_terminate(
        research_id=rid, iteration_count=5
    )
    assert result_no_fire is None, "Gap 4 < custom window 5 — must NOT fire"

    # gap = 6 - 1 = 5 >= 5 → nudge fires
    result_fire = await orch._maybe_global_stagnation_terminate(
        research_id=rid, iteration_count=6
    )
    assert result_fire is not None, "Gap 5 >= custom window 5 — must fire"
    assert "GLOBAL_STAGNATION" in result_fire


@pytest.mark.asyncio
async def test_global_stagnation_epsilon_prevents_tiny_best_reset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Improvements <= epsilon must not reset best_iteration."""
    import src.core.orchestrator as orch_module

    monkeypatch.setattr(orch_module.settings, "global_stagnation_epsilon", 0.0001)

    store = ResultsStore(str(tmp_path / "ar7_epsilon_tiny.sqlite"))
    await store.initialize()
    rid = "res_ar7_epsilon_tiny"
    await _seed_session(store, rid)

    await store.add_iteration(
        research_id=rid, iteration=1, primary_metric=0.6000,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="best", config_snapshot="a: 1\n", metrics_json="{}",
        training_time_s=1.0,
        metric_improvement_epsilon=orch_module.settings.global_stagnation_epsilon,
    )
    await store.add_iteration(
        research_id=rid, iteration=2, primary_metric=0.60005,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="noise", config_snapshot="a: 2\n", metrics_json="{}",
        training_time_s=1.0,
        metric_improvement_epsilon=orch_module.settings.global_stagnation_epsilon,
    )

    session = await store.get_session(rid)
    assert session["best_iteration"] == 1
    assert session["best_metric"] == pytest.approx(0.6000)

    orch = AgentOrchestrator(store)
    result = await orch._maybe_global_stagnation_terminate(
        research_id=rid,
        iteration_count=13,
    )
    assert result is not None
    assert "GLOBAL_STAGNATION" in result


@pytest.mark.asyncio
async def test_global_stagnation_epsilon_allows_real_best_reset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Improvements > epsilon reset best_iteration and delay the nudge."""
    import src.core.orchestrator as orch_module

    monkeypatch.setattr(orch_module.settings, "global_stagnation_epsilon", 0.0001)

    store = ResultsStore(str(tmp_path / "ar7_epsilon_real.sqlite"))
    await store.initialize()
    rid = "res_ar7_epsilon_real"
    await _seed_session(store, rid)

    await store.add_iteration(
        research_id=rid, iteration=1, primary_metric=0.6000,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="best", config_snapshot="a: 1\n", metrics_json="{}",
        training_time_s=1.0,
        metric_improvement_epsilon=orch_module.settings.global_stagnation_epsilon,
    )
    await store.add_iteration(
        research_id=rid, iteration=2, primary_metric=0.6002,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="real improvement", config_snapshot="a: 2\n", metrics_json="{}",
        training_time_s=1.0,
        metric_improvement_epsilon=orch_module.settings.global_stagnation_epsilon,
    )

    session = await store.get_session(rid)
    assert session["best_iteration"] == 2
    assert session["best_metric"] == pytest.approx(0.6002)

    orch = AgentOrchestrator(store)
    result = await orch._maybe_global_stagnation_terminate(
        research_id=rid,
        iteration_count=13,
    )
    assert result is None


@pytest.mark.asyncio
async def test_global_stagnation_no_fire_when_no_best_iteration(
    tmp_path: Path,
) -> None:
    """AR-7: conservative — no nudge when session has no best_iteration yet."""
    store = ResultsStore(str(tmp_path / "ar7_nob.sqlite"))
    await store.initialize()
    rid = "res_ar7_nob"
    # No best_iteration / best_metric set
    await _seed_session(store, rid)

    orch = AgentOrchestrator(store)

    result = await orch._maybe_global_stagnation_terminate(
        research_id=rid,
        iteration_count=20,
    )
    assert result is None, "No best_iteration recorded → conservative, no nudge"


@pytest.mark.asyncio
async def test_global_stagnation_fires_exactly_at_window_boundary(
    tmp_path: Path,
) -> None:
    """AR-7: exactly gap == window is the first trigger point (>= boundary).

    best_iteration=1, window=12: fires at iteration_count=13, not at 12.
    """
    store = ResultsStore(str(tmp_path / "ar7_boundary.sqlite"))
    await store.initialize()
    rid = "res_ar7_boundary"
    await _seed_session(store, rid, best_iteration=1, best_metric=0.5500)

    orch = AgentOrchestrator(store)

    # One short: gap=11 → no fire
    assert await orch._maybe_global_stagnation_terminate(
        research_id=rid, iteration_count=12
    ) is None

    # Exactly at window: gap=12 → fires
    assert await orch._maybe_global_stagnation_terminate(
        research_id=rid, iteration_count=13
    ) is not None


@pytest.mark.asyncio
async def test_global_stagnation_does_not_fire_in_exempt_phase(
    tmp_path: Path,
) -> None:
    """Phase-aware guard: stagnation must NOT fire when current_phase is exempt
    AND the agent did genuine work in that phase (Fix 5).

    promotion_proposal is a validation phase — metric improvement is not expected.
    To honor the exemption we require at least one in-phase iteration carrying
    explicit (non-auto) agent evidence; otherwise the phase was advanced via
    permissive auto-evidence and stagnation should still fire.
    """
    import json as _json

    store = ResultsStore(str(tmp_path / "ar7_exempt.sqlite"))
    await store.initialize()
    rid = "res_ar7_exempt"
    await _seed_session(store, rid, best_iteration=1, best_metric=0.6394)
    await store.update_session(
        rid,
        phase_state_json=_json.dumps({"current_phase": "promotion_proposal"}),
    )

    await store.add_iteration(
        research_id=rid,
        iteration=1,
        primary_metric=0.6394,
        metric_name="composite_direction_score",
        all_gates_passed=True,
        decision="keep",
        description="genuine promotion exploration",
        config_snapshot=None,
        metrics_json=_json.dumps(
            {"promotion_metadata": {"owner": "t"}, "auto_phase_evidence": True}
        ),
        training_time_s=120.0,
        search_phase="promotion_proposal",
    )

    orch = AgentOrchestrator(store)

    class _ProbeSkill:
        def blocker_classification(self):
            return {
                "actionable_blockers": [],
                "phase_evidence_keys": {
                    "promotion_proposal": ["promotion_metadata"],
                },
            }

    orch._session_skills[rid] = _ProbeSkill()

    result = await orch._maybe_global_stagnation_terminate(
        research_id=rid,
        iteration_count=13,  # gap=12 >= default window=12 — would normally fire
    )
    assert result is None, (
        "Stagnation must be suppressed in promotion_proposal once genuine work exists"
    )


@pytest.mark.asyncio
async def test_global_stagnation_fires_in_auto_evidence_only_exempt_phase(
    tmp_path: Path,
) -> None:
    """Fix 5: when the only iterations in the exempt phase are
    ``auto_phase_evidence=True`` fallbacks, stagnation must still fire.
    """
    import json as _json

    store = ResultsStore(str(tmp_path / "ar7_auto_only.sqlite"))
    await store.initialize()
    rid = "res_ar7_auto_only"
    await _seed_session(store, rid, best_iteration=1, best_metric=0.6394)
    await store.update_session(
        rid,
        phase_state_json=_json.dumps({"current_phase": "promotion_proposal"}),
    )

    for i in range(1, 14):
        await store.add_iteration(
            research_id=rid,
            iteration=i,
            primary_metric=0.6394,
            metric_name="composite_direction_score",
            all_gates_passed=True,
            decision="discard",
            description="auto-evidence only",
            config_snapshot=None,
            metrics_json=_json.dumps({"auto_phase_evidence": True}),
            training_time_s=60.0,
            search_phase="promotion_proposal",
        )

    orch = AgentOrchestrator(store)
    result = await orch._maybe_global_stagnation_terminate(
        research_id=rid,
        iteration_count=14,
    )
    assert result is not None
    assert "GLOBAL_STAGNATION" in result


@pytest.mark.asyncio
async def test_global_stagnation_fires_in_non_exempt_phase(
    tmp_path: Path,
) -> None:
    """Phase-aware guard: stagnation MUST still fire in hyperparameter-tuning phases."""
    import json as _json

    store = ResultsStore(str(tmp_path / "ar7_nonexempt.sqlite"))
    await store.initialize()
    rid = "res_ar7_nonexempt"
    await _seed_session(store, rid, best_iteration=1, best_metric=0.6394)
    await store.update_session(
        rid,
        phase_state_json=_json.dumps({"current_phase": "tabular_sweeps"}),
    )

    orch = AgentOrchestrator(store)

    result = await orch._maybe_global_stagnation_terminate(
        research_id=rid,
        iteration_count=13,  # gap=12 >= window
    )
    assert result is not None, (
        "Stagnation must still fire in tabular_sweeps (tuning phase)"
    )
    assert "GLOBAL_STAGNATION" in result
