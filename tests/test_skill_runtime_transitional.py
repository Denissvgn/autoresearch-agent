"""Structural / contract tests for the ``SkillRuntime`` protocol (ARC-011
P1-023) and the three transitional runtimes (P1-024..026), plus the P1-027
orchestrator wiring.

Mirrors ``tests/test_state_store.py`` (P1-009), ``tests/test_output_parser.py``
(P1-014), and the other P1-005-style protocol tests: these pin the public
surface of the protocol and guard against signature drift between the protocol
declaration and the three concrete transitional implementations. They are not
behavioral tests — behavior is covered by the existing per-model-type suites
(``test_rl_phase_tracing.py``, ``test_experiment_parser_volatility_phase5.py``,
``test_experiment_parser_seed_trials.py``) and the X-002 parity fixtures, which
gate the "behavior-identical" claim of the transitional shell.
"""

from __future__ import annotations

import inspect
from typing import Protocol

import pytest

from src.core.orchestrator import ResearchConfig
from src.core.skill_runtime import (
    DirectionSkillRuntime,
    RLSkillRuntime,
    SessionRecord,
    SkillRuntime,
    VolatilitySkillRuntime,
    materialize_skill_runtime,
)

# ---------------------------------------------------------------------------
# A minimal fake orchestrator exposing only the delegation surface the
# transitional runtimes call (_load_claude_md, _load_skill, _build_prompt,
# _load_research_resume). The real orchestrator has all of these as private
# methods; the transitional runtimes hold a reference to it.
# ---------------------------------------------------------------------------


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.skill_contents = {
            "direction": "<direction-skill>",
            "volatility": "<volatility-skill>",
            "rl": "<rl-skill>",
        }

    def _load_claude_md(self) -> str:
        return "<claude-md>"

    def _load_skill(self, model_type: str) -> str:
        return self.skill_contents.get(model_type, "<unknown>")

    def _build_prompt(self, config: ResearchConfig) -> str:
        return f"<directive {config.model_type}>"

    def _load_research_resume(self, config: ResearchConfig) -> str:
        return f"<resume {config.id}>"

    async def _build_resume_prompt(self, config: ResearchConfig) -> str:
        return f"<resume-prompt {config.id}>"


def _config(model_type: str = "direction") -> ResearchConfig:
    return ResearchConfig(
        id="res_test",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type=model_type,
    )


# ---------------------------------------------------------------------------
# Protocol surface tests.
# ---------------------------------------------------------------------------


def test_skill_runtime_protocol_is_typing_time_contract():
    """``SkillRuntime`` is a ``Protocol`` and is **not** ``@runtime_checkable``.

    Mirrors the ``LLMProvider`` / ``StateStore`` / ``OutputParser`` /
    ``PromotionTarget`` / ``PreflightCheck`` decisions.
    """
    assert issubclass(SkillRuntime, Protocol)
    assert getattr(SkillRuntime, "_is_runtime_protocol", False) is False


@pytest.mark.parametrize(
    "impl",
    [DirectionSkillRuntime, VolatilitySkillRuntime, RLSkillRuntime],
    ids=["Direction", "Volatility", "RL"],
)
def test_transitional_runtime_satisfies_protocol_surface(impl):
    """Every method declared on ``SkillRuntime`` exists on each transitional
    runtime (the signature-drift guard). ``skill_id`` / ``skill_version`` are
    properties; the rest are methods (none async on the transitional runtimes —
    they delegate synchronously)."""
    proto_attrs = sorted(SkillRuntime.__protocol_attrs__)
    # The full §7.5 surface.
    expected_methods = {
        "command_policy_extension",
        "directive_prompt",
        "generate_research_resume",
        "insights_prompt",
        "iteration_marker_parser",
        "list_subjects",
        "list_variants",
        "marker_file_paths",
        "output_parser",
        "parse_iteration",
        "phase_advancement_rule",
        "phase_plan",
        "preflight_checks",
        "promotion_target",
        "research_resume_path",
        "resume_prompt",
        "skill_id",
        "skill_version",
        "structured_hpo_plan",
        "system_prompt",
        "trial_identity",
    }
    assert set(proto_attrs) == expected_methods, (
        f"unexpected SkillRuntime surface delta: "
        f"missing={expected_methods - set(proto_attrs)} "
        f"extra={set(proto_attrs) - expected_methods}"
    )

    for name in proto_attrs:
        assert hasattr(impl, name), f"{impl.__name__} is missing {name!r}"


