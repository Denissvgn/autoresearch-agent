"""AR-2: Tests for structured terminal_reason on the exception path.

Defect D2: when the agent loop crashes with an unhandled exception the
``except Exception`` handler wrote ``status="failed"`` but no
``terminal_reason``, leaving the column NULL in the database.  This
defeats the F9 audit-trail and makes postmortem filtering impossible.

Fix: the handler now writes
  ``terminal_reason = f"error_unrecoverable:{type(exc).__name__}"``
before calling ``update_session``.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub the Anthropic SDK so the test can import orchestrator without a
# real API key, and so the fake Claude client can be injected.
# ---------------------------------------------------------------------------
try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    _fake_anthropic = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = _fake_anthropic

from src.core import orchestrator as orchestrator_module
from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.results_store import ResultsStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(research_id: str, workspace: str) -> ResearchConfig:
    return ResearchConfig(
        id=research_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="prompt-engineering",
        skill_id="prompt-engineering",
        tag="ar2-test",
        max_iterations=1,
        max_budget_usd=100.0,
        workspace_path=workspace,
    )


async def _seed_session(store: ResultsStore, config: ResearchConfig) -> None:
    """Create the session row that ``run()`` expects to already exist."""
    await store.create_session(
        session_id=config.id,
        instrument=config.instrument,
        timeframe=config.timeframe,
        model_type=config.model_type,
        tag=config.tag,
        quick_mode=config.quick_mode,
        max_iterations=config.max_iterations,
        max_budget_usd=config.max_budget_usd,
        focus_hint=config.focus_hint,
        workspace_path=config.workspace_path,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_failure_writes_terminal_reason_error_unrecoverable(
    tmp_path: Path,
) -> None:
    """AR-2 core: crash inside the try block writes terminal_reason.

    We inject a RuntimeError via _call_llm_with_retry so the exception
    propagates to the outer ``except Exception`` handler without touching
    the success path.  After run() returns (without re-raising), the
    session row must have:
      status          = "failed"
      terminal_reason = "error_unrecoverable:RuntimeError"
      error_message   starts with the injected message text
    """
    store = ResultsStore(str(tmp_path / "ar2_test.sqlite"))
    await store.initialize()

    config = _make_config("res_ar2_rte", str(tmp_path / "ws"))
    await _seed_session(store, config)

    orchestrator = AgentOrchestrator(store)

    # Patch the two filesystem loaders that run before the try block.
    with (
        patch.object(orchestrator_module, "_load_packaged_skill_md", return_value="# skill stub"),
        patch.object(
            orchestrator,
            "_load_claude_md_async",
            new=AsyncMock(return_value=""),
        ),
        patch.object(
            orchestrator,
            "_call_llm_with_retry",
            new=AsyncMock(side_effect=RuntimeError("injected failure for AR-2")),
        ),
    ):
        # run() must NOT re-raise — the except handler swallows it.
        await orchestrator.run(config)

    session = await store.get_session(config.id)
    assert session is not None, "session row must exist after run()"
    assert session["status"] == "failed"
    assert session["terminal_reason"] == "error_unrecoverable:RuntimeError"
    assert "injected failure for AR-2" in (session.get("error_message") or "")


@pytest.mark.asyncio
async def test_run_failure_preserves_exc_class_name_for_different_exception_types(
    tmp_path: Path,
) -> None:
    """terminal_reason class suffix must match the actual exception type.

    Uses ValueError to verify the class name is taken from type(exc).__name__,
    not hard-coded to 'RuntimeError'.
    """
    store = ResultsStore(str(tmp_path / "ar2_val.sqlite"))
    await store.initialize()

    config = _make_config("res_ar2_val", str(tmp_path / "ws"))
    await _seed_session(store, config)

    orchestrator = AgentOrchestrator(store)

    with (
        patch.object(orchestrator_module, "_load_packaged_skill_md", return_value=""),
        patch.object(orchestrator, "_load_claude_md_async", new=AsyncMock(return_value="")),
        patch.object(
            orchestrator,
            "_call_llm_with_retry",
            new=AsyncMock(side_effect=ValueError("bad value")),
        ),
    ):
        await orchestrator.run(config)

    session = await store.get_session(config.id)
    assert session["status"] == "failed"
    assert session["terminal_reason"] == "error_unrecoverable:ValueError"


@pytest.mark.asyncio
async def test_cancelled_error_does_not_write_terminal_reason(
    tmp_path: Path,
) -> None:
    """asyncio.CancelledError path must NOT write terminal_reason.

    CancelledError is operator-driven stop, not an unrecoverable error.
    It's handled by a separate except block and re-raised; the session
    status becomes 'stopped', not 'failed', and terminal_reason stays NULL.
    """
    import asyncio

    store = ResultsStore(str(tmp_path / "ar2_cancel.sqlite"))
    await store.initialize()

    config = _make_config("res_ar2_cancel", str(tmp_path / "ws"))
    await _seed_session(store, config)

    orchestrator = AgentOrchestrator(store)

    with (
        patch.object(orchestrator_module, "_load_packaged_skill_md", return_value=""),
        patch.object(orchestrator, "_load_claude_md_async", new=AsyncMock(return_value="")),
        patch.object(
            orchestrator,
            "_call_llm_with_retry",
            new=AsyncMock(side_effect=asyncio.CancelledError()),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await orchestrator.run(config)

    session = await store.get_session(config.id)
    assert session["status"] == "stopped"
    # CancelledError is not a crash — terminal_reason must be absent / NULL.
    assert session.get("terminal_reason") is None


@pytest.mark.asyncio
async def test_run_failure_error_message_truncated_at_2000_chars(
    tmp_path: Path,
) -> None:
    """error_message is truncated to 2000 chars to protect the DB column."""
    store = ResultsStore(str(tmp_path / "ar2_trunc.sqlite"))
    await store.initialize()

    config = _make_config("res_ar2_trunc", str(tmp_path / "ws"))
    await _seed_session(store, config)

    orchestrator = AgentOrchestrator(store)
    long_msg = "x" * 5000

    with (
        patch.object(orchestrator_module, "_load_packaged_skill_md", return_value=""),
        patch.object(orchestrator, "_load_claude_md_async", new=AsyncMock(return_value="")),
        patch.object(
            orchestrator,
            "_call_llm_with_retry",
            new=AsyncMock(side_effect=RuntimeError(long_msg)),
        ),
    ):
        await orchestrator.run(config)

    session = await store.get_session(config.id)
    assert session["terminal_reason"] == "error_unrecoverable:RuntimeError"
    stored_msg = session.get("error_message") or ""
    assert len(stored_msg) <= 2000
