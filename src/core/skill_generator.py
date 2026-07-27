"""Skill generator (ARC-011 P5-021..026).

Drafts a new skill package (manifest + bootstrap + eval) from a natural-language
description by calling the configured ``LLMProvider`` directly (per the Phase-5
plan decision: a dedicated codegen module, NOT a meta-skill run through the
orchestrator loop). Drafts land in ``skills/_drafts/<id>/`` as ``draft`` status
(P5-010 gating keeps them out of production until promoted via P5-024).

Safety posture (X-004 §7 / R10 / P5-026):

* **Drafts are untrusted code by construction.** They get the strictest plugin
  caps, a mandatory ``--dry-bootstrap`` overlay preview during review (T5), and
  a command-policy over-permissiveness audit (P5-026) that flags dangerous
  patterns (``rm -rf``, shell metacharacters in allowed commands, etc.).
* **The generator is feature-flagged** (P5-025: ``Settings.skill_generator_enabled``,
  default off). Operator-initiated, auth-gated; the agent never reaches it (T4 —
  absent from the ``GovernedCommandRunner`` allow-list).
* **No draft is selectable for production until promoted** (P5-026 AC #1). The
  lifecycle machine (P5-010) enforces this independently.

Design decisions (P1-007 house style):

* **Plain Python string templates** over Jinja (no Jinja in the repo; house
  style is ``str.format`` + Pydantic). The generator emits the same file set a
  hand-authored skill ships.
* **Validate before write.** The emitted manifest is validated against
  ``research_skill.v1`` (P2-001); ``bootstrap.py`` / ``eval_run.py`` are
  ``ast.parse``-linted. A schema-invalid / unparseable draft is rejected and no
  files are written (P5-026 AC #4).
* **Idempotent draft id.** The caller supplies the ``skill_id``; re-generating
  with the same id overwrites the same draft (safe for retry).
* **The LLM is the only external dependency.** No new packages; the generator
  reuses the existing ``LLMProvider`` protocol.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.core.skill_loader import load_skill_manifest
from src.core.skill_manifest import ManifestValidationError
from src.core.skill_registry import DRAFTS_SUBDIR, SkillRegistry

logger = logging.getLogger(__name__)

#: Patterns the command-policy audit flags as over-permissive (P5-026 AC #2).
#: Each is a (regex, severity, reason) tuple. ``severity`` ∈ {"critical","warning"}.
_OVERPERMISSIVE_PATTERNS: list[tuple[str, str, str]] = [
    (r"\brm\s+-rf?\b", "critical", "destructive rm command in allowed policy"),
    (r"\b(?:sudo|chmod|chown)\b", "critical", "privilege-escalation verb in allowed policy"),
    (r";|\|\||&&|\|", "warning", "shell metacharacter in allowed command (command chaining)"),
    (r"\$\(", "warning", "command substitution in allowed command"),
    (r"\brm\s+", "warning", "rm command in allowed policy"),
    (r"\beval\b", "critical", "eval in allowed policy (arbitrary code execution)"),
    (r"/etc/|/root/|/var/", "critical", "absolute system path in allowed policy"),
]


@dataclass(frozen=True)
class CommandPolicyFinding:
    """One over-permissiveness finding from the P5-026 audit."""

    severity: str  # "critical" | "warning"
    pattern: str
    reason: str
    #: The manifest path / field where the finding was triggered.
    location: str


@dataclass(frozen=True)
class GeneratedDraft:
    """A successfully drafted skill package (P5-023).

    ``skill_dir`` is the absolute path under ``skills/_drafts/<id>/``. The draft
    is ``lifecycle_state="draft"`` — not selectable for production until
    promoted (P5-024 / P5-026).
    """

    skill_id: str
    skill_dir: Path
    manifest_yaml: str
    bootstrap_py: str
    eval_run_py: Optional[str]
    skill_md: str
    #: Findings from the command-policy over-permissiveness audit (P5-026).
    policy_findings: list[CommandPolicyFinding] = field(default_factory=list)
    #: Raw LLM output, retained for debugging / audit.
    raw_llm_output: str = ""


class SkillGenerationError(ValueError):
    """Raised when a draft cannot be generated (LLM failure, schema invalid, …)."""


# ---------------------------------------------------------------------------
# Command-policy over-permissiveness audit (P5-026 AC #2)
# ---------------------------------------------------------------------------


def audit_command_policy(manifest_yaml: str) -> list[CommandPolicyFinding]:
    """Scan a generated manifest's ``command_policy`` for over-permissive grants.

    Returns a list of findings (empty ⇒ clean). The reviewer is warned with
    these before promoting (P5-024). A ``critical`` finding does not block the
    draft from being written — it surfaces in review so the operator decides.
    """
    import yaml as _yaml

    findings: list[CommandPolicyFinding] = []
    try:
        data = _yaml.safe_load(manifest_yaml)
    except _yaml.YAMLError:
        return [CommandPolicyFinding("critical", "yaml", "manifest is not valid YAML", "<root>")]
    if not isinstance(data, dict):
        return findings
    policy = data.get("command_policy") or {}
    if not isinstance(policy, dict):
        return findings
    for field_name in (
        "allowed_scripts", "allowed_executables", "allowed_python",
        "copyable_files", "readable_files",
    ):
        entries = policy.get(field_name)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            entry_str = str(entry)
            for pattern, severity, reason in _OVERPERMISSIVE_PATTERNS:
                if re.search(pattern, entry_str):
                    findings.append(
                        CommandPolicyFinding(
                            severity=severity,
                            pattern=pattern,
                            reason=reason,
                            location=f"command_policy.{field_name}: {entry_str!r}",
                        )
                    )
    return findings


# ---------------------------------------------------------------------------
# Prompt + output parsing (P5-022)
# ---------------------------------------------------------------------------


def build_generation_prompt(description: str) -> tuple[str, str]:
    """Build the (system, user) prompt pair for the generator LLM (P5-022).

    Returns a tuple of (system_prompt, user_prompt). The user prompt carries the
    natural-language description + the strict JSON output schema the LLM must
    produce.
    """
    system = (
        "You are a skill-package generator for the autoresearch-agent platform. "
        "Given a natural-language description of a research domain, you produce "
        "a complete skill package: a research_skill.v1 manifest (YAML), a "
        "bootstrap.py (renders the session workspace), an eval/run.py (scores "
        "one iteration), and a SKILL.md primer. Output STRICT JSON only."
    )
    schema = {
        "skill_id": "<kebab-case-id>",
        "manifest_yaml": "<full research_skill.v1 YAML string>",
        "bootstrap_py": "<full bootstrap.py source>",
        "eval_run_py": "<full eval/run.py source, or empty string>",
        "skill_md": "<SKILL.md primer markdown>",
    }
    user = (
        f"Generate a skill package for this research domain:\n\n"
        f"{description}\n\n"
        f"Respond with a single JSON object matching this shape (all values are "
        f"strings; emit valid YAML in manifest_yaml and valid Python in the .py "
        f"fields):\n\n{json.dumps(schema, indent=2)}"
    )
    return system, user


def _extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from ``text`` (tolerates code fences)."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else text
    # Find the first {...} block if not fenced.
    if not fence:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise SkillGenerationError("LLM output contained no JSON object")
        candidate = candidate[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise SkillGenerationError(f"LLM output was not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SkillGenerationError("LLM JSON output was not an object")
    return parsed


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class SkillGenerator:
    """Draft a new skill package from a natural-language description (P5-023).

    Parameters
    ----------
    registry:
        The ``SkillRegistry`` (used to resolve the drafts root).
    drafts_root_override:
        Optional override for the ``skills/_drafts/`` dir (tests).
    """

    def __init__(
        self,
        *,
        registry: Optional[SkillRegistry] = None,
        drafts_root_override: Optional[Path] = None,
    ) -> None:
        self._registry = registry
        self._drafts_root = drafts_root_override

    @property
    def drafts_root(self) -> Path:
        if self._drafts_root is not None:
            return self._drafts_root
        if self._registry is not None:
            return self._registry.drafts_root
        from src.core.skill_registry import DEFAULT_SKILLS_ROOT

        return DEFAULT_SKILLS_ROOT / DRAFTS_SUBDIR

    async def generate(
        self,
        *,
        description: str,
        provider: Any,
        model: str,
        skill_id: Optional[str] = None,
    ) -> GeneratedDraft:
        """Generate a draft skill package (P5-023).

        Calls ``provider.complete(...)`` with the generation prompt, parses the
        JSON output, validates the manifest + lints the Python, writes the draft
        to ``skills/_drafts/<id>/``, and runs the command-policy audit. Raises
        ``SkillGenerationError`` on any failure (no partial files written).
        """
        system, user = build_generation_prompt(description)
        raw = await provider.complete(model=model, prompt=user, system=system, max_tokens=8192)
        if not raw or not raw.strip():
            raise SkillGenerationError("LLM returned empty output")
        parsed = _extract_json(raw)
        skill_id = skill_id or parsed.get("skill_id")
        if not skill_id or not isinstance(skill_id, str):
            raise SkillGenerationError("LLM output missing skill_id")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_id):
            raise SkillGenerationError(
                f"skill_id {skill_id!r} is not kebab-case (a-z, 0-9, hyphens)"
            )
        manifest_yaml = parsed.get("manifest_yaml") or ""
        bootstrap_py = parsed.get("bootstrap_py") or ""
        eval_run_py = parsed.get("eval_run_py") or ""
        skill_md = parsed.get("skill_md") or ""
        if not manifest_yaml or not bootstrap_py:
            raise SkillGenerationError("LLM output missing manifest_yaml or bootstrap_py")
        self._validate_manifest(manifest_yaml)
        self._lint_python(bootstrap_py, "bootstrap.py")
        if eval_run_py:
            self._lint_python(eval_run_py, "eval/run.py")
        findings = audit_command_policy(manifest_yaml)
        draft_dir = self._write_draft(
            skill_id=skill_id,
            manifest_yaml=manifest_yaml,
            bootstrap_py=bootstrap_py,
            eval_run_py=eval_run_py or None,
            skill_md=skill_md,
        )
        return GeneratedDraft(
            skill_id=skill_id,
            skill_dir=draft_dir,
            manifest_yaml=manifest_yaml,
            bootstrap_py=bootstrap_py,
            eval_run_py=eval_run_py or None,
            skill_md=skill_md,
            policy_findings=findings,
            raw_llm_output=raw,
        )

    # ── validation helpers ────────────────────────────────────────────────
    def _validate_manifest(self, manifest_yaml: str) -> None:
        try:
            load_skill_manifest(manifest_yaml)
        except ManifestValidationError as exc:
            raise SkillGenerationError(f"generated manifest failed validation: {exc}") from exc

    def _lint_python(self, source: str, label: str) -> None:
        try:
            ast.parse(source)
        except SyntaxError as exc:
            raise SkillGenerationError(f"generated {label} has a syntax error: {exc}") from exc

    def _write_draft(
        self,
        *,
        skill_id: str,
        manifest_yaml: str,
        bootstrap_py: str,
        eval_run_py: Optional[str],
        skill_md: str,
    ) -> Path:
        draft_dir = self.drafts_root / skill_id
        draft_dir.mkdir(parents=True, exist_ok=True)
        (draft_dir / "SKILL.yaml").write_text(manifest_yaml, encoding="utf-8")
        (draft_dir / "bootstrap.py").write_text(bootstrap_py, encoding="utf-8")
        if skill_md:
            (draft_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
        if eval_run_py:
            eval_dir = draft_dir / "eval"
            eval_dir.mkdir(exist_ok=True)
            (eval_dir / "run.py").write_text(eval_run_py, encoding="utf-8")
        return draft_dir


__all__ = [
    "CommandPolicyFinding",
    "GeneratedDraft",
    "SkillGenerationError",
    "SkillGenerator",
    "audit_command_policy",
    "build_generation_prompt",
]
