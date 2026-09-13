"""Tests for duplicate-rejection budget decoupling.

A duplicate-rejected training attempt records an iteration row (for audit
and for the agent's anti-waste context digest), but it must NOT consume the
user-configured iteration budget (`config.max_iterations`). The orchestrator
tracks two counters:

  - `iteration_count`           — total record numbering (real + duplicates)
  - `duplicate_rejected_count`  — duplicates only

The effective iteration count = iteration_count - duplicate_rejected_count.
The budget check, agent-facing status message, phase continuation kick,
stagnation detector, and terminal_reason derivation all use the effective
count.
"""
from __future__ import annotations

import pytest

from src.core.results_store import _LATEST_SCHEMA_VERSION, ResultsStore


def test_latest_schema_version_includes_v4_migration() -> None:
    """v4 introduces effective_iteration_count + terminate_request_* columns."""
    assert _LATEST_SCHEMA_VERSION >= 4


@pytest.mark.asyncio
async def test_session_persists_effective_iteration_count(tmp_path) -> None:
    """update_session(effective_iteration_count=N) round-trips via get_session."""
    store = ResultsStore(tmp_path / "store.db")
    await store.initialize()
    await store.create_session(
        session_id="res_eff",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="effective-count-test",
        workspace_path=str(tmp_path / "ws"),
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )
    await store.update_session("res_eff", effective_iteration_count=5)
    session = await store.get_session("res_eff")
    assert session is not None
    assert session["effective_iteration_count"] == 5


@pytest.mark.asyncio
async def test_session_persists_terminate_request_fields(tmp_path) -> None:
    """update_session round-trips terminate_request_received + body."""
    store = ResultsStore(tmp_path / "store.db")
    await store.initialize()
    await store.create_session(
        session_id="res_term",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="terminate-test",
        workspace_path=str(tmp_path / "ws"),
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )
    await store.update_session(
        "res_term",
        terminate_request_received=1,
        terminate_request_body="TERMINATE_REQUEST: baseline is best",
    )
    session = await store.get_session("res_term")
    assert session is not None
    assert session["terminate_request_received"] == 1
    assert session["terminate_request_body"] == "TERMINATE_REQUEST: baseline is best"


@pytest.mark.asyncio
async def test_effective_iteration_count_defaults_to_zero(tmp_path) -> None:
    """Fresh session has effective_iteration_count = 0."""
    store = ResultsStore(tmp_path / "store.db")
    await store.initialize()
    await store.create_session(
        session_id="res_zero",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="zero-test",
        workspace_path=str(tmp_path / "ws"),
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )
    session = await store.get_session("res_zero")
    assert session is not None
    assert session["effective_iteration_count"] == 0
    assert session["terminate_request_received"] == 0
    assert session.get("terminate_request_body") in (None, "")
