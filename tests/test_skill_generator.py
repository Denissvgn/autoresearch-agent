"""Skill generator tests (ARC-011 P5-021..026).

Covers the dedicated-codegen generator (per the Phase-5 plan decision):

* **P5-022** — the generation prompt shape (system + user + JSON schema).
* **P5-023** — drafts land in ``skills/_drafts/<id>/`` with the full file set.
* **P5-026 AC #1** — a generated draft cannot be selected for production until
  promoted (lifecycle gating — tested via the lifecycle machine).
* **P5-026 AC #2** — the command-policy audit flags over-permissive drafts.
* **P5-026 AC #4** — schema-invalid / unparseable LLM output → no draft + raise.

A stub ``LLMProvider`` makes the tests deterministic (no real LLM call).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.core.skill_generator import (
    CommandPolicyFinding,
    GeneratedDraft,
    SkillGenerationError,
    SkillGenerator,
    audit_command_policy,
    build_generation_prompt,
)
from src.core.skill_lifecycle import (
    SkillLifecycleEvent,
    SkillLifecycleMachine,
    SkillLifecycleState,
    selectable_for,
)

# ---------------------------------------------------------------------------
# Stub LLM provider
# ---------------------------------------------------------------------------


class StubProvider:
    """Deterministic stand-in for ``LLMProvider.complete``."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.last_system: str | None = None
        self.last_prompt: str | None = None

    async def complete(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 8192,
    ) -> str:
        self.last_system = system
        self.last_prompt = prompt
        return self._response


def _valid_draft_payload(*, skill_id: str = "gen-skill") -> dict[str, Any]:
    """A JSON payload the generator accepts (valid manifest + bootstrap)."""
    manifest = {
        "schema_version": "research_skill.v1",
        "id": skill_id,
        "version": "1.0.0",
        "category": "optimization",
        "display_name": "Generated Skill",
        "description": "A generated test skill.",
        "llm": {"provider": "anthropic", "primary_model": "m"},
        "workspace": {"session_path_template": "runs/{skill_id}"},
        "variants": {"static": ["v1"]},
        "param_schema": {"type": "object"},
        "metric_schema": {
            "primary": {"field": "m", "label": "M", "direction": "higher_is_better"}
        },
        "decision_vocabulary": {"base": ["keep"]},
        "phase_plan": [{"id": "p1", "min_iterations": 1, "max_iterations": 2}],
        "command_policy": {"allowed_scripts": ["run.sh"]},
        "output_parser": {"format": "delimited_kv"},
        "preflight": [],
        "promotion_target": {
            "primary": {"kind": "file_path", "path_template": "/tmp/x"}
        },
    }
    import yaml

    return {
        "skill_id": skill_id,
        "manifest_yaml": yaml.safe_dump(manifest),
        "bootstrap_py": "import json, sys\n" 'print(json.dumps({"rendered": []}))\n',
        "eval_run_py": "import sys\n" "sys.exit(0)\n",
        "skill_md": "# Generated Skill\n\nA test primer.\n",
    }


# ---------------------------------------------------------------------------
# P5-022 — prompt shape
# ---------------------------------------------------------------------------


class TestGenerationPrompt:
    def test_prompt_returns_system_and_user(self):
        system, user = build_generation_prompt("tune a database config")
        assert "skill-package generator" in system.lower()
        assert "tune a database config" in user
        assert "JSON" in user

    def test_prompt_includes_schema(self):
        _, user = build_generation_prompt("x")
        assert "manifest_yaml" in user
        assert "bootstrap_py" in user
        assert "eval_run_py" in user


# ---------------------------------------------------------------------------
# P5-023 — draft generation
# ---------------------------------------------------------------------------


