"""AR-4: Tests for _build_phase_continuation_kick blocked-phase handling.

Defect D5: when the terminal phase (``promotion_proposal``) is in a
``blocked`` state — e.g., because a consistency gate raised
``missing_config_snapshot`` — ``_build_phase_continuation_kick`` emitted the
same generic phase-continuation text with no escalation.  The LLM received
the same nudge 7+ times and spun without progress, burning budget.

Fix: the kick now:
  1. Detects ``state["blocked"] == True`` separately from ``incomplete``.
  2. Counts per-block_reason attempts for each research session via
     ``AgentOrchestrator._blocker_attempt_counters``.
  3. On the first and second attempt: returns ``reason="blocker_remediation"``
     with targeted text naming the active blocker.
  4. On the 3rd (and subsequent) attempts: returns
     ``reason="blocker_unresolved_terminate"`` with text beginning
     ``BLOCKER_PERSISTED:`` to force a ``TERMINATE_REQUEST`` from the LLM.
  5. When every phase is ``completed`` AND ``blocked`` is False: returns
     ``None`` (honours end_turn).
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock

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
        tag="ar4-test",
        max_iterations=100,
        max_budget_usd=50.0,
        workspace_path="/ws",
    )


async def _seed_session(store: ResultsStore, research_id: str) -> None:
    await store.create_session(
        session_id=research_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="ar4-test",
        quick_mode=False,
        max_iterations=100,
        max_budget_usd=50.0,
        focus_hint=None,
        workspace_path="/ws",
    )


def _blocked_terminal_state(block_reason: str = "missing_config_snapshot") -> Dict[str, Any]:
    """A phase state where all non-terminal phases are completed but
    ``promotion_proposal`` (the terminal phase) is blocked by a consistency gate.

    This is the exact scenario from session ``res_a1ba6cbd520f`` (D5).
    """
    return {
        "schema_version": "autoresearch_phase_state.v1",
        "current_phase": "promotion_proposal",
        "next_action": f"Resolve consistency blockers first: {block_reason}",
        "blocked": True,
        "block_reason": block_reason,
        "phases": [
            {"id": "baseline_capture", "status": "completed"},
            {"id": "tabular_sweeps", "status": "completed"},
            {"id": "adaptive_feature_sweeps", "status": "completed"},
            {"id": "tsfm_sweeps", "status": "completed"},
            {"id": "calibration_replay_gates", "status": "completed"},
            {"id": "multi_seed_robustness", "status": "completed"},
            {"id": "inference_parity_replay", "status": "completed"},
            {"id": "promotion_proposal", "status": "blocked"},
        ],
    }


def _all_completed_state() -> Dict[str, Any]:
    """All phases completed, no blocker — phase plan is genuinely done."""
    return {
        "schema_version": "autoresearch_phase_state.v1",
        "current_phase": "promotion_proposal",
        "next_action": "Done.",
        "blocked": False,
        "block_reason": None,
        "phases": [
            {"id": "baseline_capture", "status": "completed"},
            {"id": "tabular_sweeps", "status": "completed"},
            {"id": "adaptive_feature_sweeps", "status": "completed"},
            {"id": "tsfm_sweeps", "status": "completed"},
            {"id": "calibration_replay_gates", "status": "completed"},
            {"id": "multi_seed_robustness", "status": "completed"},
            {"id": "inference_parity_replay", "status": "completed"},
            {"id": "promotion_proposal", "status": "completed"},
        ],
    }


def _incomplete_normal_state() -> Dict[str, Any]:
    """Some phases still pending, no blocker — standard continuation kick."""
    return {
        "schema_version": "autoresearch_phase_state.v1",
        "current_phase": "tabular_sweeps",
        "next_action": "Run more tabular sweep experiments.",
        "blocked": False,
        "block_reason": None,
        "phases": [
            {"id": "baseline_capture", "status": "completed"},
            {"id": "tabular_sweeps", "status": "in_progress"},
            {"id": "adaptive_feature_sweeps", "status": "pending"},
            {"id": "tsfm_sweeps", "status": "pending"},
            {"id": "calibration_replay_gates", "status": "pending"},
            {"id": "multi_seed_robustness", "status": "pending"},
            {"id": "inference_parity_replay", "status": "pending"},
            {"id": "promotion_proposal", "status": "pending"},
        ],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_kick_returns_none_when_all_phases_completed(tmp_path: Path) -> None:
    """When every phase is completed and not blocked, kick returns None."""
    store = ResultsStore(str(tmp_path / "ar4_done.sqlite"))
    await store.initialize()
    rid = "res_ar4_done"
    await _seed_session(store, rid)

    await store.update_session(rid, phase_state_json=json.dumps(_all_completed_state()))

    orch = AgentOrchestrator(store)
    # Monkeypatch _refresh_phase_state so it doesn't overwrite our planted state
    orch._refresh_phase_state = AsyncMock(return_value=None)

    result = await orch._build_phase_continuation_kick(
        research_id=rid,
        iteration_count=20,
        total_cost=5.0,
        config=_make_config(rid),
    )

    assert result is None, "Fully completed plan should return None (honour end_turn)"


@pytest.mark.asyncio
async def test_phase_kick_returns_standard_kick_when_incomplete_not_blocked(
    tmp_path: Path,
) -> None:
    """Non-blocked incomplete phases → standard 'phase_continuation' reason."""
    store = ResultsStore(str(tmp_path / "ar4_normal.sqlite"))
    await store.initialize()
    rid = "res_ar4_normal"
    await _seed_session(store, rid)

    await store.update_session(rid, phase_state_json=json.dumps(_incomplete_normal_state()))

    orch = AgentOrchestrator(store)
    orch._refresh_phase_state = AsyncMock(return_value=None)

    result = await orch._build_phase_continuation_kick(
        research_id=rid,
        iteration_count=5,
        total_cost=1.0,
        config=_make_config(rid),
    )

    assert result is not None, "Incomplete plan should return a kick"
    assert "phase plan incomplete" in result["reason"]
    # Standard kick must NOT claim a blocker
    assert "blocker" not in result["reason"]
    assert "BLOCKER_PERSISTED" not in result["text"]
    assert "[system] You issued an end_turn but the phase plan is incomplete." in result["text"]
    # Must mention the current phase
    assert "tabular_sweeps" in result["text"]


@pytest.mark.asyncio
async def test_phase_kick_returns_blocker_remediation_on_first_attempt(
    tmp_path: Path,
) -> None:
    """AR-4 D5 first attempt: blocked terminal phase → reason='blocker_remediation'.

    The LLM should receive a targeted message naming the blocker reason and
    the current phase, so it can take informed corrective action instead of
    re-running the same failing experiment.
    """
    store = ResultsStore(str(tmp_path / "ar4_blocked1.sqlite"))
    await store.initialize()
    rid = "res_ar4_blocked1"
    await _seed_session(store, rid)

    state = _blocked_terminal_state("missing_config_snapshot")
    await store.update_session(rid, phase_state_json=json.dumps(state))

    orch = AgentOrchestrator(store)
    orch._refresh_phase_state = AsyncMock(return_value=None)

    result = await orch._build_phase_continuation_kick(
        research_id=rid,
        iteration_count=10,
        total_cost=5.0,
        config=_make_config(rid),
    )

    assert result is not None
    assert result["reason"] == "blocker_remediation"
    assert "missing_config_snapshot" in result["text"]
    assert "promotion_proposal" in result["text"]
    assert "BLOCKER_PERSISTED" not in result["text"]
    assert "TERMINATE_REQUEST" in result["text"]  # instructions on how to escape


@pytest.mark.asyncio
async def test_phase_kick_escalates_to_terminate_after_three_blocker_attempts(
    tmp_path: Path,
) -> None:
    """AR-4 D5 escalation: same block_reason after 3 attempts → forced terminate.

    After 3 consecutive kick attempts for the same block_reason, the
    kick must return reason='blocker_unresolved_terminate' and include
    'BLOCKER_PERSISTED:' in the text.  The test uses the SAME orchestrator
    instance across all 3 calls so the counter accumulates correctly.
    """
    store = ResultsStore(str(tmp_path / "ar4_escalate.sqlite"))
    await store.initialize()
    rid = "res_ar4_escalate"
    await _seed_session(store, rid)

    state = _blocked_terminal_state("Consistency gate failed: missing_config_snapshot")
    await store.update_session(rid, phase_state_json=json.dumps(state))

    orch = AgentOrchestrator(store)
    orch._refresh_phase_state = AsyncMock(return_value=None)

    cfg = _make_config(rid)

    # Attempt 1 → remediation
    result1 = await orch._build_phase_continuation_kick(
        research_id=rid, iteration_count=10, total_cost=5.0, config=cfg,
    )
    assert result1 is not None
    assert result1["reason"] == "blocker_remediation"

    # Attempt 2 → still remediation
    result2 = await orch._build_phase_continuation_kick(
        research_id=rid, iteration_count=11, total_cost=6.0, config=cfg,
    )
    assert result2 is not None
    assert result2["reason"] == "blocker_remediation"

    # Attempt 3 → escalate to forced terminate
    result3 = await orch._build_phase_continuation_kick(
        research_id=rid, iteration_count=12, total_cost=7.0, config=cfg,
    )
    assert result3 is not None
    assert result3["reason"] == "blocker_unresolved_terminate"
    assert "BLOCKER_PERSISTED" in result3["text"]
    assert "TERMINATE_REQUEST" in result3["text"]
    # Attempt count must appear in the message
    assert "3" in result3["text"]


@pytest.mark.asyncio
async def test_phase_kick_counter_is_keyed_by_block_reason(tmp_path: Path) -> None:
    """Switching to a different block_reason resets the escalation counter.

    Session starts with block_reason='A' (2 attempts, no escalation), then
    the state changes to block_reason='B'.  The first attempt with reason 'B'
    should still return blocker_remediation, not escalation.
    """
    store = ResultsStore(str(tmp_path / "ar4_keyed.sqlite"))
    await store.initialize()
    rid = "res_ar4_keyed"
    await _seed_session(store, rid)

    state_a = _blocked_terminal_state("blocker_A")
    await store.update_session(rid, phase_state_json=json.dumps(state_a))

    orch = AgentOrchestrator(store)
    orch._refresh_phase_state = AsyncMock(return_value=None)
    cfg = _make_config(rid)

    # Two attempts with reason 'A'
    for _ in range(2):
        r = await orch._build_phase_continuation_kick(
            research_id=rid, iteration_count=5, total_cost=2.0, config=cfg,
        )
        assert r is not None
        assert r["reason"] == "blocker_remediation"

    # Switch to reason 'B' — counter starts fresh
    state_b = _blocked_terminal_state("blocker_B")
    await store.update_session(rid, phase_state_json=json.dumps(state_b))

    result = await orch._build_phase_continuation_kick(
        research_id=rid, iteration_count=6, total_cost=2.5, config=cfg,
    )
    assert result is not None
    assert result["reason"] == "blocker_remediation", (
        "First attempt with a new block_reason should be remediation, not escalation"
    )


@pytest.mark.asyncio
async def test_phase_kick_returns_none_when_budget_exhausted_despite_blocker(
    tmp_path: Path,
) -> None:
    """Even when the phase is blocked, if budget is ≤ $0.10 the kick returns None.

    The orchestrator should not inject text when there is no headroom left —
    the outer loop will exit naturally.
    """
    store = ResultsStore(str(tmp_path / "ar4_budget.sqlite"))
    await store.initialize()
    rid = "res_ar4_budget"
    await _seed_session(store, rid)

    state = _blocked_terminal_state("missing_config_snapshot")
    await store.update_session(rid, phase_state_json=json.dumps(state))

    orch = AgentOrchestrator(store)
    orch._refresh_phase_state = AsyncMock(return_value=None)

    # total_cost = 49.95, budget = 50.0 → remaining = 0.05 ≤ 0.10
    result = await orch._build_phase_continuation_kick(
        research_id=rid,
        iteration_count=10,
        total_cost=49.95,
        config=_make_config(rid),
    )

    assert result is None, "Exhausted budget must return None even when blocked"


@pytest.mark.asyncio
async def test_phase_kick_counter_cleaned_up_in_finally(tmp_path: Path) -> None:
    """_blocker_attempt_counters is cleaned up after a session ends.

    We manually simulate the cleanup that the finally: block performs and
    assert the per-session counter entry is removed.
    """
    store = ResultsStore(str(tmp_path / "ar4_cleanup.sqlite"))
    await store.initialize()
    rid = "res_ar4_cleanup"
    await _seed_session(store, rid)

    state = _blocked_terminal_state("some_blocker")
    await store.update_session(rid, phase_state_json=json.dumps(state))

    orch = AgentOrchestrator(store)
    orch._refresh_phase_state = AsyncMock(return_value=None)
    cfg = _make_config(rid)

    # Trigger the counter
    await orch._build_phase_continuation_kick(
        research_id=rid, iteration_count=5, total_cost=1.0, config=cfg,
    )
    assert rid in orch._blocker_attempt_counters, "Counter should exist mid-session"

    # Simulate finally: cleanup
    orch._blocker_attempt_counters.pop(rid, None)

    assert rid not in orch._blocker_attempt_counters, (
        "Counter must be absent after finally: cleanup"
    )
