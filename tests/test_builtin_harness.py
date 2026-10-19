"""The built-in harness adapter: conformance, kernel routing, instructions,
cleanup, and provider parity.

The rendered prompts here are product assets under test; they do not
control the implementation agent's repository workflow.
"""
from __future__ import annotations

import pytest

from src.core.builtin_harness import (
    BUILTIN_WORKSPACE_INSTRUCTION_FILE,
    BuiltinHarnessAdapter,
)
from src.core.harness_adapter import HarnessRegistry
from src.core.harness_conformance import run_conformance
from src.core.harness_contract import (
    ATTACH_MODE_CONTINUATION,
    ATTACH_MODE_NATIVE_RESUME,
    CAPABILITY_PAUSE,
    CAPABILITY_RESUME,
    HarnessContractError,
)
from src.core.instruction_assembly import (
    COMMON_RESEARCH_INSTRUCTIONS,
    assemble_instructions,
    harness_tool_instructions,
    render_workspace_instructions,
)
from src.core.research_kernel import run_kernel_lifecycle


def _scripted_attempt_fn():
    script = [
        {"outcome": "completed", "metric": 0.1},
        {"outcome": "completed", "metric": 0.4},
        {"outcome": "completed", "metric": 0.3},
    ]

    def step(context, attempt_index):
        return dict(script[min(attempt_index - 1, len(script) - 1)])

    return step


def test_builtin_adapter_conforms_to_the_harness_contract():
    adapter = BuiltinHarnessAdapter(attempt_fn=_scripted_attempt_fn())
    assert run_conformance(adapter) == []


def test_builtin_adapter_is_selected_explicitly_from_the_registry():
    registry = HarnessRegistry()
    registry.register(BuiltinHarnessAdapter(attempt_fn=_scripted_attempt_fn()))
    adapter = registry.resolve("builtin")
    assert adapter.identity()["name"] == "builtin"
    assert adapter.capabilities() == frozenset(
        {CAPABILITY_PAUSE, CAPABILITY_RESUME}
    )


def test_builtin_adapter_completes_the_kernel_lifecycle():
    adapter = BuiltinHarnessAdapter(attempt_fn=_scripted_attempt_fn())
    outcome = run_kernel_lifecycle(
        adapter,
        session={"max_iterations": 3},
        max_attempts=8,
        candidate_samples=[0.1, 0.4, 0.3],
    )
    assert outcome.completed is True
    assert [a.metric for a in outcome.attempts] == [0.1, 0.4, 0.3]
    assert outcome.budget is not None
    assert outcome.budget.exhausted == ("iterations",)
    assert outcome.promotion is not None


def test_builtin_proposals_route_through_the_kernel():
    adapter = BuiltinHarnessAdapter(attempt_fn=_scripted_attempt_fn())
    decision = adapter.route_proposal(
        {
            "proposal_id": "p1",
            "kind": "attempt_result",
            "target": "run",
            "payload": {"verdict": "improve", "phase_id": "phase-2",
                        "phase_advanced": True},
        },
        metric=0.9,
        best_metric=0.5,
    )
    assert decision.verdict == "improve"
    assert decision.phase_action == "advance"
    assert decision.plan == "continue"
    stopped = adapter.route_proposal(
        {"proposal_id": "p2", "kind": "attempt_result", "target": "run",
         "payload": {"stop_requested": True}},
    )
    assert stopped.plan == "stop"


def test_attach_holds_the_honest_mode():
    adapter = BuiltinHarnessAdapter(attempt_fn=_scripted_attempt_fn())
    native = adapter.attach(
        {"research_id": "res", "mode": ATTACH_MODE_NATIVE_RESUME,
         "origin_harness": "builtin"}
    )
    assert native["mode"] == ATTACH_MODE_NATIVE_RESUME
    adapter.close(native["handle"])
    with pytest.raises(HarnessContractError):
        adapter.attach(
            {"research_id": "res", "mode": ATTACH_MODE_NATIVE_RESUME,
             "origin_harness": "external"}
        )
    continued = adapter.attach(
        {"research_id": "res", "mode": ATTACH_MODE_CONTINUATION,
         "origin_harness": "external"}
    )
    assert continued["mode"] == ATTACH_MODE_CONTINUATION
    adapter.close(continued["handle"])


