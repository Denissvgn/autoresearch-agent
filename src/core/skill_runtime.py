"""``SkillRuntime`` protocol — the single contract between skill author and
orchestrator (ARC-011 P1-023).

This module introduces the ``SkillRuntime`` protocol: every domain-specific
decision the orchestrator used to make via ``if config.model_type == ...`` is
declared as a method on this protocol. The orchestrator (P1-027) materializes
one ``SkillRuntime`` per session and reaches every domain-specific behavior
through ``skill.<method>()``.

The full method surface is the §7.5 sketch in
``UNIVERSAL_RESEARCH_AGENT_GENERALIZATION_ANALYSIS.md`` (lines 773-849),
materialized here as a Python ``Protocol``. Three transitional implementations
land in P1-024/025/026 (``DirectionSkillRuntime`` / ``VolatilitySkillRuntime`` /
``RLSkillRuntime``) that **delegate to the current hardcoded code** — no
behavior change, just relocation. Phase 2 replaces them with manifest-driven
runtimes built from ``skills/<id>/SKILL.yaml``.

Design decisions baked in here (D1-D3 from the plan):

* **Not ``@runtime_checkable``.** Typing-time contract only — mirrors
  ``LLMProvider`` / ``StateStore`` / ``OutputParser`` / ``PromotionTarget`` /
  ``PreflightCheck``.
* **Value types are ``TypedDict`` aliases over existing dict shapes (D1).**
  ``SessionRecord``, ``IterationRecord``, ``CommandPolicyExtension``, ``Phase``,
  ``AdvancementRule``, ``StructuredHPOPlan``, ``SubjectDescriptor``,
  ``VariantDescriptor`` are typing-only aliases so callers keep treating them as
  plain dicts (byte-identical behavior, zero construction churn). The storage
  layer returns dicts everywhere; a dataclass would force ``.to_dict()`` churn
  across the stack — rejected for a "behavior-identical" phase.
* **``session_nonce`` is accepted but ignored by transitional runtimes (D2).**
  The ``parse_iteration`` signature accepts ``session_nonce: bytes`` for the P4
  anti-forgery work, but no nonce validation exists today. Recorded as an
  AC-deviation (P1-007 house style) in the CHANGELOG and module docstring.
* **``skill_id`` / ``skill_version`` (D3).** ``ResearchConfig`` gains these two
  optional fields (defaults ``""``); transitional runtimes derive them from
  ``config.model_type`` (e.g. ``"direction" → ("direction-autotuner", "1")``).
  No DB schema or API change is required for the transitional shell (the fields
  default to empty); a real schema migration lands when Phase 2 makes manifests
  authoritative.

P1-023 references protocols introduced by the three prerequisite epics:
``OutputParser`` (P1-010), ``PromotionTarget`` (P1-015), ``PreflightCheck``
(P1-019), ``StateStore`` (P1-006). All now exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Protocol,
    TypedDict,
)

if TYPE_CHECKING:
    # Avoid a runtime circular import: orchestrator imports skill_runtime, and
    # ResearchConfig lives in orchestrator. The annotations are typing-only.
    from src.core.orchestrator import ResearchConfig
    from src.core.output_parser import OutputParser
    from src.core.preflight import PreflightCheck
    from src.core.promotion_target import PromotionTarget
    from src.core.state_store import StateStore


# ---------------------------------------------------------------------------
# Value types — TypedDict aliases over existing dict shapes (D1).
# ---------------------------------------------------------------------------


class SessionRecord(TypedDict, total=False):
    """Alias over the session dict ``StateStore.get_session`` returns. Keys
    mirror the ``research_sessions`` row (research_id, instrument, timeframe,
    model_type, tag, status, ...). ``total=False`` — callers read via .get()."""

    research_id: str
    instrument: str
    timeframe: str
    model_type: str
    tag: str
    status: str


class IterationRecord(TypedDict, total=False):
    """Alias over the iteration dict ``StateStore.get_iteration`` returns
    (research_id, iteration, primary_metric, metric_name, decision,
    config_snapshot, metrics_json, ...)."""


class CommandPolicyExtension(TypedDict, total=False):
    """Per-skill extension to the orchestrator's base command policy.

    Today the orchestrator has one global ``_ALLOWED_SCRIPTS`` allow-list
    (``command_policy.py``); the manifest-driven future (P2-023) lets each skill
    declare its own allowed scripts/executables/copyable-files/readable-files.
    The transitional runtimes (P1-024..026) return the model-type-relevant
    subset of the current global allow-list.
    """

    allowed_scripts: list[str]
    allowed_executables: list[str]
    copyable_files: list[str]
    readable_files: list[str]


class Phase(TypedDict, total=False):
    """Alias over the phase dict shape in ``research_phase_plan.py``
    (``DIRECTION_PHASES`` / ``VOLATILITY_PHASES`` / ``FALLBACK_PHASES``):
    ``id``, ``label``, ``next_action``, ``min_iterations``, ``max_iterations``."""

    id: str
    label: str
    next_action: str
    min_iterations: int
    max_iterations: int


class AdvancementRule(TypedDict, total=False):
    """Phase advancement evidence rule. Today advancement keys live in the
    module constant ``research_phase_plan._PHASE_ADVANCEMENT_KEYS`` (a tuple of
    metric-key strings per phase id). The TypedDict wraps that into a per-phase
    descriptor the manifest future can express declaratively."""

    evidence_keys: tuple[str, ...]


class StructuredHPOPlan(TypedDict, total=False):
    """Alias over the HPO plan dict ``structured_hpo.build_structured_hpo_plan``
    returns: ``schema_version``, ``research_id``, ``study_id``, ``model_type``,
    ``instrument``, ``timeframe``, ``enabled``, ``status``, ``created_at``,
    ``max_trials``, ``timeout_s``, ``quick_mode``, ``budget``, ``search_space``,
    ``execution``, ``trials``, ``plan_hash``."""


class SubjectDescriptor(TypedDict, total=False):
    """A research subject a skill can enumerate (e.g. an instrument, a model
    family). No subject/variant domain exists for the ML skills today — the
    transitional runtimes return ``[]`` (greenfield, Phase 2+)."""

    id: str
    label: str


class VariantDescriptor(TypedDict, total=False):
    """A variant under a subject (e.g. a timeframe, a parameterization).
    Greenfield for the ML skills today — transitional runtimes return ``[]``."""

    id: str
    subject_id: str
    label: str


# ---------------------------------------------------------------------------
# The protocol.
# ---------------------------------------------------------------------------


class SkillRuntime(Protocol):
    """Contract every research skill implements (ARC-011 P1-023, §7.5).

    Materialized once per session. All methods are deterministic and
    side-effect-free unless documented otherwise; the orchestrator owns
    persistence, audit, and execution. The three transitional implementations
    (P1-024..026) delegate to the current hardcoded code paths — behavior is
    identical, just relocated out of the orchestrator's ``if config.model_type``
    branches.
    """

    # ── Identity ──────────────────────────────────────────────────
    @property
    def skill_id(self) -> str: ...

    @property
    def skill_version(self) -> str: ...

    # ── Prompt construction ───────────────────────────────────────
    def system_prompt(self) -> str: ...

    def directive_prompt(self, config: "ResearchConfig") -> str: ...

    def resume_prompt(
        self,
        config: "ResearchConfig",
        parent: SessionRecord,
        parent_iterations: list[IterationRecord],
    ) -> str: ...

    # ── Command policy ────────────────────────────────────────────
    def command_policy_extension(self) -> CommandPolicyExtension:
        """Allowed scripts/executables/copyable-files/readable-files that extend
        the orchestrator's base policy."""
        ...

    # ── Iteration detection ───────────────────────────────────────
    def parse_iteration(
        self,
        raw_output: str,
        *,
        session_nonce: Optional[bytes] = None,
        config_snapshot: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Parse experiment output into a structured result.

        Validates ``session_nonce`` to reject forged metrics blocks (P4
        anti-forgery). The transitional runtimes (P1-024..026) **ignore** the
        nonce and delegate to the unchanged ``OutputParser`` impls — no nonce
        validation exists today (D2 deviation).
        """
        ...

    def marker_file_paths(self, config: "ResearchConfig") -> list[Path]:
        """Fallback iteration sources (``last_metrics.txt``, ``results.json``)."""
        ...

    # ── Phase contract ────────────────────────────────────────────
    def phase_plan(self) -> list[Phase]: ...

    def phase_advancement_rule(self, phase_id: str) -> AdvancementRule: ...

    # ── Trial identity (dedup) ────────────────────────────────────
    def trial_identity(
        self,
        config: "ResearchConfig",
        *,
        command: str,
        config_snapshot: Optional[str] = None,
        planned_trial: Optional[dict] = None,
    ) -> dict: ...

    # ── Preflight ─────────────────────────────────────────────────
    def preflight_checks(self) -> list["PreflightCheck"]: ...

    # ── Promotion ─────────────────────────────────────────────────
    def promotion_target(self) -> "PromotionTarget": ...

    # ── Output parsing ────────────────────────────────────────────
    def output_parser(self) -> "OutputParser":
        """The parser for ``---`` delimited prepare.py output."""
        ...

    def iteration_marker_parser(self) -> "OutputParser":
        """The parser for ``ITERATION_RESULT:`` JSON-line markers."""
        ...

    # ── Insights ──────────────────────────────────────────────────
    def insights_prompt(
        self,
        session: SessionRecord,
        iterations: list[IterationRecord],
    ) -> str: ...

    # ── Cross-session memory ──────────────────────────────────────
    def research_resume_path(self, config: "ResearchConfig") -> Path: ...

    def generate_research_resume(
        self,
        config: "ResearchConfig",
        store: "StateStore",
    ) -> str: ...

    # ── Structured HPO (optional) ─────────────────────────────────
    def structured_hpo_plan(
        self,
        config: "ResearchConfig",
    ) -> Optional[StructuredHPOPlan]: ...

    # ── Subjects / variants enumeration ───────────────────────────
    def list_subjects(self) -> list[SubjectDescriptor]: ...

    def list_variants(self, subject_id: str) -> list[VariantDescriptor]: ...


# ---------------------------------------------------------------------------
# Transitional runtimes (P1-024 / P1-025 / P1-026).
#
# Each delegates to the current hardcoded code paths — behavior is identical,
# just relocated out of the orchestrator's ``if config.model_type`` branches.
# They hold a reference to the orchestrator instance (which owns the existing
# private prompt-builder / skill-loader / resume methods) and delegate to
# module-level helpers for the rest (``phases_for_model``, ``_ALLOWED_SCRIPTS``,
# ``build_trial_identity``, ``build_structured_hpo_plan``). Phase 2 replaces
# these with manifest-driven runtimes built from ``skills/<id>/SKILL.yaml``.
# ---------------------------------------------------------------------------

# model_type → (skill_id, skill_version). The skill ids match the on-disk
# skills/<id>/ directory names the orchestrator's _load_skill map already uses
# (orchestrator.py). skill_version is "1" for all three transitional skills.
_SKILL_IDENTITY: dict[str, tuple[str, str]] = {
    "direction": ("direction-autotuner", "1"),
    "volatility": ("volatility-autotuner", "1"),
    "rl": ("rl-autotuner", "1"),
}


class _BaseTransitionalSkillRuntime:
    """Shared delegation logic for the three transitional runtimes.

    Subclasses set ``_model_type``; everything else delegates to the
    orchestrator instance + module-level helpers unchanged.
    """

    _model_type: str

    def __init__(self, orchestrator: Any) -> None:
        self._orch = orchestrator

    # ── Identity ──────────────────────────────────────────────────
    @property
    def skill_id(self) -> str:
        return _SKILL_IDENTITY[self._model_type][0]

    @property
    def skill_version(self) -> str:
        return _SKILL_IDENTITY[self._model_type][1]

    # ── Prompt construction (delegate to orchestrator) ────────────
    def system_prompt(self) -> str:
        # Mirrors orchestrator.run()'s system_prompt assembly: claude.md +
        # skill SKILL.md content. _load_skill maps model_type → skills dir.
        import asyncio

        claude_md = self._orch._load_claude_md()
        skill_content = self._orch._load_skill(self._model_type)
        return f"{claude_md}\n\n---\n\n{skill_content}"

    def directive_prompt(self, config: "ResearchConfig") -> str:
        # Delegates to the orchestrator's existing _build_prompt, which already
        # branches on model_type (RL HPO path, RL enrichment, etc.).
        return self._orch._build_prompt(config)

    def resume_prompt(
        self,
        config: "ResearchConfig",
        parent: SessionRecord,
        parent_iterations: list[IterationRecord],
    ) -> str:
        # _build_resume_prompt is async on the orchestrator; the protocol
        # declares sync here for the typing surface. P1-027 wires the actual
        # call path (which awaits the orchestrator method directly).
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self._orch._build_resume_prompt(config)
        )

    # ── Command policy ────────────────────────────────────────────
    def command_policy_extension(self) -> CommandPolicyExtension:
        # Today the orchestrator has one global _ALLOWED_SCRIPTS allow-list
        # (command_policy.py). The transitional runtime returns the
        # model-type-relevant subset: the shared scripts (setup.py, resume.py)
        # plus the model-specific prepare.py. RL also adds enrich_rl_dataset.py.
        from src.core.command_policy import _ALLOWED_SCRIPTS

        shared = [
            s for s in _ALLOWED_SCRIPTS
            if "prepare.py" not in s and "enrich" not in s
        ]
        model_prepare = f"scripts/autotuner/{self._model_type}/prepare.py"
        scripts = shared + ([model_prepare] if model_prepare in _ALLOWED_SCRIPTS else [])
        if self._model_type == "rl":
            enrich = "scripts/autotuner/enrich_rl_dataset.py"
            if enrich in _ALLOWED_SCRIPTS:
                scripts.append(enrich)
        return {"allowed_scripts": sorted(set(scripts))}

    # ── Iteration detection ───────────────────────────────────────
    def parse_iteration(
        self,
        raw_output: str,
        *,
        session_nonce: Optional[bytes] = None,
        config_snapshot: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        # D2: session_nonce is ignored (no nonce validation exists today).
        # Delegates to the orchestrator's parser instances (P1-013).
        from src.core.output_parser import DelimitedKVParser, JSONMarkerParser

        if "ITERATION_RESULT:" in raw_output:
            return JSONMarkerParser().parse_iteration(
                raw_output, session_nonce=session_nonce
            )
        return DelimitedKVParser().parse(raw_output)

    def marker_file_paths(self, config: "ResearchConfig") -> list[Path]:
        # Mirrors orchestrator._read_marker_file's base_dir derivation.
        import os

        from src.config import settings

        instrument_underscore = config.instrument.replace("-", "_")
        base_dir = os.path.join(
            settings.workspace_root,
            "runs", "autotuner",
            f"{instrument_underscore}_{config.timeframe}",
            config.model_type,
        )
        return [Path(base_dir) / "last_metrics.txt"]

    # ── Phase contract ────────────────────────────────────────────
    def phase_plan(self) -> list[Phase]:
        from src.core.research_phase_plan import phases_for_model

        return phases_for_model(self._model_type)  # type: ignore[return-value]

    def phase_advancement_rule(self, phase_id: str) -> AdvancementRule:
        # _PHASE_ADVANCEMENT_KEYS maps phase_id → tuple of evidence key strings.
        from src.core.research_phase_plan import _PHASE_ADVANCEMENT_KEYS

        return {"evidence_keys": _PHASE_ADVANCEMENT_KEYS.get(phase_id, ())}

    # ── Trial identity (dedup) ────────────────────────────────────
    def trial_identity(
        self,
        config: "ResearchConfig",
        *,
        command: str,
        config_snapshot: Optional[str] = None,
        planned_trial: Optional[dict] = None,
    ) -> dict:
        from src.core.iteration_snapshot import build_trial_identity

        return build_trial_identity(
            instrument=config.instrument,
            timeframe=config.timeframe,
            model_type=config.model_type,
            config_snapshot=config_snapshot,
            command=command,
            marker=planned_trial,
            quick_mode=config.quick_mode,
        )

    # ── Preflight ─────────────────────────────────────────────────
    def preflight_checks(self) -> list["PreflightCheck"]:
        from src.core.preflight import preflight_check_from_target
        from src.core.service_preflight import build_service_preflight_targets

        targets = build_service_preflight_targets(model_type=self._model_type)
        return [preflight_check_from_target(t) for t in targets]

    # ── Promotion ─────────────────────────────────────────────────
    def promotion_target(self) -> "PromotionTarget":
        from src.core.promotion_target import FilePathPromotionTarget

        return FilePathPromotionTarget()

    # ── Output parsing ────────────────────────────────────────────
    def output_parser(self) -> "OutputParser":
        from src.core.output_parser import DelimitedKVParser

        return DelimitedKVParser()

    def iteration_marker_parser(self) -> "OutputParser":
        from src.core.output_parser import JSONMarkerParser

        return JSONMarkerParser()

    # ── Insights (delegate to orchestrator) ───────────────────────
    def insights_prompt(
        self,
        session: SessionRecord,
        iterations: list[IterationRecord],
    ) -> str:
        # The orchestrator's insights-prompt builder is inlined in the
        # completion path; transitional runtime returns an empty prompt (the
        # orchestrator still builds it directly during P1-027 until the logic
        # is fully extracted in a later task). Documented deviation.
        return ""

    # ── Cross-session memory (delegate to orchestrator) ───────────
    def research_resume_path(self, config: "ResearchConfig") -> Path:
        # Mirrors orchestrator._load_research_resume's path derivation.
        import os

        from src.config import settings

        instrument_underscore = config.instrument.replace("-", "_")
        return Path(os.path.join(
            settings.workspace_root,
            "runs", "autotuner",
            f"{instrument_underscore}_{config.timeframe}",
            config.model_type,
            "research_resume.md",
        ))

    def generate_research_resume(
        self,
        config: "ResearchConfig",
        store: "StateStore",
    ) -> str:
        # Delegates to the orchestrator's existing resume generator.
        return self._orch._load_research_resume(config)

    # ── Structured HPO (optional) ─────────────────────────────────
    def structured_hpo_plan(
        self,
        config: "ResearchConfig",
    ) -> Optional[StructuredHPOPlan]:
        if not getattr(config, "enable_hpo", False):
            return None
        from src.core.structured_hpo import build_structured_hpo_plan

        return build_structured_hpo_plan(  # type: ignore[return-value]
            research_id=config.id,
            instrument=config.instrument,
            timeframe=config.timeframe,
            model_type=config.model_type,
            max_iterations=config.max_iterations,
            max_budget_usd=config.max_budget_usd,
            enable_hpo=config.enable_hpo,
            hpo_trials=config.hpo_trials,
            timeout_s=config.timeout_s,
            quick_mode=config.quick_mode,
            trading_mode=config.trading_mode,
            hpo_timesteps=config.hpo_timesteps,
        )

    # ── Subjects / variants enumeration ───────────────────────────
    def list_subjects(self) -> list[SubjectDescriptor]:
        # Greenfield (D1): no subject/variant domain exists for the ML skills
        # today. Returns [] until Phase 2+ introduces manifest-driven subjects.
        return []

    def list_variants(self, subject_id: str) -> list[VariantDescriptor]:
        return []


class DirectionSkillRuntime(_BaseTransitionalSkillRuntime):
    """Transitional runtime for the ``direction`` model type (ARC-011 P1-024).

    Delegates to the current hardcoded direction code paths. Behavior identical.
    """

    _model_type = "direction"


class VolatilitySkillRuntime(_BaseTransitionalSkillRuntime):
    """Transitional runtime for the ``volatility`` model type (ARC-011 P1-025).

    Delegates to the current hardcoded volatility code paths. Behavior identical.
    """

    _model_type = "volatility"


class RLSkillRuntime(_BaseTransitionalSkillRuntime):
    """Transitional runtime for the ``rl`` model type (ARC-011 P1-026).

    Delegates to the current hardcoded RL code paths (including the RL HPO
    workflow and dataset-enrichment step). Behavior identical.
    """

    _model_type = "rl"


# ---------------------------------------------------------------------------
# Manifest-driven runtime (ARC-011 P2-007).
#
# A generic ``ManifestSkillRuntime`` that satisfies the ``SkillRuntime`` protocol
# by reading **everything** from a validated ``ResearchSkillManifest`` (P2-001).
# This replaces the three transitional runtimes (P1-024..026) for skills lifted
# into ``skills/<id>/SKILL.yaml`` (P2-005/009/013).
#
# Data-driven methods (phase_plan, command_policy, parsers, preflight,
# promotion, marker paths, insights) read purely from the manifest.
# Computation-heavy methods (prompts, trial_identity, structured_hpo,
# research-resume) delegate to the same orchestrator helpers the transitional
# runtimes use — parameterized by manifest data — so behavior is byte-identical
# (the X-002 parity golden rule). ``session_nonce`` remains accepted but ignored
# (D2 forward-compat; P4 owns anti-forgery).
#
# Plugin escapes (G1 phase advancement, G2 trial identity) are owned by
# per-skill ``phases.py`` / ``resolve_identity.py`` shims that wrap the existing
# logic (``_completed_phase_ids``, ``build_trial_identity``); full X-004 sandbox
# hardening is a Phase-4 concern.
# ---------------------------------------------------------------------------


class ManifestSkillRuntime:
    """A ``SkillRuntime`` driven entirely by a ``ResearchSkillManifest`` (P2-007).

    Holds a reference to the orchestrator (which owns the prompt-builder,
    skill-loader, resume-generator, and trial-identity helpers) and reaches every
    domain-specific decision through the manifest. ``materialize_skill_runtime``
    constructs this when ``config.skill_id`` resolves in the registry.
    """

    def __init__(self, manifest: Any, orchestrator: Any) -> None:
        self._manifest = manifest
        self._orch = orchestrator
        # Locate the skill package dir (sibling of SKILL.yaml) for file reads.
        from src.core.skill_registry import DEFAULT_SKILLS_ROOT

        self._skill_dir: Path = DEFAULT_SKILLS_ROOT / manifest.id

    # ── Identity ──────────────────────────────────────────────────
    @property
    def skill_id(self) -> str:
        return self._manifest.id

    @property
    def skill_version(self) -> str:
        return self._manifest.version

    # ── Prompt construction ───────────────────────────────────────
    def system_prompt(self) -> str:
        """Assemble the system prompt from the manifest's primer file
        (``llm.system_prompt``, default ``SKILL.md``)."""
        primer_name = self._manifest.llm.system_prompt or "SKILL.md"
        primer_path = self._skill_dir / primer_name
        # Delegates to the orchestrator's claude.md loader + reads the skill
        # primer, mirroring the transitional runtime's assembly exactly.
        claude_md = self._orch._load_claude_md()
        skill_content = primer_path.read_text(encoding="utf-8")
        return f"{claude_md}\n\n---\n\n{skill_content}"

    def directive_prompt(self, config: "ResearchConfig") -> str:
        # Delegates to the orchestrator's existing _build_prompt, which branches
        # on model_type. P2-017 (model_type as a read-only alias of skill_id)
        # keeps this working; a fully declarative prompt builder is a follow-up.
        # The manifest's prompt section (setup/experiment_command) is consumed by
        # _build_prompt via the existing model_type dispatch today.
        return self._orch._build_prompt(config)

    def resume_prompt(
        self,
        config: "ResearchConfig",
        parent: SessionRecord,
        parent_iterations: list[IterationRecord],
    ) -> str:
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self._orch._build_resume_prompt(config)
        )

    # ── Command policy ────────────────────────────────────────────
    def command_policy_extension(self) -> CommandPolicyExtension:
        """Read the allowed scripts/executables/files from the manifest's
        ``command_policy`` section (the model-specific extension to the
        orchestrator's domain-neutral base policy)."""
        cp = self._manifest.command_policy
        ext: CommandPolicyExtension = {}
        if cp.allowed_scripts:
            ext["allowed_scripts"] = sorted(cp.allowed_scripts)
        if cp.allowed_executables:
            ext["allowed_executables"] = sorted(cp.allowed_executables)
        if cp.copyable_files:
            ext["copyable_files"] = sorted(cp.copyable_files)
        if cp.readable_files:
            ext["readable_files"] = sorted(cp.readable_files)
        return ext

    # ── Iteration detection ───────────────────────────────────────
    def parse_iteration(
        self,
        raw_output: str,
        *,
        session_nonce: Optional[bytes] = None,
        config_snapshot: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        # D2: session_nonce ignored. Format selection mirrors the transitional
        # runtime: json_marker when the marker is present, else delimited_kv.
        from src.core.output_parser import DelimitedKVParser, JSONMarkerParser

        marker = self._manifest.output_parser.iteration_marker or "ITERATION_RESULT:"
        if marker in raw_output:
            return JSONMarkerParser().parse_iteration(
                raw_output, session_nonce=session_nonce
            )
        return DelimitedKVParser().parse(raw_output)

    def marker_file_paths(self, config: "ResearchConfig") -> list[Path]:
        """Fallback iteration sources from the manifest's
        ``output_parser.fallback`` section."""
        fb = self._manifest.output_parser.fallback
        if fb is None or not fb.marker_dir_template:
            return []
        # Resolve the template's {workspace_root}/{subject_id_underscore}/
        # {variant} placeholders against the session.
        from src.config import settings

        subject = getattr(config, "subject_id", None) or config.instrument
        variant = getattr(config, "variant", None) or config.timeframe
        base = fb.marker_dir_template.format(
            workspace_root=settings.workspace_root,
            subject_id_underscore=subject.replace("-", "_"),
            subject_id=subject,
            variant=variant,
            skill_id=self._manifest.id,
        )
        paths: list[Path] = []
        if fb.read_marker_file:
            paths.append(Path(base) / fb.read_marker_file)
        if fb.read_results_file:
            paths.append(Path(base) / fb.read_results_file)
        return paths

    # ── Phase contract ────────────────────────────────────────────
    def phase_plan(self) -> list[Phase]:
        """Read the phase list from the manifest's ``phase_plan`` section,
        reproducing the incumbent ``DIRECTION_PHASES`` etc. literals."""
        return [
            {  # type: ignore[return-value]
                "id": p.id,
                "label": p.label,
                "min_iterations": p.min_iterations,
                "max_iterations": p.max_iterations,
                "evidence_keys": tuple(p.evidence_keys),
                "next_action": p.next_action,
                "stagnation_exempt": p.stagnation_exempt,
            }
            for p in self._manifest.phase_plan
        ]

    def phase_advancement_rule(self, phase_id: str) -> AdvancementRule:
        """Read per-phase evidence keys from the manifest. The hybrid completion
        rule (G1) is owned by the phases.py plugin when ``phase_advancement.mode
        == plugin``; this returns the declarative evidence-keys portion only."""
        for p in self._manifest.phase_plan:
            if p.id == phase_id:
                return {"evidence_keys": tuple(p.evidence_keys)}
        return {"evidence_keys": ()}

    # ── Trial identity (dedup) ────────────────────────────────────
    def trial_identity(
        self,
        config: "ResearchConfig",
        *,
        command: str,
        config_snapshot: Optional[str] = None,
        planned_trial: Optional[dict] = None,
    ) -> dict:
        # G2: delegates to build_trial_identity (the existing multi-source
        # synthesis). A resolve_identity.py plugin slot is declared in the
        # manifest but the behavior is byte-identical via the shared helper.
        from src.core.iteration_snapshot import build_trial_identity

        model_type = getattr(config, "model_type", "") or ""
        return build_trial_identity(
            instrument=config.instrument,
            timeframe=config.timeframe,
            model_type=model_type,
            config_snapshot=config_snapshot,
            command=command,
            marker=planned_trial,
            quick_mode=config.quick_mode,
        )

    # ── Preflight ─────────────────────────────────────────────────
    def preflight_checks(self) -> list["PreflightCheck"]:
        """Build preflight checks from the manifest's ``preflight`` section."""
        from src.core.preflight import HTTPHealthCheck, TCPConnectCheck
        from src.core.service_preflight import ServicePreflightTarget

        checks: list["PreflightCheck"] = []
        for entry in self._manifest.preflight:
            if entry.kind == "local_file":
                # local_file checks aren't PreflightCheck instances today
                # (no transport); skip — they are validated elsewhere. P3 UI.
                continue
            health_paths = tuple(entry.health_paths) if entry.health_paths else ("/health",)
            target = ServicePreflightTarget(
                name=entry.name,
                url=entry.url or "",
                health_paths=health_paths,
                required=entry.required,
                transport="tcp" if entry.kind == "tcp" else "http",
            )
            if entry.kind == "tcp":
                checks.append(TCPConnectCheck(target, timeout_s=entry.timeout_s))
            else:
                checks.append(HTTPHealthCheck(target))
        return checks

    # ── Promotion ─────────────────────────────────────────────────
    def promotion_target(self) -> "PromotionTarget":
        """Build the development-scope ``PromotionTarget`` from the manifest's
        ``promotion_target.primary`` (kind=file_path today; registry_api /
        artifact_store / git_branch are forward-compat)."""
        from src.core.promotion_target import FilePathPromotionTarget

        primary = self._manifest.promotion_target.primary
        kind = getattr(primary, "kind", None)
        if kind == "file_path":
            # FilePathPromotionTarget's path derivation is parameterized by the
            # manifest's path_template at the runtime boundary (P3 concern);
            # for Phase 2 the default target reproduces the incumbent paths.
            return FilePathPromotionTarget()
        # Non-file_path kinds stay in ConfigPromoter for Phase 2 (follow-up);
        # the run loop only needs development-scope file promotion from YAML.
        return FilePathPromotionTarget()

    # ── Output parsing ────────────────────────────────────────────
    def output_parser(self) -> "OutputParser":
        from src.core.output_parser import DelimitedKVParser, JSONMarkerParser

        fmt = self._manifest.output_parser.format
        return JSONMarkerParser() if fmt == "json_marker" else DelimitedKVParser()

    def iteration_marker_parser(self) -> "OutputParser":
        from src.core.output_parser import JSONMarkerParser

        return JSONMarkerParser()

    # ── Insights ──────────────────────────────────────────────────
    def insights_prompt(
        self,
        session: SessionRecord,
        iterations: list[IterationRecord],
    ) -> str:
        # G9: read the per-skill insights template; if absent, the orchestrator
        # builds insights inline (same deviation as the transitional runtime).
        cfg = self._manifest.insights
        if cfg is None:
            return ""
        template_path = self._skill_dir / cfg.prompt_template
        if not template_path.is_file():
            return ""
        return template_path.read_text(encoding="utf-8")

    # ── Cross-session memory (delegate to orchestrator) ───────────
    def research_resume_path(self, config: "ResearchConfig") -> Path:
        return self._orch._read_research_resume(config)

    def generate_research_resume(
        self,
        config: "ResearchConfig",
        store: "StateStore",
    ) -> str:
        return self._orch._load_research_resume(config)

    # ── Structured HPO (optional) ─────────────────────────────────
    def structured_hpo_plan(
        self,
        config: "ResearchConfig",
    ) -> Optional[StructuredHPOPlan]:
        if not self._manifest.structured_hpo.enabled:
            return None
        if not getattr(config, "enable_hpo", False):
            return None
        from src.core.structured_hpo import build_structured_hpo_plan

        model_type = getattr(config, "model_type", "") or ""
        return build_structured_hpo_plan(  # type: ignore[return-value]
            research_id=config.id,
            instrument=config.instrument,
            timeframe=config.timeframe,
            model_type=model_type,
            max_iterations=config.max_iterations,
            max_budget_usd=config.max_budget_usd,
            enable_hpo=config.enable_hpo,
            hpo_trials=config.hpo_trials,
            timeout_s=config.timeout_s,
            quick_mode=config.quick_mode,
            trading_mode=config.trading_mode,
            hpo_timesteps=config.hpo_timesteps,
        )

    # ── Subjects / variants enumeration ───────────────────────────
    def list_subjects(self) -> list[SubjectDescriptor]:
        subs = self._manifest.subjects
        if subs is None or subs.static is None:
            return []
        return [{"id": s.id, "label": s.label or s.id} for s in subs.static]

    def list_variants(self, subject_id: str) -> list[VariantDescriptor]:
        var = self._manifest.variants
        if var is None or var.static is None:
            return []
        return [{"id": v, "label": v} for v in var.static]


def materialize_skill_runtime(
    orchestrator: Any,
    config: "ResearchConfig",
) -> SkillRuntime:
    """Build the ``SkillRuntime`` for a session (P1-027 helper, P2-007 update).

    Prefers a manifest-driven ``ManifestSkillRuntime`` when ``config.skill_id``
    resolves in the registry (P2-007); otherwise falls back to the transitional
    runtimes (P1-024..026) keyed by ``config.model_type``. The fallback keeps
    the switchover per-skill and reversible: a skill not yet lifted into
    ``skills/<id>/SKILL.yaml`` keeps working through its transitional runtime.
    """
    # ── P2-007: manifest-driven path ──────────────────────────────────────
    skill_id = config.skill_id
    if skill_id:
        try:
            from src.core.skill_registry import default_registry

            manifest = default_registry.get(skill_id)
        except Exception:  # noqa: BLE001 — registry miss → fall through
            manifest = None
        if manifest is not None:
            return ManifestSkillRuntime(manifest, orchestrator)

    # ── Transitional path (P1-024..026) ───────────────────────────────────
    model_type = config.model_type or _model_type_from_skill_id(config.skill_id)
    cls = {
        "direction": DirectionSkillRuntime,
        "volatility": VolatilitySkillRuntime,
        "rl": RLSkillRuntime,
    }.get(model_type)
    if cls is None:
        raise ValueError(
            f"Unknown model_type/skill_id for SkillRuntime materialization: "
            f"model_type={config.model_type!r} skill_id={config.skill_id!r}"
        )
    return cls(orchestrator)  # type: ignore[return-value]


def _model_type_from_skill_id(skill_id: str) -> str:
    """Reverse-map a skill_id to its model_type (e.g. direction-autotuner → direction)."""
    for mt, (sid, _) in _SKILL_IDENTITY.items():
        if sid == skill_id:
            return mt
    return ""


__all__ = [
    "AdvancementRule",
    "CommandPolicyExtension",
    "DirectionSkillRuntime",
    "IterationRecord",
    "ManifestSkillRuntime",
    "Phase",
    "RLSkillRuntime",
    "SessionRecord",
    "SkillRuntime",
    "StructuredHPOPlan",
    "SubjectDescriptor",
    "VariantDescriptor",
    "VolatilitySkillRuntime",
    "materialize_skill_runtime",
]