def test_minimal_skill_runtime_satisfies_protocol():
    """A minimal stub satisfies the protocol at the type level (structural
    typing — no inheritance required)."""

    class _Stub:
        @property
        def skill_id(self):
            return "x"

        @property
        def skill_version(self):
            return "1"

        def system_prompt(self):
            return ""

        def directive_prompt(self, config):
            return ""

        def resume_prompt(self, config, parent, parent_iterations):
            return ""

        def command_policy_extension(self):
            return {}

        def parse_iteration(self, raw_output, *, session_nonce=None, config_snapshot=None):
            return None

        def marker_file_paths(self, config):
            return []

        def phase_plan(self):
            return []

        def phase_advancement_rule(self, phase_id):
            return {}

        def trial_identity(self, config, *, command, config_snapshot=None, planned_trial=None):
            return {}

        def preflight_checks(self):
            return []

        def promotion_target(self):
            return None

        def output_parser(self):
            return None

        def iteration_marker_parser(self):
            return None

        def insights_prompt(self, session, iterations):
            return ""

        def research_resume_path(self, config):
            return None

        def generate_research_resume(self, config, store):
            return ""

        def structured_hpo_plan(self, config):
            return None

        def list_subjects(self):
            return []

        def list_variants(self, subject_id):
            return []

    for name in SkillRuntime.__protocol_attrs__:
        assert hasattr(_Stub, name)


# ---------------------------------------------------------------------------
# Identity (D3): skill_id / skill_version derived from model_type.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls,model_type,expected_skill_id",
    [
        (DirectionSkillRuntime, "direction", "direction-autotuner"),
        (VolatilitySkillRuntime, "volatility", "volatility-autotuner"),
        (RLSkillRuntime, "rl", "rl-autotuner"),
    ],
)
def test_skill_identity_derived_from_model_type(cls, model_type, expected_skill_id):
    runtime = cls(_FakeOrchestrator())
    assert runtime.skill_id == expected_skill_id
    assert runtime.skill_version == "1"


# ---------------------------------------------------------------------------
# Delegation tests — each method delegates to the existing code path and
# produces the same shape/identity the orchestrator did before.
# ---------------------------------------------------------------------------


def test_system_prompt_assembles_claude_md_and_skill_content():
    """``system_prompt()`` mirrors the orchestrator's run()-time assembly:
    ``{claude_md}\n\n---\n\n{skill_content}``."""
    runtime = DirectionSkillRuntime(_FakeOrchestrator())
    assert runtime.system_prompt() == "<claude-md>\n\n---\n\n<direction-skill>"


def test_directive_prompt_delegates_to_orchestrator_build_prompt():
    runtime = DirectionSkillRuntime(_FakeOrchestrator())
    assert runtime.directive_prompt(_config("direction")) == "<directive direction>"


def test_phase_plan_matches_phases_for_model():
    """``phase_plan()`` returns the same list ``phases_for_model(model_type)``
    returns (the existing module-level selector)."""
    from src.core.research_phase_plan import phases_for_model

    for model_type in ("direction", "volatility", "rl"):
        runtime_cls = {
            "direction": DirectionSkillRuntime,
            "volatility": VolatilitySkillRuntime,
            "rl": RLSkillRuntime,
        }[model_type]
        runtime = runtime_cls(_FakeOrchestrator())
        assert runtime.phase_plan() == phases_for_model(model_type)


def test_phase_advancement_rule_reads_phase_advancement_keys():
    """``phase_advancement_rule`` wraps ``_PHASE_ADVANCEMENT_KEYS[phase_id]``
    into the AdvancementRule TypedDict."""
    from src.core.research_phase_plan import _PHASE_ADVANCEMENT_KEYS

    runtime = DirectionSkillRuntime(_FakeOrchestrator())
    # A phase that has evidence keys in the direction plan.
    rule = runtime.phase_advancement_rule("tabular_sweeps")
    assert rule["evidence_keys"] == _PHASE_ADVANCEMENT_KEYS["tabular_sweeps"]
    # An unknown phase id returns an empty tuple (no KeyError).
    assert runtime.phase_advancement_rule("nope")["evidence_keys"] == ()


def test_command_policy_extension_returns_model_relevant_subset():
    """direction/volatility get setup + resume + their prepare.py; rl also gets
    enrich_rl_dataset.py. All drawn from the global _ALLOWED_SCRIPTS."""
    from src.core.command_policy import _ALLOWED_SCRIPTS

    orch = _FakeOrchestrator()
    direction = DirectionSkillRuntime(orch).command_policy_extension()["allowed_scripts"]
    volatility = VolatilitySkillRuntime(orch).command_policy_extension()["allowed_scripts"]
    rl = RLSkillRuntime(orch).command_policy_extension()["allowed_scripts"]

    assert "scripts/autotuner/direction/prepare.py" in direction
    assert "scripts/autotuner/volatility/prepare.py" in volatility
    assert "scripts/autotuner/rl/prepare.py" in rl
    assert "scripts/autotuner/enrich_rl_dataset.py" in rl
    assert "scripts/autotuner/enrich_rl_dataset.py" not in direction
    # every script returned is in the global allow-list
    for s in direction + volatility + rl:
        assert s in _ALLOWED_SCRIPTS


def test_parse_iteration_routes_kv_block_vs_marker():
    """``parse_iteration`` delegates to DelimitedKVParser for ``---`` blocks and
    JSONMarkerParser for ``ITERATION_RESULT:`` lines (D2: nonce ignored)."""
    runtime = DirectionSkillRuntime(_FakeOrchestrator())

    kv_block = "---\nstatus: completed\nprimary_metric: 0.5\n---\n"
    kv_result = runtime.parse_iteration(kv_block)
    assert kv_result is not None
    assert kv_result["primary_metric"] == 0.5

    marker = 'ITERATION_RESULT: {"iteration": 1, "primary_metric": 0.9}'
    marker_result = runtime.parse_iteration(marker, session_nonce=b"ignored")
    assert marker_result is not None
    assert marker_result["iteration"] == 1


