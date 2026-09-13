from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    class _FakeAsyncAnthropic:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class _FakeAPIStatusError(Exception):
        status_code = 500

    sys.modules["anthropic"] = types.SimpleNamespace(
        AsyncAnthropic=_FakeAsyncAnthropic,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=_FakeAPIStatusError,
    )

from src.core import orchestrator as orchestrator_module  # noqa: E402
from src.core.iteration_context import ITERATION_CONTEXT_DIGEST_MARKER  # noqa: E402
from src.core.llm_provider import (  # noqa: E402
    Message,
    TextBlock,
    ToolResultBlock,
)
from src.core.orchestrator import (  # noqa: E402
    PROMOTION_HANDOFF_INSTRUCTION,
    AgentOrchestrator,
    ResearchConfig,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_FILES = (
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "skills" / "prompt-engineering" / "SKILL.md",
)


def _config(model_type: str, **overrides) -> ResearchConfig:
    values = {
        "id": f"res_{model_type}",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": model_type,
        "tag": "arp006",
        "quick_mode": True,
        "workspace_path": f"/tmp/{model_type}",
    }
    values.update(overrides)
    return ResearchConfig(**values)


def test_prompt_sources_do_not_instruct_direct_promote_py():
    for path in PROMPT_FILES:
        text = path.read_text(encoding="utf-8")

        assert "promote.py" not in text, path

    # The workspace-level agent context carries the server-owned promotion
    # handoff contract explicitly.
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Do not promote directly" in claude_md
    assert "let the server preview/confirm" in claude_md


@pytest.mark.asyncio
async def test_duplicate_training_guard_rejects_same_identity():
    class Store:
        async def find_duplicate_trial_identity(self, **kwargs):
            return {
                "research_id": "res_direction",
                "iteration": 1,
                "trial_identity_hash": kwargs["trial_identity_hash"],
            }

    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._store = Store()
    config = _config("direction")

    rejection, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=4,
        command=(
            ".venv/bin/python scripts/autotuner/direction/prepare.py "
            "--config runs/autotuner/DOGE_USDT_15m/direction/"
            "planned_trials/trial_001/train.yaml --quick"
        ),
        config_snapshot="walkforward_n_folds: 3\n",
        planned_trial={"trial_id": "trial_001"},
    )

    assert rejection.meta["policy_allowed"] is False
    assert rejection.meta["policy_operation"] == "duplicate_attempt.reject"
    assert marker["status"] == "rejected_duplicate"
    assert marker["duplicate_of_iteration"] == 1
    assert marker["trial_identity_hash"] == rejection.meta["trial_identity_hash"]


@pytest.mark.asyncio
async def test_iteration_context_digest_appended_after_recorded_attempt(monkeypatch):
    class Store:
        async def get_session(self, research_id: str):
            return {
                "id": research_id,
                "instrument": "DOGE_USDT",
                "timeframe": "15m",
                "model_type": "direction",
                "max_iterations": 3,
                "max_budget_usd": 1.0,
            }

        async def get_iterations(self, research_id: str):
            return [
                {
                    "iteration": 1,
                    "primary_metric": 0.61,
                    "metric_name": "score",
                    "all_gates_passed": 1,
                    "decision": "keep",
                    "description": "baseline",
                }
            ]

        async def get_hpo_studies(self, research_id: str):
            return []

        async def get_planned_trials(self, research_id: str):
            return []

    monkeypatch.setattr(orchestrator_module.settings, "iteration_context_enabled", True)
    monkeypatch.setattr(orchestrator_module.settings, "iteration_context_max_chars", 6000)
    monkeypatch.setattr(orchestrator_module.settings, "iteration_context_recent_attempts", 5)
    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._store = Store()
    tool_results = [ToolResultBlock(tool_use_id="tool-1", content="ok")]

    await orchestrator._append_iteration_context_digest(
        config=_config("direction"),
        tool_results=tool_results,
        turn_recorded_iteration=True,
        total_cost=0.12,
    )

    assert any(
        isinstance(block, TextBlock)
        and ITERATION_CONTEXT_DIGEST_MARKER in block.text
        for block in tool_results
    )


@pytest.mark.asyncio
async def test_iteration_context_digest_not_appended_without_recorded_attempt(
    monkeypatch,
):
    monkeypatch.setattr(orchestrator_module.settings, "iteration_context_enabled", True)
    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._store = object()
    tool_results = [ToolResultBlock(tool_use_id="tool-1", content="ok")]

    await orchestrator._append_iteration_context_digest(
        config=_config("direction"),
        tool_results=tool_results,
        turn_recorded_iteration=False,
        total_cost=0.12,
    )

    assert len(tool_results) == 1


@pytest.mark.asyncio
async def test_iteration_context_digest_disabled(monkeypatch):
    monkeypatch.setattr(orchestrator_module.settings, "iteration_context_enabled", False)
    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._store = object()
    tool_results = [ToolResultBlock(tool_use_id="tool-1", content="ok")]

    await orchestrator._append_iteration_context_digest(
        config=_config("direction"),
        tool_results=tool_results,
        turn_recorded_iteration=True,
        total_cost=0.12,
    )

    assert len(tool_results) == 1


def test_compaction_retains_latest_iteration_context_digest():
    digest = f"{ITERATION_CONTEXT_DIGEST_MARKER}:\n- Best so far: iteration 2"
    messages: list[Message] = [
        Message(role="user", content="initial"),
        Message(role="assistant", content="old assistant"),
        Message(role="user", content=[TextBlock(text=digest)]),
        Message(role="assistant", content="recent assistant"),
        Message(role="user", content="recent user"),
    ]

    compacted = AgentOrchestrator._compact_messages(messages, keep_recent=2)

    assert len(compacted) == 4
    assert isinstance(compacted[1].content, str)
    assert ITERATION_CONTEXT_DIGEST_MARKER in compacted[1].content