class TestGenerateDraft:
    @pytest.mark.asyncio
    async def test_generates_full_draft(self, tmp_path: Path):
        payload = _valid_draft_payload()
        provider = StubProvider(json.dumps(payload))
        gen = SkillGenerator(drafts_root_override=tmp_path / "_drafts")
        draft = await gen.generate(
            description="a test skill", provider=provider, model="claude-3-haiku"
        )
        assert draft.skill_id == "gen-skill"
        assert draft.skill_dir.is_dir()
        assert (draft.skill_dir / "SKILL.yaml").is_file()
        assert (draft.skill_dir / "bootstrap.py").is_file()
        assert (draft.skill_dir / "SKILL.md").is_file()
        assert (draft.skill_dir / "eval" / "run.py").is_file()

    @pytest.mark.asyncio
    async def test_draft_lands_under_drafts_subdir(self, tmp_path: Path):
        payload = _valid_draft_payload()
        provider = StubProvider(json.dumps(payload))
        drafts_root = tmp_path / "_drafts"
        gen = SkillGenerator(drafts_root_override=drafts_root)
        await gen.generate(description="x", provider=provider, model="m")
        assert (drafts_root / "gen-skill" / "SKILL.yaml").is_file()

    @pytest.mark.asyncio
    async def test_explicit_skill_id_overrides_llm(self, tmp_path: Path):
        payload = _valid_draft_payload(skill_id="llm-suggested-id")
        provider = StubProvider(json.dumps(payload))
        gen = SkillGenerator(drafts_root_override=tmp_path / "_drafts")
        draft = await gen.generate(
            description="x", provider=provider, model="m", skill_id="operator-id"
        )
        assert draft.skill_id == "operator-id"
        assert (tmp_path / "_drafts" / "operator-id").is_dir()


# ---------------------------------------------------------------------------
# P5-026 AC #4 — invalid output → no draft + raise
# ---------------------------------------------------------------------------


class TestGenerateFailurePaths:
    @pytest.mark.asyncio
    async def test_empty_output_raises(self, tmp_path: Path):
        provider = StubProvider("")
        gen = SkillGenerator(drafts_root_override=tmp_path / "_drafts")
        with pytest.raises(SkillGenerationError, match="empty"):
            await gen.generate(description="x", provider=provider, model="m")

    @pytest.mark.asyncio
    async def test_non_json_output_raises(self, tmp_path: Path):
        provider = StubProvider("this is not json at all")
        gen = SkillGenerator(drafts_root_override=tmp_path / "_drafts")
        with pytest.raises(SkillGenerationError, match="JSON"):
            await gen.generate(description="x", provider=provider, model="m")

    @pytest.mark.asyncio
    async def test_invalid_manifest_raises_no_files_written(self, tmp_path: Path):
        payload = _valid_draft_payload()
        payload["manifest_yaml"] = "schema_version: bogus\nid: x\n"  # invalid
        provider = StubProvider(json.dumps(payload))
        drafts_root = tmp_path / "_drafts"
        gen = SkillGenerator(drafts_root_override=drafts_root)
        with pytest.raises(SkillGenerationError, match="validation"):
            await gen.generate(description="x", provider=provider, model="m")
        # No files written on failure.
        assert not drafts_root.exists() or not any(drafts_root.iterdir())

    @pytest.mark.asyncio
    async def test_syntax_error_bootstrap_raises(self, tmp_path: Path):
        payload = _valid_draft_payload()
        payload["bootstrap_py"] = "def (:\\n  pass\n"  # syntax error
        provider = StubProvider(json.dumps(payload))
        gen = SkillGenerator(drafts_root_override=tmp_path / "_drafts")
        with pytest.raises(SkillGenerationError, match="syntax"):
            await gen.generate(description="x", provider=provider, model="m")

    @pytest.mark.asyncio
    async def test_bad_skill_id_rejected(self, tmp_path: Path):
        payload = _valid_draft_payload()
        payload["skill_id"] = "Bad ID With Spaces!"
        provider = StubProvider(json.dumps(payload))
        gen = SkillGenerator(drafts_root_override=tmp_path / "_drafts")
        with pytest.raises(SkillGenerationError, match="kebab-case"):
            await gen.generate(description="x", provider=provider, model="m")