def test_output_parser_and_marker_parser_return_protocol_impls():
    runtime = DirectionSkillRuntime(_FakeOrchestrator())
    from src.core.output_parser import DelimitedKVParser, JSONMarkerParser

    assert isinstance(runtime.output_parser(), DelimitedKVParser)
    assert isinstance(runtime.iteration_marker_parser(), JSONMarkerParser)


def test_promotion_target_returns_filepath_promotion_target():
    runtime = DirectionSkillRuntime(_FakeOrchestrator())
    from src.core.promotion_target import FilePathPromotionTarget

    assert isinstance(runtime.promotion_target(), FilePathPromotionTarget)


def test_structured_hpo_plan_none_when_hpo_disabled():
    runtime = RLSkillRuntime(_FakeOrchestrator())
    cfg = _config("rl")
    cfg.enable_hpo = False
    assert runtime.structured_hpo_plan(cfg) is None


def test_structured_hpo_plan_built_when_hpo_enabled():
    runtime = RLSkillRuntime(_FakeOrchestrator())
    cfg = _config("rl")
    cfg.enable_hpo = True
    plan = runtime.structured_hpo_plan(cfg)
    assert plan is not None
    assert plan["model_type"] == "rl"
    assert plan["enabled"] is True
    assert "plan_hash" in plan


def test_list_subjects_and_variants_are_empty_for_ml_skills():
    """Greenfield (D1): no subject/variant domain exists for the ML skills
    today — transitional runtimes return [] until Phase 2+."""
    runtime = DirectionSkillRuntime(_FakeOrchestrator())
    assert runtime.list_subjects() == []
    assert runtime.list_variants("any") == []


# ---------------------------------------------------------------------------
# materialize_skill_runtime (P1-027 helper).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_type,expected_cls",
    [
        ("direction", DirectionSkillRuntime),
        ("volatility", VolatilitySkillRuntime),
        ("rl", RLSkillRuntime),
    ],
)
def test_materialize_skill_runtime_maps_model_type(model_type, expected_cls):
    orch = _FakeOrchestrator()
    cfg = _config(model_type)
    runtime = materialize_skill_runtime(orch, cfg)
    assert isinstance(runtime, expected_cls)


def test_materialize_skill_runtime_unknown_model_type_raises():
    orch = _FakeOrchestrator()
    cfg = _config("direction")
    cfg.model_type = "unknown"
    with pytest.raises(ValueError):
        materialize_skill_runtime(orch, cfg)


def test_research_config_has_skill_identity_fields():
    """D3: ``ResearchConfig`` gains ``skill_id`` / ``skill_version`` (default
    empty) for the transitional identity derivation."""
    cfg = ResearchConfig(
        id="x", instrument="X", timeframe="1m", model_type="direction"
    )
    assert cfg.skill_id == ""
    assert cfg.skill_version == ""


# ---------------------------------------------------------------------------
# ARC-011 P4-003: hot-path swap parity. The orchestrator now calls
# ``skill.parse_iteration(text, session_nonce=...)`` instead of the bare
# ``parse_iteration_marker`` facade. For the transitional (ML) runtimes,
# D2 documents that session_nonce is ignored — so the result must be identical
# to the facade's, with NO ``metrics_verification`` key (the X-002 parity
# guarantee). A regression here would byte-shift the golden fixtures.
# ---------------------------------------------------------------------------


def test_transitional_parse_iteration_ignores_session_nonce_for_parity():
    """The new hot-path call shape preserves ML parity: passing a session_nonce
    (even a non-None one) does not alter the transitional runtime's result and
    never adds a ``metrics_verification`` key."""
    from src.core.experiment_parser import parse_iteration_marker

    runtime = DirectionSkillRuntime(_FakeOrchestrator())
    marker = (
        'ITERATION_RESULT: {"status":"completed","primary_metric":0.7,'
        '"metric_name":"composite_eval_score"}'
    )
    # The new call shape (orchestrator passes bytes from config.session_nonce).
    nonce_bytes = bytes.fromhex("aabbccdd" * 8)
    result = runtime.parse_iteration(marker, session_nonce=nonce_bytes)
    # The old call shape (the facade the hot path used before the swap).
    facade_result = parse_iteration_marker(marker)

    assert result is not None
    assert result == facade_result, (
        "transitional parse_iteration diverged from the facade — parity broken"
    )
    assert "metrics_verification" not in result, (
        "transitional runtime must not annotate verification (ML is unverified)"
    )


def test_research_config_session_nonce_defaults_empty():
    """P4-002: ``ResearchConfig.session_nonce`` defaults to empty (legacy
    sessions) — the parser's graceful-downgrade path handles this."""
    cfg = ResearchConfig(
        id="x", instrument="X", timeframe="1m", model_type="direction"
    )
    assert cfg.session_nonce == ""
