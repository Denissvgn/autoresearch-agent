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

from server.core.orchestrator import (  # noqa: E402
    AgentOrchestrator,
    PROMOTION_HANDOFF_INSTRUCTION,
    ResearchConfig,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_FILES = (
    REPO_ROOT / "services" / "autoresearch-agent" / "CLAUDE.md",
    REPO_ROOT / ".github" / "skills" / "direction-autotuner" / "SKILL.md",
    REPO_ROOT / ".github" / "skills" / "volatility-autotuner" / "SKILL.md",
    REPO_ROOT / ".github" / "skills" / "rl-autotuner" / "SKILL.md",
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
        assert "Do not promote directly" in text, path
        assert "let the server preview/confirm" in text, path


def test_fresh_orchestrator_prompts_use_server_owned_setup_mode(monkeypatch):
    orchestrator = object.__new__(AgentOrchestrator)
    monkeypatch.setattr(
        AgentOrchestrator,
        "_load_research_resume",
        lambda self, config: "",
    )

    for model_type in ("direction", "volatility", "rl"):
        prompt = orchestrator._build_prompt(_config(model_type))

        assert PROMOTION_HANDOFF_INSTRUCTION in prompt
        assert f"--models {model_type}" in prompt
        assert "--force" not in prompt

    hpo_prompt = orchestrator._build_prompt(_config("rl", enable_hpo=True))
    assert PROMOTION_HANDOFF_INSTRUCTION in hpo_prompt
    assert "--models rl" in hpo_prompt
    assert "--force" not in hpo_prompt


@pytest.mark.asyncio
async def test_resume_prompt_keeps_promotion_server_owned(monkeypatch):
    class Store:
        async def get_session(self, parent_id: str):
            return {
                "best_iteration": 3,
                "best_metric": 0.42,
                "insights": "Keep wider deadzone.",
            }

        async def get_iterations(self, parent_id: str):
            return []

    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._store = Store()
    monkeypatch.setattr(
        AgentOrchestrator,
        "_load_research_resume",
        lambda self, config: "",
    )

    prompt = await orchestrator._build_resume_prompt(
        _config("direction", resumed_from="res_parent")
    )

    assert PROMOTION_HANDOFF_INSTRUCTION in prompt
    assert "Do NOT run setup.py" in prompt
    assert "--force" not in prompt
