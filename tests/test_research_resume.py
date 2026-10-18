"""Cross-session research resume: generated at setup, read by prompts.

The resume summarizes prior recorded experiments for the same subject and
variant so sessions build on — rather than repeat — prior work. Generation
runs at session setup (async store access); the sync prompt builders only
read the rendered file.
"""

from __future__ import annotations

import json

import pytest

from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.results_store import ResultsStore


def _config(research_id: str, skill_id: str = "conformance-probe") -> ResearchConfig:
    return ResearchConfig(
        id=research_id,
        instrument="conformance-subject",
        timeframe="default",
        model_type="direction",
        skill_id=skill_id,
        tag="resume",
        max_iterations=3,
        max_budget_usd=1.0,
        workspace_path="/tmp/resume-workspace",
    )


async def _seed_history(store: ResultsStore) -> None:
    for index in (1, 2):
        research_id = f"res_prior_{index}"
        await store.create_session(
            session_id=research_id,
            instrument="conformance-subject",
            timeframe="default",
            model_type="direction",
            tag="prior",
            quick_mode=False,
            max_iterations=3,
            max_budget_usd=1.0,
            focus_hint=None,
            workspace_path="/tmp/resume-workspace",
        )
        await store.add_iteration(
            research_id=research_id,
            iteration=1,
            primary_metric=float(index),
            metric_name="score",
            all_gates_passed=True,
            decision="keep",
            description=None,
            config_snapshot=f"metric: {index}\n",
            metrics_json=json.dumps({"primary_metric": index}),
            training_time_s=0.1,
            canonical_config_hash=f"hash-{index}" * 4,
        )


@pytest.mark.asyncio
async def test_generated_resume_summarizes_prior_experiments(
    tmp_path, monkeypatch,
):
    from src.core import orchestrator as orchestrator_module

    monkeypatch.setattr(
        orchestrator_module.settings, "workspace_root", str(tmp_path),
    )
    store = ResultsStore(str(tmp_path / "resume.sqlite"))
    await store.initialize()
    await _seed_history(store)
    orchestrator = AgentOrchestrator(store)
    config = _config("res_current")
    resume_path = orchestrator._research_resume_path(config)
    await orchestrator._generate_research_resume_file(
        config=config, resume_path=resume_path,
    )
    content = orchestrator._read_research_resume_file(resume_path)
    assert "Prior candidates for this subject and variant" in content
    assert "attempt(s)" in content
    framed = orchestrator._load_research_resume(config)
    assert "Research Resume (prior experiments on this instrument)" in framed
    assert "Prior candidates" in framed


@pytest.mark.asyncio
async def test_resume_is_empty_without_prior_experiments(tmp_path):
    store = ResultsStore(str(tmp_path / "resume.sqlite"))
    await store.initialize()
    orchestrator = AgentOrchestrator(store)
    config = _config("res_first")
    resume_path = str(tmp_path / "research_resume.md")
    await orchestrator._generate_research_resume_file(
        config=config, resume_path=resume_path,
    )
    assert orchestrator._load_research_resume(config) == ""


@pytest.mark.asyncio
async def test_skill_runtime_resume_helpers_resolve(tmp_path):
    from src.core.skill_runtime import materialize_skill_runtime

    store = ResultsStore(str(tmp_path / "resume.sqlite"))
    await store.initialize()
    orchestrator = AgentOrchestrator(store)
    config = _config("res_runtime", skill_id="db-config-tuning")
    skill = materialize_skill_runtime(orchestrator, config)
    assert skill.research_resume_path(config).name == "research_resume.md"
    assert isinstance(skill.generate_research_resume(config, store), str)
