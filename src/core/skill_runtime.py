"""``SkillRuntime`` protocol — the single contract between skill author and
orchestrator (ARC-011 P1-023).

This module defines the ``SkillRuntime`` protocol: every domain-specific
decision the orchestrator used to make via ``if config.model_type == ...`` is
declared as a method on this protocol. The orchestrator (P1-027) materializes
one ``SkillRuntime`` per session and reaches every domain-specific behavior
through ``skill.<method>()``.

The only implementation is ``ManifestSkillRuntime``, driven entirely by a
validated ``ResearchSkillManifest`` loaded from ``skills/<id>/SKILL.yaml``.
(The transitional per-model runtimes that delegated to the orchestrator's
hardcoded ML code paths were removed together with the trading skills.)

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
* **``session_nonce`` threading (D2).** ``parse_iteration`` accepts
  ``session_nonce: bytes``; manifest runtimes enforce the echoed-nonce contract
  when the skill declares ``output_parser.require_signed_metrics``.

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
    cast,
)

from src.core.fs_safety import sha256_regular_file as _sha256_file

if TYPE_CHECKING:
    # Avoid a runtime circular import: orchestrator imports skill_runtime, and
    # ResearchConfig lives in orchestrator. The annotations are typing-only.
    from src.core.orchestrator import ResearchConfig
    from src.core.output_parser import OutputParser
    from src.core.preflight import PreflightCheck
    from src.core.promotion_target import PromotionTarget
    from src.core.state_store import StateStore


class SkillConfigError(ValueError):
    """A skill manifest declares something the runtime cannot honor.

    ARC-011 review C2 (2026-08-15): raised when the manifest-driven runtime
    hits a declaration with no wired implementation (e.g.
    ``promotion_target.kind=registry_api`` on the config-promotion path) —
    surfacing the deployment error loudly instead of silently downgrading
    to a default behavior. ``ValueError`` base matches the
    ``ManifestValidationError`` convention in ``skill_manifest.py``.
    """


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

    ``script_paths`` (ARC-011 review C4): declared-name → absolute packaged-
    path resolution. Skill manifests declare scripts workspace-relative
    (``eval/run.py``); the runtime resolves each to the read-only packaged
    ``skills/<id>/`` tree so the governed command can execute it (the
    session workspace is deliberately NOT used — it is agent-writable).
    """

    allowed_scripts: list[str]
    allowed_executables: list[str]
    copyable_files: list[str]
    readable_files: list[str]
    #: Evaluation-data filenames the candidate must never overwrite (staged
    #: eval sets, protected test files). Enforced by the shared file-tool
    #: authorization on every candidate write.
    write_protected_files: list[str]
    script_paths: dict[str, str]
    #: Declared-name → sha256 digest of the pinned packaged script. Computed
    #: at load; re-verified before every launch so pinned content that is
    #: missing or changed fails the command instead of running.
    script_digests: dict[str, str]
    #: ARC-012 P7-011: the CLI flag carrying the skill's per-iteration config
    #: artifact (default ``--config`` when absent).
    config_flag: str