def test_instruction_snapshot_common_and_harness_are_separate():
    # common research instructions carry no tool or harness coupling
    assert "Tool usage" not in COMMON_RESEARCH_INSTRUCTIONS
    assert "CLAUDE.md" not in COMMON_RESEARCH_INSTRUCTIONS
    # harness tool instructions are provider-neutral prose, not tool blocks
    harness = harness_tool_instructions(
        [("bash", "run one shell command"), ("read_file", "read a file")],
        surface_name="built-in tools",
    )
    assert "Tool usage (built-in tools)" in harness
    assert "`bash` — run one shell command" in harness
    assert "input_schema" not in harness
    assert "content_block" not in harness
    # the assembled prompt is a stable product asset
    assembled = assemble_instructions(harness=harness)
    assert assembled == COMMON_RESEARCH_INSTRUCTIONS + "\n\n" + harness
    assert assembled.startswith("# Research conduct")


def test_workspace_instruction_file_is_rendered_through_the_adapter():
    # the filename is adapter-owned data, never a core dependency
    name, content = render_workspace_instructions(
        filename="AGENTS.md", harness="harness block"
    )
    assert name == "AGENTS.md"
    assert content.startswith("# Research conduct")
    assert content.endswith("harness block")
    default_name, _ = render_workspace_instructions(filename="anything.md")
    assert default_name == "anything.md"
    assert BUILTIN_WORKSPACE_INSTRUCTION_FILE == "CLAUDE.md"


def test_core_reads_whatever_instruction_file_the_adapter_names(
    tmp_path, monkeypatch
):
    from src.core import orchestrator as orch_module
    from src.core.orchestrator import AgentOrchestrator

    monkeypatch.setattr(
        orch_module.settings, "workspace_root", str(tmp_path)
    )
    (tmp_path / "AGENTS.md").write_text("renamed instruction file")
    (tmp_path / "CLAUDE.md").write_text("old convention")
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch._workspace_instruction_filename = "CLAUDE.md"
    assert orch._load_claude_md() == "old convention"
    orch.set_workspace_instruction_filename("AGENTS.md")
    assert orch._load_claude_md() == "renamed instruction file"
    # the built-in adapter sets its own convention when bound
    BuiltinHarnessAdapter(orchestrator=orch)
    assert orch._workspace_instruction_filename == "CLAUDE.md"


class _ClosableProvider:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


def test_repeated_session_release_closes_per_session_state(tmp_path):
    from src.core.orchestrator import AgentOrchestrator
    from src.core.state_store import SQLiteStateStore

    store = SQLiteStateStore(str(tmp_path / "state.db"))
    orch = AgentOrchestrator(store)
    for round_index in range(3):
        for session_index in range(4):
            research_id = f"res{round_index}-{session_index}"
            provider = _ClosableProvider()
            orch._session_providers[research_id] = provider
            orch._session_models[research_id] = "model"
            orch._session_model_roles[research_id] = object()
            orch._stop_flags[research_id] = True
            orch._pause_flags[research_id] = True
            orch._session_skills[research_id] = object()
            orch.release_session(research_id)
            # repeated release is safe
            orch.release_session(research_id)
            assert provider.closed == 1
        assert orch._session_providers == {}
        assert orch._session_models == {}
        assert orch._session_model_roles == {}
        assert orch._stop_flags == {}
        assert orch._pause_flags == {}
        assert orch._session_skills == {}


def test_adapter_behavior_is_provider_parity():
    from src.core.llm_provider import MockProvider, Usage

    providers = [MockProvider(), MockProvider()]

    def make_step(provider):
        def step(context, attempt_index):
            quote = provider.price_quote("mock", Usage(10, 5))
            return {
                "outcome": "completed",
                "metric": quote.money_usd,
                "metrics": {"priced": True},
            }

        return step

    outcomes = []
    for provider in providers:
        adapter = BuiltinHarnessAdapter(attempt_fn=make_step(provider))
        outcome = run_kernel_lifecycle(
            adapter, session={"max_iterations": 2}, max_attempts=4
        )
        outcomes.append(outcome)
    # identical lifecycle results across provider bindings
    assert [a.metric for a in outcomes[0].attempts] == [
        a.metric for a in outcomes[1].attempts
    ]
    assert outcomes[0].budget == outcomes[1].budget
    # the harness contract carries no provider types
    for adapter in (BuiltinHarnessAdapter(),):
        assert "provider" not in adapter.identity()