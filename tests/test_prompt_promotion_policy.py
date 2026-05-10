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
from src.core.orchestrator import (  # noqa: E402
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


def test_fresh_resume_falls_back_to_generated_resume(monkeypatch, tmp_path):
    fake_settings = types.SimpleNamespace(
        runs_dir=str(tmp_path / "runs"),
        workspace_root=str(tmp_path),
        db_path=str(tmp_path / "db" / "experiments.db"),
        venv_python=str(tmp_path / ".venv" / "bin" / "python"),
    )
    monkeypatch.setattr(orchestrator_module, "settings", fake_settings)

    def generate(*, config, resume_path):
        path = Path(resume_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Generated resume\n\nBest: iteration 2\n", encoding="utf-8")

    monkeypatch.setattr(
        AgentOrchestrator,
        "_generate_research_resume_file",
        staticmethod(generate),
    )

    orchestrator = object.__new__(AgentOrchestrator)
    block = orchestrator._load_research_resume(_config("direction"))

    assert "Research Resume" in block
    assert "Generated resume" in block


def test_fresh_resume_fallback_failure_does_not_abort(monkeypatch, tmp_path):
    fake_settings = types.SimpleNamespace(
        runs_dir=str(tmp_path / "runs"),
        workspace_root=str(tmp_path),
        db_path=str(tmp_path / "db" / "experiments.db"),
        venv_python=str(tmp_path / ".venv" / "bin" / "python"),
    )
    monkeypatch.setattr(orchestrator_module, "settings", fake_settings)

    def generate(*, config, resume_path):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        AgentOrchestrator,
        "_generate_research_resume_file",
        staticmethod(generate),
    )

    orchestrator = object.__new__(AgentOrchestrator)

    assert orchestrator._load_research_resume(_config("direction")) == ""


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
    tool_results = [{"type": "tool_result", "tool_use_id": "tool-1", "content": "ok"}]

    await orchestrator._append_iteration_context_digest(
        config=_config("direction"),
        tool_results=tool_results,
        turn_recorded_iteration=True,
        total_cost=0.12,
    )

    assert any(
        block.get("type") == "text"
        and ITERATION_CONTEXT_DIGEST_MARKER in block.get("text", "")
        for block in tool_results
    )


@pytest.mark.asyncio
async def test_iteration_context_digest_not_appended_without_recorded_attempt(
    monkeypatch,
):
    monkeypatch.setattr(orchestrator_module.settings, "iteration_context_enabled", True)
    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._store = object()
    tool_results = [{"type": "tool_result", "tool_use_id": "tool-1", "content": "ok"}]

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
    tool_results = [{"type": "tool_result", "tool_use_id": "tool-1", "content": "ok"}]

    await orchestrator._append_iteration_context_digest(
        config=_config("direction"),
        tool_results=tool_results,
        turn_recorded_iteration=True,
        total_cost=0.12,
    )

    assert len(tool_results) == 1


def test_compaction_retains_latest_iteration_context_digest():
    digest = f"{ITERATION_CONTEXT_DIGEST_MARKER}:\n- Best so far: iteration 2"
    messages = [
        {"role": "user", "content": "initial"},
        {"role": "assistant", "content": "old assistant"},
        {"role": "user", "content": [{"type": "text", "text": digest}]},
        {"role": "assistant", "content": "recent assistant"},
        {"role": "user", "content": "recent user"},
    ]

    compacted = AgentOrchestrator._compact_messages(messages, keep_recent=2)

    assert len(compacted) == 4
    assert ITERATION_CONTEXT_DIGEST_MARKER in compacted[1]["content"]