# ---------------------------------------------------------------------------
# P5-026 AC #2 — command-policy over-permissiveness audit
# ---------------------------------------------------------------------------


class TestCommandPolicyAudit:
    def test_clean_policy_no_findings(self):
        payload = _valid_draft_payload()
        findings = audit_command_policy(payload["manifest_yaml"])
        assert findings == []

    def test_flags_rm_rf_as_critical(self):
        payload = _valid_draft_payload()
        import yaml

        manifest = yaml.safe_load(payload["manifest_yaml"])
        manifest["command_policy"]["allowed_scripts"] = ["rm -rf /tmp/work"]
        findings = audit_command_policy(yaml.safe_dump(manifest))
        criticals = [f for f in findings if f.severity == "critical"]
        assert any("destructive rm" in f.reason for f in criticals)

    def test_flags_shell_metacharacters_as_warning(self):
        payload = _valid_draft_payload()
        import yaml

        manifest = yaml.safe_load(payload["manifest_yaml"])
        manifest["command_policy"]["allowed_scripts"] = ["run.sh; cat /etc/passwd"]
        findings = audit_command_policy(yaml.safe_dump(manifest))
        warnings = [f for f in findings if f.severity == "warning"]
        assert any("metacharacter" in f.reason for f in warnings)

    def test_flags_eval_as_critical(self):
        payload = _valid_draft_payload()
        import yaml

        manifest = yaml.safe_load(payload["manifest_yaml"])
        manifest["command_policy"]["allowed_executables"] = ["eval $INPUT"]
        findings = audit_command_policy(yaml.safe_dump(manifest))
        criticals = [f for f in findings if f.severity == "critical"]
        assert any("eval" in f.reason for f in criticals)

    @pytest.mark.asyncio
    async def test_findings_attached_to_generated_draft(self, tmp_path: Path):
        """A generated draft with a permissive policy carries the findings so
        the reviewer sees them at promotion time (P5-024)."""
        payload = _valid_draft_payload()
        import yaml

        manifest = yaml.safe_load(payload["manifest_yaml"])
        manifest["command_policy"]["allowed_scripts"] = ["rm -rf /work"]
        payload["manifest_yaml"] = yaml.safe_dump(manifest)
        provider = StubProvider(json.dumps(payload))
        gen = SkillGenerator(drafts_root_override=tmp_path / "_drafts")
        draft = await gen.generate(description="x", provider=provider, model="m")
        assert len(draft.policy_findings) >= 1
        assert any(f.severity == "critical" for f in draft.policy_findings)


# ---------------------------------------------------------------------------
# P5-026 AC #1 — draft cannot be selected for production until promoted
# ---------------------------------------------------------------------------


class TestDraftNotSelectableForProduction:
    """The lifecycle machine (P5-010) enforces this independently of the
    generator — this test pins the end-to-end guarantee."""

    def test_draft_state_not_selectable_for_production(self):
        assert selectable_for(SkillLifecycleState.DRAFT, production=True) is False

    @pytest.mark.asyncio
    async def test_draft_promotion_enables_production(self):
        """A draft that goes through submit_for_review → approve becomes
        production-selectable."""
        machine = SkillLifecycleMachine()
        machine.register("gen-skill", SkillLifecycleState.DRAFT)
        assert selectable_for(machine.get_state("gen-skill"), production=True) is False
        await machine.transition("gen-skill", SkillLifecycleEvent.SUBMIT_FOR_REVIEW)
        await machine.transition("gen-skill", SkillLifecycleEvent.APPROVE)
        assert machine.get_state("gen-skill") is SkillLifecycleState.STABLE
        assert selectable_for(machine.get_state("gen-skill"), production=True) is True
