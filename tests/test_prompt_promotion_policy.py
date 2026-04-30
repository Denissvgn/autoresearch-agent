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

    direction_hpo_prompt = orchestrator._build_prompt(
        _config("direction", enable_hpo=True, hpo_trials=4, max_iterations=3)
    )
    assert "server owns the trial list" in direction_hpo_prompt
    assert "server_hpo_plan.json" in direction_hpo_prompt
    assert "expected commands" in direction_hpo_prompt
    assert "MANUAL_REVIEW_REQUEST" in direction_hpo_prompt
    assert "edit train.yaml" not in direction_hpo_prompt


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


@pytest.mark.asyncio
async def test_structured_hpo_guard_rejects_off_plan_prepare_and_yaml_writes():
    expected_command = (
        ".venv/bin/python scripts/autotuner/direction/prepare.py "
        "--config runs/autotuner/DOGE_USDT_15m/direction/"
        "planned_trials/trial_001/train.yaml --quick"
    )

    class Store:
        def __init__(self) -> None:
            self.manual_reviews = []
            self.audit_events = []

        async def get_planned_trial_for_command(self, research_id: str, command: str):
            if command == expected_command:
                return {"trial_id": "trial_001", "expected_command": command}
            return None

        async def get_hpo_studies(self, research_id: str):
            return [{"study_id": "hpo_res_direction"}]

        async def record_planned_trial_manual_review(self, **kwargs):
            self.manual_reviews.append(kwargs)
            return {"status": "manual_review", **kwargs}

        async def record_audit_event(self, **kwargs):
            self.audit_events.append(kwargs)
            return kwargs

    store = Store()
    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._store = store
    config = _config("direction", enable_hpo=True)

    planned, rejection = await orchestrator._guard_structured_hpo_tool(
        config=config,
        turn=1,
        tool_name="bash",
        input_data={"command": expected_command},
    )
    assert planned["trial_id"] == "trial_001"
    assert rejection is None

    planned, rejection = await orchestrator._guard_structured_hpo_tool(
        config=config,
        turn=2,
        tool_name="bash",
        input_data={
            "command": (
                ".venv/bin/python scripts/autotuner/direction/prepare.py "
                "--config runs/autotuner/DOGE_USDT_15m/direction/train.yaml --quick"
            )
        },
    )
    assert planned is None
    assert rejection.meta["policy_allowed"] is False
    assert rejection.meta["policy_operation"] == "structured_hpo.manual_review"
    assert store.manual_reviews[-1]["reason"].startswith("Structured HPO command")

    planned, rejection = await orchestrator._guard_structured_hpo_tool(
        config=config,
        turn=3,
        tool_name="write_file",
        input_data={"path": "planned_trials/trial_001/train.yaml", "content": "x: 1"},
    )
    assert planned is None
    assert rejection.meta["policy_allowed"] is False
    assert store.manual_reviews[-1]["expected_command"].startswith("write_file:")


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
    config = _config("direction", enable_hpo=True)

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
