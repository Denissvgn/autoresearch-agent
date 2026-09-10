"""ARC-011 implementation review C2 (2026-08-15) — the manifest-driven runtime
is the production path.

The review found the orchestrator bypassed the materialized ``SkillRuntime``
for everything except ``parse_iteration``: the phase plan came from the
hardcoded ``phases_for_model`` table, the system prompt from the legacy
``_load_skill`` map, command gating from the global ``_ALLOWED_SCRIPTS`` (the
manifest ``command_policy`` section was dead config), the blocker
classification from module constants, and promotion always used the implicit
file target. These tests pin the C2 fixes:

* C2-1  phase plan sourced from the skill runtime (prompt contract +
        ``build_phase_state`` / ``_refresh_phase_state``)
* C2-2  packaged primer for manifest sessions (incl. the manifest-declared
        primer filename)
* C2-3  ``command_policy_extension`` consumed by ``evaluate_command_policy``
        (additive-only)
* C2-4  ``blocker_classification`` consumed (actionable blockers + phase
        evidence keys)
* C2-5  promotion routed through the skill's declared target; unsupported
        kinds skip loudly instead of silently writing a file
* materialization fails loudly for an explicit unknown ``skill_id`` (no
  silent transitional downgrade)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    sys.modules["anthropic"] = types.SimpleNamespace(
        AsyncAnthropic=MagicMock(return_value=MagicMock()),
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

from src.core import config_promoter
from src.core import orchestrator as orchestrator_module
from src.core import skill_registry as skill_registry_module
from src.core.command_policy import evaluate_command_policy
from src.core.orchestrator import AgentOrchestrator, ResearchConfig, _load_packaged_skill_md
from src.core.promotion_target import FilePathPromotionTarget
from src.core.research_phase_plan import build_phase_state, phases_for_model
from src.core.skill_loader import load_skill_manifest
from src.core.skill_registry import SkillRegistry, default_registry
from src.core.skill_runtime import (
    ManifestSkillRuntime,
    SkillConfigError,
    materialize_skill_runtime,
)

SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"


def _manifest(skill_id: str):
    return load_skill_manifest(SKILLS_ROOT / skill_id / "SKILL.yaml")


def _file_path_manifest():
    """A synthetic ``file_path``-promotion manifest (no installed skill uses
    that kind anymore; the runtime must still resolve it)."""
    import yaml

    data = {
        "schema_version": "research_skill.v1",
        "id": "synthetic-file-skill",
        "version": "1.0.0",
        "category": "optimization",
        "display_name": "Synthetic",
        "description": "synthetic file_path skill",
        "llm": {"provider": "anthropic", "primary_model": "m"},
        "workspace": {"session_path_template": "runs/{skill_id}"},
        "variants": {"static": ["v1"]},
        "param_schema": {"type": "object"},
        "metric_schema": {
            "primary": {"field": "m", "label": "M", "direction": "higher_is_better"}
        },
        "decision_vocabulary": {"base": ["keep"]},
        "phase_plan": [{"id": "p1", "min_iterations": 1, "max_iterations": 2}],
        "command_policy": {},
        "output_parser": {"format": "delimited_kv"},
        "preflight": [],
        "promotion_target": {
            "primary": {"kind": "file_path", "path_template": "/tmp/x"}
        },
    }
    return load_skill_manifest(yaml.safe_dump(data))


def _config(**overrides: Any) -> ResearchConfig:
    defaults = dict(
        id="res_c2",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="c2-production-path",
        workspace_path="/tmp/autoresearch",
    )
    defaults.update(overrides)
    return ResearchConfig(**defaults)


# ============================================================================
# C2-1 — phase plan from the skill runtime
# ============================================================================


def test_phase_contract_block_sources_from_manifest_not_constants(monkeypatch):
    """With ``skill_id`` set, the prompt's phase contract renders the
    manifest's phase plan even when the hardcoded per-model table is
    unavailable — proving the runtime (not ``phases_for_model``) is the
    production source."""
    def _no_constants(model_type: str) -> list:
        raise AssertionError(
            "phases_for_model must not be consulted for manifest-driven "
            f"sessions (called with {model_type!r})"
        )

    monkeypatch.setattr(orchestrator_module, "phases_for_model", _no_constants)
    orch = AgentOrchestrator(MagicMock())  # type: ignore[arg-type]

    block = orch._build_phase_contract_block(
        _config(skill_id="prompt-engineering", model_type="prompt-engineering")
    )
    # Rendered from the manifest's own phase ids.
    for phase in _manifest("prompt-engineering").phase_plan:
        assert phase.id in block, f"manifest phase {phase.id!r} missing from contract"

    # The transitional fallback is gone for legacy sessions only: with no
    # skill_id the (patched-to-explode) table would be consulted, so instead
    # prove the branch selection with a returning patch.
    monkeypatch.setattr(
        orchestrator_module, "phases_for_model", lambda mt: [],
    )
    legacy_block = orch._build_phase_contract_block(_config())
    assert legacy_block == ""


def test_skill_phase_plan_none_for_legacy_sessions():
    orch = AgentOrchestrator(MagicMock())  # type: ignore[arg-type]
    assert orch._skill_phase_plan(_config()) is None
    # Manifest sessions get the runtime's plan.
    plan = orch._skill_phase_plan(
        _config(skill_id="prompt-engineering", model_type="prompt-engineering")
    )
    assert plan is not None
    assert [p["id"] for p in plan] == [
        p.id for p in _manifest("prompt-engineering").phase_plan
    ]


def test_build_phase_state_accepts_explicit_phase_override():
    """The ``phases=`` parameter (C2-1) lets callers source the operator-facing
    plan from the runtime; ``None`` keeps the legacy derivation."""
    session = {"model_type": "direction"}
    custom = [
        {"id": "zz_probe_phase", "label": "Probe", "min_iterations": 1,
         "max_iterations": 2, "evidence_keys": (), "next_action": "probe",
         "stagnation_exempt": False},
    ]
    state = build_phase_state(session=session, iterations=[], phases=custom)
    rendered_ids = [p["id"] for p in state["phases"]]
    assert rendered_ids == ["zz_probe_phase"]

    legacy = build_phase_state(session=session, iterations=[])
    assert [p["id"] for p in legacy["phases"]] == [
        p["id"] for p in phases_for_model("direction")
    ]


class _FakePlanStore:
    """Minimal store surface for ``_refresh_phase_state``."""

    def __init__(self, iterations: List[Dict[str, Any]]) -> None:
        self.iterations = iterations
        self.updated: Dict[str, Any] = {}

    async def get_session(self, research_id: str):
        return {"id": research_id, "model_type": "direction"}

    async def get_iterations(self, research_id: str):
        return self.iterations

    async def get_hpo_studies(self, research_id):
        return []

    async def list_promotions(self):
        return []

    async def update_session(self, research_id, **fields):
        self.updated = {"research_id": research_id, **fields}
        return {"id": research_id}


@pytest.mark.asyncio
async def test_refresh_phase_state_uses_session_skill_plan():
    """``_refresh_phase_state`` derives the plan from the bound skill runtime
    (C2-1) — the hardcoded table is only the transitional fallback."""
    store = _FakePlanStore([])
    orch = AgentOrchestrator(store)  # type: ignore[arg-type]

    class _ProbeSkill:
        def phase_plan(self):
            return [
                {"id": "zz_probe_phase", "label": "Probe", "min_iterations": 1,
                 "max_iterations": 2, "evidence_keys": (), "next_action": "x",
                 "stagnation_exempt": False},
            ]

    orch._session_skills["res_c2"] = _ProbeSkill()  # type: ignore[attr-defined]
    await orch._refresh_phase_state("res_c2")

    phase_state = json.loads(store.updated["phase_state_json"])
    assert [p["id"] for p in phase_state["phases"]] == ["zz_probe_phase"]


# ============================================================================
# C2-2 — packaged primer for manifest sessions
# ============================================================================


def test_load_packaged_skill_md_reads_package_primer():
    content = _load_packaged_skill_md("prompt-engineering")
    assert content.strip(), "packaged prompt-engineering primer must be non-empty"
    primer = (SKILLS_ROOT / "prompt-engineering" / "SKILL.md").read_text(encoding="utf-8")
    assert content == primer


def test_load_packaged_skill_md_missing_primer_degrades_to_empty():
    assert _load_packaged_skill_md("no-such-skill") == ""


def test_load_packaged_skill_md_honors_declared_primer_filename(monkeypatch, tmp_path):
    """C2-2: the primer filename comes from the manifest
    (``llm.system_prompt``), not a hardcoded ``SKILL.md``."""
    package = tmp_path / "skills" / "c2-custom-primer"
    package.mkdir(parents=True)
    (package / "PRIMER.md").write_text("custom primer body", encoding="utf-8")
    monkeypatch.setattr(skill_registry_module, "DEFAULT_SKILLS_ROOT", tmp_path / "skills")

    assert _load_packaged_skill_md("c2-custom-primer", "PRIMER.md") == "custom primer body"
    assert _load_packaged_skill_md("c2-custom-primer", "SKILL.md") == ""


def test_manifest_runtime_exposes_declared_primer_filename():
    rt = ManifestSkillRuntime(_manifest("prompt-engineering"), orchestrator=MagicMock())
    assert rt.primer_filename == "SKILL.md"  # declared in llm.system_prompt


# ============================================================================
# C2-3 — command policy extension consumed (additive-only)
# ============================================================================


def test_policy_extension_adds_allowed_script():
    command = ".venv/bin/python skills/prompt-engineering/eval/run.py --workspace /tmp/w"
    base = evaluate_command_policy(command, workspace_root="/tmp/w")
    assert not base.allowed, "unlisted script must be rejected by the base policy"

    extended = evaluate_command_policy(
        command,
        workspace_root="/tmp/w",
        policy_extension={"allowed_scripts": {"skills/prompt-engineering/eval/run.py"}},
    )
    assert extended.allowed
    assert extended.operation == "python:skills/prompt-engineering/eval/run.py"


def test_policy_extension_cannot_widen_executables():
    """Additive-only: the extension unions allow-*sets*; it cannot introduce
    new executables into the python/cp/cat dispatch."""
    decision = evaluate_command_policy(
        "rm -rf /",
        workspace_root="/tmp/w",
        policy_extension={"allowed_executables": {"rm"}},
    )
    assert not decision.allowed


def test_policy_extension_cannot_reallow_rejected_config_target():
    """A base restriction (prepare.py --config must stay inside the session
    workspace) cannot be bypassed via copyable_files widening outside the
    workspace — path confinement is checked independently of the allow-set."""
    decision = evaluate_command_policy(
        ".venv/bin/python scripts/autotuner/direction/prepare.py --config /etc/passwd",
        workspace_root="/tmp/w",
        session_workspace="/tmp/w/session",
        policy_extension={"copyable_files": {"passwd"}},
    )
    assert not decision.allowed


def test_manifest_runtime_policy_extension_carries_manifest_scripts():
    rt = ManifestSkillRuntime(_manifest("prompt-engineering"), orchestrator=MagicMock())
    ext = rt.command_policy_extension()
    assert "eval/run.py" in ext["allowed_scripts"]


# ============================================================================
# C2-4 — blocker classification consumed
# ============================================================================


def test_manifest_runtime_blocker_classification_non_empty():
    rt = ManifestSkillRuntime(_manifest("prompt-engineering"), orchestrator=MagicMock())
    bc = rt.blocker_classification()
    assert bc["actionable_blockers"], "prompt-engineering declares actionable blockers"
    assert "phase_evidence_keys" in bc


class _GenuinenessStore:
    def __init__(self, metrics: Dict[str, Any]) -> None:
        self.iterations = [
            {"iteration": 1, "search_phase": "zz_probe_phase",
             "metrics_json": json.dumps(metrics)},
        ]

    async def get_iterations(self, research_id: str):
        return [dict(row) for row in self.iterations]


class _ProbeBlockerSkill:
    def blocker_classification(self):
        return {
            "actionable_blockers": ["zz_probe_blocker"],
            "phase_evidence_keys": {"zz_probe_phase": ["zz_probe_key"]},
        }


@pytest.mark.asyncio
async def test_phase_advancement_genuine_uses_declared_evidence_keys():
    """C2-4: a manifest-declared phase-evidence key confirms genuine work in a
    phase the module-level ``_PHASE_SPECIFIC_AGENT_KEYS`` table knows nothing
    about."""
    orch = AgentOrchestrator(
        _GenuinenessStore({"auto_phase_evidence": True, "zz_probe_key": 1})  # type: ignore[arg-type]
    )
    orch._session_skills["res_c2"] = _ProbeBlockerSkill()  # type: ignore[attr-defined]
    assert await orch._phase_advancement_is_genuine("res_c2", "zz_probe_phase") is True


@pytest.mark.asyncio
async def test_phase_advancement_not_genuine_without_the_key():
    """Same phase, auto-evidence only, key absent — not genuine (the override
    replaces the table; it does not blanket-approve the phase)."""
    orch = AgentOrchestrator(
        _GenuinenessStore({"auto_phase_evidence": True})  # type: ignore[arg-type]
    )
    orch._session_skills["res_c2"] = _ProbeBlockerSkill()  # type: ignore[attr-defined]
    assert await orch._phase_advancement_is_genuine("res_c2", "zz_probe_phase") is False


# ============================================================================
# C2-5 — promotion routed through the skill's declared target
# ============================================================================


def test_manifest_runtime_file_path_kind_returns_file_target():
    rt = ManifestSkillRuntime(_file_path_manifest(), orchestrator=MagicMock())
    assert isinstance(rt.promotion_target(), FilePathPromotionTarget)


def test_manifest_runtime_registry_api_kind_raises_loudly():
    """prompt-engineering declares ``registry_api`` — the config-promotion
    machinery must refuse to pretend it can handle it."""
    rt = ManifestSkillRuntime(
        _manifest("prompt-engineering"), orchestrator=MagicMock(),
    )
    with pytest.raises(SkillConfigError, match="registry_api"):
        rt.promotion_target()


class _AutoPromoteStore:
    def __init__(self) -> None:
        self.session = {
            "id": "res_c2",
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "model_type": "direction",
            "workspace_path": "/tmp/autoresearch",
            "best_iteration": 4,
            "terminal_reason": "agent_self_terminated",
        }
        self.iterations = [
            {"iteration": 4, "all_gates_passed": True, "decision": "keep",
             "primary_metric": 0.63, "metrics_json": "{}"},
        ]
        self.audit_events: List[Dict[str, Any]] = []

    async def get_session(self, research_id: str):
        return dict(self.session)

    async def get_iterations(self, research_id: str):
        return [dict(row) for row in self.iterations]

    async def get_hpo_studies(self, research_id: str):
        return []

    async def list_promotions(self):
        return []

    async def record_audit_event(self, **kwargs: Any):
        self.audit_events.append(kwargs)
        return kwargs

    async def update_session(self, research_id, **fields):
        return {"id": research_id}


class _FakeAgentLog:
    def __init__(self) -> None:
        self.entries: List[tuple[str, str]] = []

    async def append(self, level: str, message: str) -> None:
        self.entries.append((level, message))


class _RegistryApiSkill:
    def promotion_target(self):
        raise SkillConfigError(
            "skill 'c2-registry' declares promotion_target.kind='registry_api', "
            "which has no wired PromotionTarget implementation"
        )


def _complete_phase_state() -> Dict[str, Any]:
    phases = [
        {**phase, "status": "completed"}
        for phase in phases_for_model("direction")
    ]
    return {
        "schema_version": "autoresearch_phase_state.v1",
        "research_id": "res_c2",
        "model_type": "direction",
        "current_phase": "promotion_proposal",
        "next_action": "test",
        "blocked": False,
        "block_reason": None,
        "phases": phases,
    }


@pytest.mark.asyncio
async def test_auto_promote_skips_loudly_on_unsupported_target(monkeypatch):
    """C2-5: a skill declaring an unwired promotion kind skips auto-promotion
    with an audit trail — it must NOT silently fabricate a file promotion."""
    store = _AutoPromoteStore()
    store.session["phase_state_json"] = json.dumps(_complete_phase_state())

    calls: Dict[str, List[str]] = {"preview": [], "confirm": []}

    class FakePromoter:
        def __init__(self, store_: Any, target: Any = None) -> None:
            pass

        async def preview(self, research_id: str) -> Dict[str, Any]:
            calls["preview"].append(research_id)
            return {"promotion_allowed": True}

        async def confirm(self, research_id: str) -> Dict[str, Any]:
            calls["confirm"].append(research_id)
            return {"status": "promoted"}

    monkeypatch.setattr(config_promoter, "ConfigPromoter", FakePromoter)

    orch = AgentOrchestrator(store)  # type: ignore[arg-type]
    orch._session_skills["res_c2"] = _RegistryApiSkill()  # type: ignore[attr-defined]
    await orch._try_auto_promote("res_c2", _config(), _FakeAgentLog())  # noqa: SLF001

    assert calls["preview"] == []
    assert calls["confirm"] == []
    skip_events = [
        e for e in store.audit_events if e.get("action") == "promotion.auto_skip"
    ]
    assert skip_events, "the unsupported-target skip must be audited"
    metadata = skip_events[-1]["request_metadata"]
    assert metadata["reason"] == "unsupported_promotion_target"
    assert "registry_api" in metadata["collection_errors"]["promotion_target"]


@pytest.mark.asyncio
async def test_auto_promote_transitional_sessions_keep_default_constructor(
    monkeypatch,
):
    """Back-compat: with no bound skill runtime the promoter is constructed
    exactly as before (no target kwarg) — the FakePromoter harness in
    test_auto_promotion_readiness pins this shape too."""
    store = _AutoPromoteStore()
    store.session["phase_state_json"] = json.dumps(_complete_phase_state())

    constructed: List[Dict[str, Any]] = []

    class FakePromoter:
        def __init__(self, store_: Any, target: Any = None) -> None:
            constructed.append({"target": target})

        async def preview(self, research_id: str) -> Dict[str, Any]:
            return {"promotion_allowed": False, "blockers": ["gate"]}

        async def confirm(self, research_id: str) -> Dict[str, Any]:
            return {"status": "promoted"}

    monkeypatch.setattr(config_promoter, "ConfigPromoter", FakePromoter)

    orch = AgentOrchestrator(store)  # type: ignore[arg-type]
    await orch._try_auto_promote("res_c2", _config(), _FakeAgentLog())  # noqa: SLF001

    assert constructed == [{"target": None}]


# ============================================================================
# Materialization — no silent transitional downgrade (review H2/C2)
# ============================================================================


def test_materialize_unknown_explicit_skill_id_raises():
    cfg = _config(skill_id="totally-unknown-skill")
    with pytest.raises(SkillConfigError, match="totally-unknown-skill"):
        materialize_skill_runtime(MagicMock(), cfg)


def test_materialize_canonical_skill_id_returns_manifest_runtime():
    rt = materialize_skill_runtime(
        MagicMock(), _config(skill_id="prompt-engineering", model_type="prompt-engineering")
    )
    assert isinstance(rt, ManifestSkillRuntime)
    assert rt.skill_id == "prompt-engineering"


def test_materialize_legacy_empty_skill_id_raises():
    """Sessions without a skill_id can no longer materialize a runtime —
    every session must name an installed skill."""
    with pytest.raises(SkillConfigError, match="no skill_id"):
        materialize_skill_runtime(MagicMock(), _config())


# ============================================================================
# Registry wiring — the default registry resolves the packaged skills
# ============================================================================


@pytest.mark.parametrize("skill_id", ["prompt-engineering"])
def test_default_registry_resolves_packaged_skills(skill_id):
    """The production registry (the one ``materialize_skill_runtime`` uses)
    resolves the packaged skills — the manifest path is reachable
    without any test-only setup."""
    manifest = default_registry.get(skill_id)
    assert manifest.id == skill_id