class Phase(TypedDict, total=False):
    """Alias over the phase dict shape in ``research_phase_plan.py``
    (``DIRECTION_PHASES`` / ``VOLATILITY_PHASES`` / ``FALLBACK_PHASES``):
    ``id``, ``label``, ``next_action``, ``min_iterations``, ``max_iterations``."""

    id: str
    label: str
    next_action: str
    min_iterations: int
    max_iterations: int
    evidence_keys: tuple[str, ...]
    stagnation_exempt: bool


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

    def evaluator_command_params(self, config: "ResearchConfig") -> dict[str, str]:
        """Server-owned evaluator flags for execution-boundary enforcement."""
        ...

    def experiment_command(self, config: "ResearchConfig") -> str:
        """Session-resolved suggested experiment command."""
        ...

    def demo_experiment_command(self, config: "ResearchConfig") -> str:
        """The command the demo provider (MockProvider) executes verbatim in
        demo sessions (ARC-012 P7-011). Rendered from the skill's declared
        ``prompt.demo_experiment_command`` with absolute session-workspace
        paths; empty when the skill declares none."""
        ...

    def iteration_marker_prefix(self) -> str:
        """The ``output_parser.iteration_marker`` prefix (default
        ``ITERATION_RESULT:``) — how this skill's evaluator announces a
        result on stdout."""
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

    def blocker_classification(self) -> dict[str, Any]:
        """G3: per-skill blocker-classification overrides (ARC-011 review
        C2-4). Returns ``{"actionable_blockers": [...],
        "phase_evidence_keys": {phase: [...]}}``; an **empty dict** means
        "no override — use the orchestrator's module-level defaults"
        (``_AGENT_ACTIONABLE_BLOCKERS`` / ``_PHASE_SPECIFIC_AGENT_KEYS``)."""
        ...

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

    # ── Execution (P1-4) ───────────────────────────────────────────
    def execution_concurrency(self) -> int:
        """Max independent trial commands the loop may run in parallel."""
        ...

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
    def manifest(self) -> Any:
        """The validated ``ResearchSkillManifest`` (P2 multi-seed significance
        reads ``metric_schema`` declarative sections from it)."""
        return self._manifest

    @property
    def skill_version(self) -> str:
        return self._manifest.version

    @property
    def primer_filename(self) -> str:
        """The manifest-declared system-prompt primer file
        (``llm.system_prompt``, default ``SKILL.md``) — consumed by the
        orchestrator's packaged-primer read (ARC-011 review C2-2) so a skill
        can ship its primer under a different filename."""
        return self._manifest.llm.system_prompt or "SKILL.md"

    @property
    def requires_signed_metrics(self) -> bool:
        """W11 enforcement flag (``output_parser.require_signed_metrics``).
        Consumed by the orchestrator (ARC-011 review C3) to gate both the
        nonce delivery env and the KV-block verification path."""
        return bool(self._manifest.output_parser.require_signed_metrics)

    @property
    def nonce_field(self) -> str:
        """The echoed-nonce field name (``output_parser.nonce_field``,
        default ``server_nonce``) — the field `_verify_nonce` checks."""
        return self._manifest.output_parser.nonce_field or "server_nonce"

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

    def blocker_classification(self) -> dict[str, Any]:
        """G3: the manifest's ``blocker_classification`` section (ARC-011
        review C2 — consumed by the orchestrator's promotion-readiness
        advisory). An empty dict means "no override — use the module-level
        defaults" (``_AGENT_ACTIONABLE_BLOCKERS``)."""
        bc = getattr(self._manifest, "blocker_classification", None)
        if bc is None:
            return {}
        return {
            "actionable_blockers": list(bc.actionable_blockers),
            "phase_evidence_keys": {
                key: list(values)
                for key, values in bc.phase_evidence_keys.items()
            },
        }

    def evaluator_command_params(self, config: "ResearchConfig") -> dict[str, str]:
        """Server-owned argv values; execution must override agent-supplied flags.

        This is also used to render the suggested command, but prompt text alone
        is NOT enforcement. No provider credential is exposed to the child.
        """
        if self.skill_id != "prompt-engineering":
            return {}
        from urllib.parse import urlsplit

        from src.config import settings

        params = getattr(config, "skill_params", None) or {}
        scorer = params.get("scorer_url", "")
        if not isinstance(scorer, str):
            raise SkillConfigError("scorer_url must be a string")
        if scorer:
            url = urlsplit(scorer)
            if (url.scheme not in {"http", "https"} or not url.hostname
                    or url.username or url.password or url.fragment
                    or any(c.isspace() or ord(c) < 32 for c in scorer)):
                raise SkillConfigError("scorer_url must be an HTTP(S) endpoint without credentials")
        demo = settings.demo_mode is True and str(settings.environment).lower() != "production"
        return {"--eval": "eval_set.jsonl", "--scorer-url": scorer,
                "--demo": "true" if demo else "false"}

    def experiment_command(self, config: "ResearchConfig") -> str:
        """Resolve the manifest command with explicit session evaluator wiring."""
        import shlex

        prompt = self._manifest.prompt
        command = (prompt.experiment_command if prompt is not None else None) or ""
        params = self.evaluator_command_params(config)
        if params:
            # Fixed packaged entrypoint; never copy or invoke workspace code.
            command = ".venv/bin/python eval/run.py --prompt prompt.yaml"
            for flag, value in params.items():
                command += " " + flag + " " + shlex.quote(value)
        return command.strip()

    def demo_experiment_command(self, config: "ResearchConfig") -> str:
        """Render ``prompt.demo_experiment_command`` for this session
        (ARC-012 P7-011).

        The template's ``{session_workspace}`` becomes the session's absolute
        workspace path (governed commands run with cwd = the workspace root,
        so workspace-relative file arguments would miss); the identity
        placeholders mirror the D4 path-template vocabulary. A skill that
        declares no demo command renders "" — the demo provider then keeps
        its default behaviour (no session-specific eval).
        """
        prompt = self._manifest.prompt
        template = (
            prompt.demo_experiment_command if prompt is not None else None
        ) or ""
        if not template:
            return ""
        return template.format(
            session_workspace=config.workspace_path or "",
            skill_id=self.skill_id,
            subject_id=config.subject_id or config.instrument,
            variant=config.variant or config.timeframe,
        )

    def iteration_marker_prefix(self) -> str:
        op = self._manifest.output_parser
        if op is None:
            return "ITERATION_RESULT:"
        return op.iteration_marker or "ITERATION_RESULT:"

    def directive_prompt(self, config: "ResearchConfig") -> str:
        """Build the session-directing user prompt from the manifest.

        Structure: goal header → manifest-declared setup/experiment commands →
        fixed skill_params notice → promotion handoff → focus hint →
        cross-session resume block → phase contract. Every domain-specific
        line comes from the manifest; the orchestrator contributes only the
        generic scaffolding (budget, handoff contract, phase rendering).
        """
        from src.core.orchestrator import PROMOTION_HANDOFF_INSTRUCTION

        parts: list[str] = [
            (
                f"Run research for skill '{self.skill_id}' — subject "
                f"{config.subject_id}, variant {config.variant} "
                f"(tag: {config.tag}). Max {config.max_iterations} iterations."
            )
        ]

        prompt_cfg = self._manifest.prompt
        steps: list[str] = []
        if prompt_cfg is not None:
            if prompt_cfg.setup_command:
                steps.append(
                    "1. Setup:\n"
                    f"```bash\n{prompt_cfg.setup_command}\n```"
                )
            if prompt_cfg.experiment_command:
                steps.append(
                    (
                        f"{len(steps) + 1}. Experiment command "
                        "(run once per iteration):\n"
                        f"```bash\n{self.experiment_command(config)}\n```"
                    )
                )
        if steps:
            parts.append(
                "Execute these steps IN ORDER — do not explore first:\n\n"
                + "\n\n".join(steps)
            )

        fixed = {
            key: value
            for key, value in (getattr(config, "skill_params", None) or {}).items()
            if value is not None
        }
        if fixed:
            fields_str = ", ".join(f"{k}: {v}" for k, v in fixed.items())
            parts.append(
                f"**FIXED SETTINGS (operator-supplied, do NOT modify):** "
                f"{fields_str}."
            )

        parts.append(PROMOTION_HANDOFF_INSTRUCTION)
        parts.append(
            "Run autonomously. Start with the steps above without exploring "
            "the filesystem first."
        )
        if config.focus_hint:
            parts.append(f"Focus hint: {config.focus_hint}")
        resume_block = self._orch._load_research_resume(config)
        if resume_block:
            parts.append(resume_block.strip())
        phase_contract = self._orch._build_phase_contract_block(config)
        if phase_contract:
            parts.append(phase_contract.strip())
        return "\n\n".join(p for p in parts if p)

    def resume_prompt(
        self,
        config: "ResearchConfig",
        parent: SessionRecord,
        parent_iterations: list[IterationRecord],
    ) -> str:
        """Build the continuation prompt for a resumed session.

        Generic version of the legacy resume prompt: reports the parent's
        best result and iteration history, points the agent at the preserved
        workspace, and re-issues the manifest's experiment command.
        """
        from src.core.gate_status import training_gates_passed_from_iteration
        from src.core.orchestrator import PROMOTION_HANDOFF_INSTRUCTION

        parent_id = config.resumed_from
        parent_insights = str((parent or {}).get("insights", "") or "")
        parent_best_iter = (parent or {}).get("best_iteration")
        parent_best_metric = (parent or {}).get("best_metric")

        iter_lines = []
        for it in parent_iterations or []:
            num = it.get("iteration", "?")
            pm = it.get("primary_metric")
            metric_s = f"{pm:.4f}" if pm is not None else "—"
            gates = "✅" if training_gates_passed_from_iteration(it) else "❌"
            decision = it.get("decision", "?")
            desc = str(it.get("description") or "")[:150]
            iter_lines.append(
                f"  {num}. metric={metric_s} gates={gates} "
                f"decision={decision} — {desc}"
            )
        iter_summary = (
            "\n".join(iter_lines) if iter_lines else "  (no iterations recorded)"
        )

        best_info = ""
        if parent_best_metric is not None:
            best_info = (
                f"Best result so far: iteration {parent_best_iter}, "
                f"metric={parent_best_metric:.4f}\n"
            )
        insights_block = ""
        if parent_insights.strip():
            insights_block = (
                f"\n**Insights from parent session:**\n{parent_insights.strip()}\n"
            )

        experiment_cmd = self.experiment_command(config)
        continue_block = ""
        if experiment_cmd:
            continue_block = (
                "Continue iterating with the experiment command:\n"
                f"```bash\n{experiment_cmd}\n```"
            )

        parts = [
            (
                f"**CONTINUATION SESSION** — Resuming research for skill "
                f"'{self.skill_id}' on {config.subject_id} / {config.variant} "
                f"(tag: {config.tag})."
            ),
            (
                f"The previous session (id: {parent_id[:12] if parent_id else '?'}) "
                f"recorded {len(parent_iterations or [])} iterations.\n"
                f"{best_info}"
                f"You have {config.max_iterations} iterations remaining."
            ),
            f"## Parent session iteration history\n{iter_summary}",
            insights_block,
            (
                "## Instructions\n\n"
                "The workspace is ALREADY SET UP from the previous session — "
                "do NOT repeat setup or the baseline."
            ),
            continue_block,
            PROMOTION_HANDOFF_INSTRUCTION,
            (
                "Build on the parent session's findings. Do NOT repeat "
                "experiments that already failed. Run autonomously."
            ),
        ]
        if config.focus_hint:
            parts.append(f"Focus hint: {config.focus_hint}")
        resume_block = self._orch._load_research_resume(config)
        if resume_block:
            parts.append(resume_block.strip())
        return "\n\n".join(p for p in parts if p)

    # ── Command policy ────────────────────────────────────────────
    def command_policy_extension(self) -> CommandPolicyExtension:
        """Read the allowed scripts/executables/files from the manifest's
        ``command_policy`` section (the model-specific extension to the
        orchestrator's domain-neutral base policy).

        ARC-011 review C4 (P4-016): each declared script that exists in the
        packaged skill dir is also resolved into ``script_paths`` so the
        governed command can execute it — the agent invokes the declared
        workspace-relative name (``eval/run.py``); the policy layer rewrites
        the argv to the read-only packaged path (never the agent-writable
        session workspace)."""
        cp = self._manifest.command_policy
        ext: CommandPolicyExtension = {}
        if cp.allowed_scripts:
            ext["allowed_scripts"] = sorted(cp.allowed_scripts)
            script_paths = {}
            script_digests = {}
            for script in cp.allowed_scripts:
                packaged = self._skill_dir / script
                if packaged.is_file():
                    script_paths[script] = str(packaged)
                    script_digests[script] = _sha256_file(packaged)
            if script_paths:
                ext["script_paths"] = script_paths
                ext["script_digests"] = script_digests
        if cp.allowed_executables:
            ext["allowed_executables"] = sorted(cp.allowed_executables)
        if cp.copyable_files:
            ext["copyable_files"] = sorted(cp.copyable_files)
        if cp.readable_files:
            ext["readable_files"] = sorted(cp.readable_files)
        if cp.write_protected_files:
            ext["write_protected_files"] = sorted(cp.write_protected_files)
        # ARC-012 P7-011: the skill's declared config-artifact flag — policy
        # confinement and the pre-run snapshot both key on it (default
        # ``--config``).
        if cp.config_flag:
            ext["config_flag"] = cp.config_flag
        return ext

    # ── Iteration detection ───────────────────────────────────────
    def parse_iteration(
        self,
        raw_output: str,
        *,
        session_nonce: Optional[bytes] = None,
        config_snapshot: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        # P4-003: thread the manifest's nonce config (nonce_field +
        # require_signed_metrics) to the parser. When require_signed_metrics is
        # true, the parser validates the echoed nonce and rejects forged blocks.
        from src.core.output_parser import DelimitedKVParser, JSONMarkerParser

        op = self._manifest.output_parser
        marker = op.iteration_marker or "ITERATION_RESULT:"
        if marker in raw_output:
            return cast(
                Optional[dict[str, Any]],
                JSONMarkerParser().parse_iteration(
                    raw_output,
                    session_nonce=session_nonce,
                    nonce_field=op.nonce_field,
                    require_signed_metrics=op.require_signed_metrics,
                ),
            )
        return cast(
            Optional[dict[str, Any]],
            DelimitedKVParser().parse_iteration(
                raw_output,
                session_nonce=session_nonce,
                nonce_field=op.nonce_field,
                require_signed_metrics=op.require_signed_metrics,
            ),
        )

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

    # ── Execution (P1-4) ───────────────────────────────────────────────
    def execution_concurrency(self) -> int:
        """The manifest's ``execution.concurrency`` (default 1 = sequential)."""
        execution = getattr(self._manifest, "execution", None)
        if execution is None:
            return 1
        return int(getattr(execution, "concurrency", 1) or 1)

    # ── Promotion ─────────────────────────────────────────────────
    def promotion_target(self) -> "PromotionTarget":
        """Build the development-scope ``PromotionTarget`` from the manifest's
        ``promotion_target.primary``.

        ARC-011 review C2 (2026-08-15) + P1-3, centralized by ARC-012
        P7-007: resolution lives in ONE site —
        ``promotion_target.promotion_target_from_manifest`` — shared with the
        API's manual promotion path and the orchestrator's auto-promote path.
        The declared ``kind`` must match an implemented target (``file_path``
        with its declared ``path_template`` / ``webhook`` / ``registry_api``
        with an endpoint); anything else raises ``SkillConfigError`` instead
        of silently downgrading to a file write.
        """
        from src.core.promotion_target import promotion_target_from_manifest

        try:
            return promotion_target_from_manifest(self._manifest)
        except SkillConfigError:
            raise
        except ValueError as exc:
            raise SkillConfigError(str(exc)) from exc

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

    # ── Structured HPO (reserved) ─────────────────────────────────
    def structured_hpo_plan(
        self,
        config: "ResearchConfig",
    ) -> Optional[StructuredHPOPlan]:
        # The ``structured_hpo`` manifest section is parsed and reserved, but
        # the former server-owned HPO trial-planner engine (built for the ML
        # tuning skills) was removed with them. Skills that need planned
        # trials should ship a ``plan_generator`` plugin; until one is
        # registered this returns None (no planned-trial enforcement).
        return None

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
    """Build the ``SkillRuntime`` for a session.

    Every session is manifest-driven: ``config.skill_id`` must resolve in the
    skill registry. A missing/empty ``skill_id`` or one the registry rejects
    raises ``SkillConfigError`` — there is no transitional fallback anymore.
    (The legacy ML runtimes were removed together with the trading skills.)
    """
    skill_id = config.skill_id
    if not skill_id:
        raise SkillConfigError(
            "session has no skill_id — every session must name an installed "
            "skill (legacy model_type-only sessions are no longer supported)"
        )
    try:
        from src.core.skill_registry import default_registry

        manifest = default_registry.get(skill_id)
    except Exception as exc:  # noqa: BLE001 — re-raised below with context
        raise SkillConfigError(
            f"skill_id {skill_id!r} was rejected by the skill registry "
            f"(the manifest is missing, invalid, or was removed by a "
            f"reload): {exc}"
        ) from exc
    if manifest is None:
        raise SkillConfigError(
            f"skill_id {skill_id!r} is not registered; cannot materialize a "
            "SkillRuntime"
        )
    return ManifestSkillRuntime(manifest, orchestrator)


__all__ = [
    "AdvancementRule",
    "CommandPolicyExtension",
    "IterationRecord",
    "ManifestSkillRuntime",
    "Phase",
    "SessionRecord",
    "SkillConfigError",
    "SkillRuntime",
    "StructuredHPOPlan",
    "SubjectDescriptor",
    "VariantDescriptor",
    "materialize_skill_runtime",
]
