"""``research_skill.v1`` manifest schema (ARC-011 P2-001).

This module is the authoritative Pydantic v2 model for a *skill descriptor* —
the declarative ``SKILL.yaml`` that captures every domain-specific decision the
orchestrator used to hardcode behind ``if config.model_type == ...`` branches
(ARC-011 §5.2, §9). One validated schema serves all skills; the three incumbent
ML skills (``ml-direction`` / ``ml-volatility`` / ``ml-rl``) are authored
against it in Phase 2 (P2-005 / P2-009 / P2-013).

Requirements input: ``docs/adr/ARC-011-manifest-spike.md`` §7 (schema
punch-list, gaps G1–G13) and §4 (section-name canonicalization). The GO verdict
of that spike greenlights this schema; the gap list below maps each resolved
gap to the field that addresses it.

Design decisions (P1-007 house style):

* **Pydantic v2, not TypedDict.** Unlike the Phase-1 value types (``IterationResult``,
  ``Phase`` — TypedDict aliases over existing dict shapes, kept mutable for the
  orchestrator), a manifest is a *configuration document* that must be loaded,
  validated, and rejected with field-specific errors before a session ever
  starts. Pydantic v2 gives coercion, cross-field validators, and human-readable
  ``ValidationError`` messages for free — exactly P2-001 AC #3. Loaded manifests
  are converted to the Phase-1 ``TypedDict`` shapes at the ``ManifestSkillRuntime``
  boundary (P2-007) so callers downstream of the runtime keep using plain dicts.
* **``extra="forbid"``.** Unknown keys are a schema-version or authoring error;
  surface them loudly. Mirrors ``research_manifest.py``.
* **G6 split.** This schema only *allows* ``{settings.<name>}`` /
  ``{skill_params.<name>}`` placeholders in string fields (they must pass
  validation as opaque strings). The substitution semantics belong to the loader
  (P2-002 ``skill_loader.py``); this module does not resolve them.
* **G1 / G2 are the only two sanctioned plugin escapes in v1** (spike §6). The
  schema carries ``phase_advancement.plugin`` and ``trial_identity.resolve.plugin``
  slots; any other behavior that resists declarative expression is an authoring
  bug, not a schema gap.

Gap resolution map (spike §6/§7 → this module):

* **G1** hybrid phase advancement → ``PhaseAdvancement`` + per-phase ``Phase.advancement``.
* **G2** trial-identity synthesis → ``TrialIdentity.resolve`` (plugin slot).
* **G3** actionable-blocker / phase-evidence sets → ``BlockerClassification``.
* **G4** per-scope gate bundles → ``GateBundles``.
* **G5** production composite REST → ``RegistryApiTarget`` fields.
* **G6** ``{settings.*}`` interpolation → allowed as opaque strings here; loader owns resolution.
* **G7** marker dir template + JSONPath → ``OutputParserFallback``.
* **G8** success-value marker → ``DecisionVocabulary.success_values``.
* **G10** multi-file artifact bundle → ``ArtifactStoreTarget.bundle_manifest``.
* **G11** optimize vs satisfice → ``MetricSchema.goal``.
* **G12** non-ML subjects/variants → ``Subjects`` / ``Variants``.
* **G13** category advisory metadata → ``ResearchSkillManifest.category``.

Section names are canonicalized per spike §4: ``metric_schema`` (not
``metrics``), ``phase_plan`` (not ``phases``), ``promotion_target`` (not
``promotion``).
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

#: The schema-version string every v1 manifest must declare (P2-001 AC #2).
#: The loader (P2-002) accepts this version and N-1; unknown versions raise a
#: clear ``ManifestVersionError``.
SCHEMA_VERSION = "research_skill.v1"

#: Advisory category values (ARC-011 §8.4 / §13, spike G13). Drives UI grouping
#: and category-derived defaults. Advisory only — not behaviorally load-bearing.
#: P5-014 widened from the original three to all five named in ARC-011 §13.
Category = Literal["optimization", "generative", "exploratory", "validation", "design"]

#: Metric-optimization semantics (G11). ``optimize`` = a single best iteration
#: wins; ``satisfice`` = meet a threshold, no single winner.
MetricGoal = Literal["optimize", "satisfice"]

#: Phase-advancement resolution mode (G1). ``declarative`` = evidence-key
#: presence + min/max cardinality only (expressible in YAML); ``plugin`` = a
#: sandboxed ``phases.py`` owns the hybrid completion rule.
AdvancementMode = Literal["declarative", "plugin"]

#: Trial-identity resolution mode (G2). ``declarative`` = ``hash_fields`` hash;
#: ``plugin`` = a sandboxed ``resolve_identity.py`` synthesizes the identity.
IdentityResolveMode = Literal["declarative", "plugin"]

#: Output-parser wire format (ARC-011 §9 ``output_parser.format``).
ParserFormat = Literal["delimited_kv", "json_marker"]

#: Preflight check transport (ARC-011 §9 ``preflight[].kind``). ``tcp`` maps to
#: ``TCPConnectCheck``; ``http_health`` / ``local_file`` map to
#: ``HTTPHealthCheck`` / a local-file existence check (P1-019..021).
PreflightKind = Literal["http_health", "tcp", "local_file"]

#: Promotion-target discriminator (ARC-011 §9 ``promotion_target.primary.kind``).
#: ``file_path`` → ``FilePathPromotionTarget`` (P1-015); ``registry_api`` /
#: ``artifact_store`` / ``git_branch`` are v1 slots enriched by G5 / G10.
PromotionKind = Literal["file_path", "registry_api", "artifact_store", "git_branch"]

#: Skill-plugin kinds (ARC-011 §5.3 / X-004 §6). Each maps to an optional
#: on-disk Python file in the skill package, executed via the governed
#: ``PluginRunner`` subprocess (P5-005). ``bootstrap`` runs once at session
#: start; the others run on demand per the runtime contract.
PluginKind = Literal["parser", "preflight", "resolve_identity", "bootstrap"]


# ---------------------------------------------------------------------------
# Top-level identity / routing sections
# ---------------------------------------------------------------------------


class LLMConfig(BaseModel):
    """LLM tier routing (ARC-011 §9 ``llm``)."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(description="Provider id (e.g. ``anthropic``, ``router``).")
    primary_model: str
    insight_model: Optional[str] = Field(
        default=None,
        description="Smaller model used for the insights summarization pass.",
    )
    max_output_tokens: int = Field(default=8192, ge=1)
    #: Relative path (within the skill package) of the system-prompt primer file.
    system_prompt: str = Field(default="SKILL.md")
    # P4-009: capability requirements the provider router (P4-010) matches
    # against ``provider.capabilities()``. Defaults preserve existing ML skills
    # (which all use Anthropic with native tool use + system prompts).
    required_native_tool_use: bool = True
    required_system_prompt: bool = True
    required_max_context_tokens: Optional[int] = Field(default=None, ge=1)


class WorkspaceConfig(BaseModel):
    """Per-session workspace layout (ARC-011 §9 ``workspace``)."""

    model_config = ConfigDict(extra="forbid")

    #: Template for the per-session run directory. Supports the placeholders
    #: ``{skill_id}``, ``{subject_id}``, ``{variant}`` plus ``{settings.*}`` (G6).
    session_path_template: str


class SubjectField(BaseModel):
    """One enumerated subject (e.g. an instrument / research topic)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: Optional[str] = None


class SubjectsConfig(BaseModel):
    """Subject enumeration (G12). ML skills glob config files today; non-ML
    skills use an enumerator script or an inline static list. ``static`` accepts
    either a list of ``{id, label}`` mappings (rich form) or a list of bare
    strings (id-only form, e.g. ``[postgres16, postgres15]``)."""

    model_config = ConfigDict(extra="forbid")

    enumerator: Optional[str] = Field(
        default=None,
        description="Relative path of a script emitting ``[{id, label}]`` JSON.",
    )
    static: Optional[list[SubjectField]] = Field(
        default=None, description="Inline subject list (mutually exclusive with ``enumerator``)."
    )
    cache_ttl_s: int = Field(default=60, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _coerce_static_strings(cls, data: Any) -> Any:
        """Accept bare-string subjects (``[postgres16, postgres15]``) by lifting
        them into the ``{id}`` mapping the model expects."""
        if isinstance(data, dict) and isinstance(data.get("static"), list):
            coerced = []
            for item in data["static"]:
                if isinstance(item, str):
                    coerced.append({"id": item})
                else:
                    coerced.append(item)
            data = {**data, "static": coerced}
        return data

    @model_validator(mode="after")
    def _enumerator_or_static(self) -> "SubjectsConfig":
        if self.enumerator is None and self.static is None:
            raise ValueError("subjects: provide either ``enumerator`` or ``static``")
        return self


class VariantsConfig(BaseModel):
    """Variant enumeration (G12). A variant is a per-subject sweep dimension
    (e.g. timeframe / question set)."""

    model_config = ConfigDict(extra="forbid")

    static: Optional[list[str]] = Field(default=None)
    enumerator: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def _static_or_enumerator(self) -> "VariantsConfig":
        if self.static is None and self.enumerator is None:
            raise ValueError("variants: provide either ``enumerator`` or ``static``")
        return self


# ---------------------------------------------------------------------------
# 1/8 param_schema — JSON Schema for skill_params
# ---------------------------------------------------------------------------


class ParamSchemaProperty(BaseModel):
    """One property in the ``param_schema`` JSON Schema (a subset of JSON-Schema
    draft-07 property descriptors is carried verbatim as a dict — P2-001 does
    not re-validate the inner JSON Schema, only the wrapper)."""

    model_config = ConfigDict(extra="allow")

    type: Optional[str] = None
    default: Any = None
    description: Optional[str] = None


class ParamSchema(BaseModel):
    """JSON Schema describing the ``skill_params`` a skill accepts (ARC-011
    §9 ``param_schema``). Lifted from ``ResearchConfig`` flat fields + the HTTP
    request bounds."""

    model_config = ConfigDict(extra="allow")

    type: Literal["object"] = "object"
    additionalProperties: bool = False
    properties: dict[str, ParamSchemaProperty] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 2/8 metric_schema
# ---------------------------------------------------------------------------


class PrimaryMetric(BaseModel):
    """The primary optimization metric (ARC-011 §9 ``metric_schema.primary``)."""

    model_config = ConfigDict(extra="forbid")

    field: str
    label: str
    direction: Literal["higher_is_better", "lower_is_better"]
    format: Optional[str] = Field(default=None, description="e.g. ``.4f``, ``duration_seconds``.")
    #: G7: JSONPath(s) into ``results.json`` used when the ``---`` block /
    #: marker is absent. Tried in order; first hit wins, else ``0.0``.
    primary_metric_jsonpath: Optional[list[str]] = Field(default=None)


class MetricColumn(BaseModel):
    """One gate badge, chart series, or iteration-table column."""

    model_config = ConfigDict(extra="allow")

    field: str
    label: str
    kind: Optional[str] = Field(default=None, description="e.g. ``boolean_badge``, ``icon``.")
    axis: Optional[Literal["left", "right"]] = None
    format: Optional[str] = None


class MetricSchema(BaseModel):
    """Metric presentation + semantics (ARC-011 §9 ``metric_schema``)."""

    model_config = ConfigDict(extra="forbid")

    primary: PrimaryMetric
    gates: list[MetricColumn] = Field(default_factory=list)
    chart_series: list[MetricColumn] = Field(default_factory=list)
    iteration_table_columns: list[MetricColumn] = Field(default_factory=list)
    #: G11: optimization domain. ``optimize`` (default) = single winner;
    #: ``satisfice`` = meet a threshold, no single winner.
    goal: MetricGoal = "optimize"
    satisfice_threshold_field: Optional[str] = Field(
        default=None,
        description="Boolean field gating satisfice completion (G11).",
    )


# ---------------------------------------------------------------------------
# 3/8 decision_vocabulary (G8)
# ---------------------------------------------------------------------------


class DecisionVocabulary(BaseModel):
    """Closed decision set + success marker (ARC-011 §9, G8)."""

    model_config = ConfigDict(extra="forbid")

    base: list[str]
    extensions: list[str] = Field(default_factory=list)
    #: G8: decisions that count as a "successful" iteration (e.g.
    #: ``{keep, improve, hpo_screening}``). Defaults to ``[keep, improve]``.
    success_values: list[str] = Field(default_factory=lambda: ["keep", "improve"])


# ---------------------------------------------------------------------------
# 4/8 phase_plan + phase_advancement (G1)
# ---------------------------------------------------------------------------


class PhaseAdvancementOverride(BaseModel):
    """Per-phase advancement override (G1). Inherits the top-level mode when
    omitted."""

    model_config = ConfigDict(extra="forbid")

    mode: AdvancementMode
    plugin: Optional[str] = Field(
        default=None,
        description="Relative path of the ``phases.py`` plugin (mode=plugin only).",
    )


class Phase(BaseModel):
    """One phase in the research playbook (ARC-011 §9 ``phase_plan[]``).
    Literals reproduce the incumbent ``DIRECTION_PHASES`` etc. verbatim."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: Optional[str] = None
    min_iterations: int = Field(ge=0)
    max_iterations: int = Field(ge=0)
    #: Metrics-json keys whose presence advances the phase (the declarative
    #: share of the G1 hybrid rule; the ``phases.py`` plugin owns the rest).
    evidence_keys: list[str] = Field(default_factory=list)
    next_action: Optional[str] = None
    #: Whether the phase is exempt from the global stagnation terminator
    #: (reconciles the global ``stagnation_exempt_phases`` per-phase).
    stagnation_exempt: bool = False
    #: G1: per-phase advancement override (inherits top-level mode if unset).
    advancement: Optional[PhaseAdvancementOverride] = None

    @model_validator(mode="after")
    def _min_le_max(self) -> "Phase":
        if self.min_iterations > self.max_iterations:
            raise ValueError(
                f"phase {self.id!r}: min_iterations ({self.min_iterations}) > "
                f"max_iterations ({self.max_iterations})"
            )
        return self


class PhaseAdvancement(BaseModel):
    """Top-level phase-advancement mode (G1). When ``mode == plugin`` the
    completion rule is owned by a sandboxed ``phases.py``; the declarative
    ``Phase`` fields above are its inputs."""

    model_config = ConfigDict(extra="forbid")

    mode: AdvancementMode = "declarative"
    plugin: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def _plugin_only_with_plugin_mode(self) -> "PhaseAdvancement":
        if self.mode == "plugin" and not self.plugin:
            raise ValueError("phase_advancement: mode=plugin requires a ``plugin`` path")
        if self.mode == "declarative" and self.plugin is not None:
            raise ValueError(
                "phase_advancement: ``plugin`` must be omitted when mode=declarative"
            )
        return self


# ---------------------------------------------------------------------------
# 5/8 command_policy
# ---------------------------------------------------------------------------


class CommandPolicy(BaseModel):
    """Allowed scripts / executables / files for the skill (ARC-011 §9
    ``command_policy``). The orchestrator's domain-neutral base policy
    (``_ALLOWED_PYTHON``, ``_DISALLOWED_EXECUTABLES``, ``_FORBIDDEN_*``,
    ``_SECRET_MARKERS``) is merged with this per-skill extension."""

    model_config = ConfigDict(extra="forbid")

    allowed_python: list[str] = Field(default_factory=list)
    allowed_scripts: list[str] = Field(default_factory=list)
    allowed_executables: list[str] = Field(default_factory=list)
    copyable_files: list[str] = Field(default_factory=list)
    readable_files: list[str] = Field(default_factory=list)
    forbidden_tokens: list[str] = Field(default_factory=list)
    forbidden_substrings: list[str] = Field(default_factory=list)
    secret_markers: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 5b/8 plugin_caps (X-004 §6 — the plugin capability contract)
# ---------------------------------------------------------------------------


class PluginCaps(BaseModel):
    """Capability block for one skill plugin (ARC-011 X-004 §6).

    The governed ``PluginRunner`` (P5-005) reads these per-plugin caps to
    build the subprocess environment / filesystem confinement before spawning.
    Default-deny: anything not declared here is withheld. The contract is the
    load-bearing input to P5-005 and P5-021 (generator safety).

    Per-kind defaults are applied by the registry/loader when a skill omits a
    ``plugin`` entry but the corresponding file is present on disk
    (X-004 §6 ``Default caps per kind``)::

        parser / resolve_identity → {fs_write: none, network_egress: [], env: []}
        preflight                 → {network_egress: [manifest health URLs]}
        bootstrap                 → {fs_write: workspace}
    """

    model_config = ConfigDict(extra="forbid")

    #: ``"workspace"`` = may write inside the session workspace only; ``"none"``
    #: = read-only. Matches X-004 §6 ``fs_write``.
    fs_write: Literal["workspace", "none"] = "none"
    #: Explicit network endpoints the plugin may reach (``host:port`` strings).
    #: Empty list = default-deny (the X-004 plugin posture).
    network_egress: list[str] = Field(default_factory=list)
    #: Additional env var names the plugin may read beyond the strict default
    #: allow-list (PATH/LANG/HOME/venv PYTHONPATH). Default none.
    env: list[str] = Field(default_factory=list)
    #: Hard wall-clock cap (seconds). Breach fails closed.
    timeout_s: float = Field(default=30.0, gt=0)
    #: Max resident set size in MB. Breach → psutil tree kill (D6).
    max_rss_mb: int = Field(default=512, ge=1)
    #: Max CPU time in seconds (D6).
    max_cpu_s: float = Field(default=30.0, gt=0)


class PluginEntry(BaseModel):
    """One declared skill plugin with its capability grant (X-004 §6).

    ``path`` is relative to the skill package root (e.g. ``"bootstrap.py"``,
    ``"parser.py"``). ``caps`` defaults to the X-004 per-kind default applied
    by the loader/registry at materialization time; a manifest may override
    any cap to *narrow* it (never widen beyond the kind default — defense in
    depth for R10 generated skills).
    """

    model_config = ConfigDict(extra="forbid")

    kind: PluginKind
    path: str = Field(description="Relative path of the plugin within the skill package.")
    caps: Optional[PluginCaps] = Field(
        default=None,
        description=(
            "Capability grant. Omit to take the X-004 per-kind default; the "
            "loader applies it. A manifest may narrow but not widen the default."
        ),
    )


class PluginsConfig(BaseModel):
    """Declared skill plugins + their capability grants (ARC-011 §5.3 / X-004).

    Optional in v1: skills with only ``SKILL.yaml``/``SKILL.md`` have no
    plugins. The loader (P5-001) cross-checks declared paths against the
    package's on-disk files; the registry surfaces the resolved layout via
    ``SkillLayout`` (P5-001). The ``PluginRunner`` (P5-005) is the sole
    consumer at runtime.
    """

    model_config = ConfigDict(extra="forbid")

    #: Declared plugins, keyed by ``kind`` for at-most-one-per-kind ergonomics.
    #: A list (not a dict) keeps the YAML authoring shape flat and lets the
    #: loader report duplicates with a clear pointer.
    entries: list[PluginEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_kinds_and_paths(self) -> "PluginsConfig":
        seen_kinds: set[str] = set()
        seen_paths: set[str] = set()
        for entry in self.entries:
            if entry.kind in seen_kinds:
                raise ValueError(
                    f"plugins: duplicate plugin kind {entry.kind!r} "
                    f"(at most one per kind per skill)"
                )
            if entry.path in seen_paths:
                raise ValueError(f"plugins: duplicate plugin path {entry.path!r}")
            seen_kinds.add(entry.kind)
            seen_paths.add(entry.path)
        return self


# ---------------------------------------------------------------------------
# 6/8 output_parser (G7)
# ---------------------------------------------------------------------------


class OutputParserFallback(BaseModel):
    """Fallback iteration sources when the primary parse yields nothing
    (ARC-011 §9 ``output_parser.fallback``, G7)."""

    model_config = ConfigDict(extra="forbid")

    read_marker_file: Optional[str] = Field(
        default=None, description="Basename of the marker fallback (e.g. ``last_metrics.txt``)."
    )
    read_results_file: Optional[str] = Field(
        default=None, description="Basename of the JSON results fallback (e.g. ``results.json``)."
    )
    #: G7: directory template for the fallback files. Supports
    #: ``{workspace_root}``, ``{subject_id_underscore}``, ``{variant}``,
    #: ``{skill_id}`` plus ``{settings.*}`` (G6).
    marker_dir_template: Optional[str] = None


class FieldTypes(BaseModel):
    """Type hints for parser fields used during coercion."""

    model_config = ConfigDict(extra="allow")


class OutputParserConfig(BaseModel):
    """Parser contract (ARC-011 §9 ``output_parser``, G7). Reproduces
    ``experiment_parser.py`` literals."""

    model_config = ConfigDict(extra="forbid")

    format: ParserFormat
    #: ``delimited_kv``: the block delimiter (default ``---``).
    block_delimiter: str = Field(default="---")
    #: ``json_marker``: the line marker (default ``ITERATION_RESULT:``).
    iteration_marker: str = Field(default="ITERATION_RESULT:")
    #: W11 anti-forgery nonce field name (Phase 4). Accepted, not enforced.
    nonce_field: Optional[str] = None
    #: W11 anti-forgery enforcement flag (P4-005). When ``true``, the parser
    #: validates the echoed nonce against the session's known nonce; a missing
    #: or wrong nonce rejects the metrics block. Default ``false`` keeps all
    #: existing ML skills working without changes (X-002 parity green). Flipped
    #: to ``true`` per-skill as each skill's eval script is backfilled (P4-004).
    require_signed_metrics: bool = False
    required_fields: list[str] = Field(default_factory=list)
    field_types: Optional[FieldTypes] = None
    failure_statuses: list[str] = Field(default_factory=list)
    fallback: Optional[OutputParserFallback] = None


# ---------------------------------------------------------------------------
# 7/8 preflight (G6)
# ---------------------------------------------------------------------------


class PreflightEntry(BaseModel):
    """One service-dependency preflight check (ARC-011 §9 ``preflight[]``).
    ``url`` / ``path`` may carry ``{settings.*}`` / ``{skill_params.*}``
    placeholders (G6, resolved by the loader)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: PreflightKind = "http_health"
    url: Optional[str] = Field(
        default=None, description="http_health/tcp endpoint (G6 placeholders ok)."
    )
    path: Optional[str] = Field(default=None, description="local_file path (G6 placeholders ok).")
    health_paths: list[str] = Field(default_factory=lambda: ["/health"])
    required: bool = True
    timeout_s: float = Field(default=3.0, ge=0)

    @model_validator(mode="after")
    def _kind_field_consistency(self) -> "PreflightEntry":
        if self.kind == "local_file" and self.path is None:
            raise ValueError(f"preflight {self.name!r}: kind=local_file requires ``path``")
        if self.kind in ("http_health", "tcp") and self.url is None:
            raise ValueError(f"preflight {self.name!r}: kind={self.kind} requires ``url``")
        return self


# ---------------------------------------------------------------------------
# 8/8 promotion_target (G4 gate bundles, G5 registry_api, G10 artifact_store)
# ---------------------------------------------------------------------------


class GateBundles(BaseModel):
    """Per-scope promotion gate bundles + override location (G4). Pure paths."""

    model_config = ConfigDict(extra="forbid")

    development: Optional[str] = None
    production: Optional[str] = None
    #: Template locating per-subject gate overrides (G6 placeholders ok).
    overrides_location: Optional[str] = None


class PromotionScope(BaseModel):
    """One promotion scope declaration (ARC-011 §9 ``promotion_target.scopes``)."""

    model_config = ConfigDict(extra="allow")

    id: str
    approval_required: bool = False
    #: Scopes that must precede this one in the chain (G5).
    prior_scopes: list[str] = Field(default_factory=list)


class FilePathPromotionTarget(BaseModel):
    """``kind: file_path`` — write a config file to the host bind mount
    (P1-015 ``FilePathPromotionTarget``)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["file_path"] = "file_path"
    #: G6: ``{settings.host_configs_path}`` etc. resolved by the loader.
    path_template: str
    sidecar_extensions: list[str] = Field(default_factory=list)
    rollback_template: Optional[str] = None
    atomic_write: bool = True


class RegistryLookup(BaseModel):
    """``registry_api.lookup`` — how to find the composite to promote (G5)."""

    model_config = ConfigDict(extra="forbid")

    by: str = Field(
        description="Composite version field to match (e.g. ``serving_model_version``)."
    )
    query_endpoint: str


class RegistryApiTarget(BaseModel):
    """``kind: registry_api`` — production composite REST promotion (G5).
    Enriched beyond the thin Analysis-§9 descriptor: lookup query, Bearer auth
    secret name, the rollup metric forwarded. The REST client itself stays in
    ``ConfigPromoter`` for Phase 2; the manifest *describes* it. The G5
    enrichment fields are optional so both the ml-direction production
    ``delegate`` (full G5 form) and the simpler prompt-registry primary validate."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["registry_api"] = "registry_api"
    registry: str
    #: Promote endpoint. Accepts the ``register_endpoint`` alias used by the
    #: prompt-registry flavor.
    endpoint: Optional[str] = Field(default=None, validation_alias="register_endpoint")
    lookup: Optional[RegistryLookup] = None
    auth_secret: Optional[str] = None
    rollup_metric: Optional[str] = None
    atomic_write: bool = True


class ArtifactStoreTarget(BaseModel):
    """``kind: artifact_store`` — promote a multi-file artifact bundle (G10)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["artifact_store"] = "artifact_store"
    path_template: str
    atomic_write: bool = True
    #: G10: manifest naming the bundle's constituent files.
    bundle_manifest: Optional[str] = None
    bundle_artifacts: list[str] = Field(default_factory=list)


class GitBranchTarget(BaseModel):
    """``kind: git_branch`` — promote to a version-control branch
    (code-refactor domain; flagged for the X-004 sandbox)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["git_branch"] = "git_branch"
    repository: Optional[str] = Field(
        default=None, description="Repo URL/identifier (G6 placeholders ok)."
    )
    base_branch: str
    #: Alias accepted: ``proposed_branch_template`` (code-refactor draft).
    target_branch_template: Optional[str] = Field(
        default=None, validation_alias="proposed_branch_template"
    )
    pr_template: Optional[dict[str, Any]] = None


#: Discriminated union over ``kind``. The literal ``kind`` tag lets pydantic
#: pick the right model and emit field-specific errors on mismatch.
PromotionTargetKind = Union[
    FilePathPromotionTarget,
    RegistryApiTarget,
    ArtifactStoreTarget,
    GitBranchTarget,
]


class PromotionTarget(BaseModel):
    """Promotion surface (ARC-011 §9 ``promotion_target``). ``primary`` is the
    default-scope (development) target; ``gate_bundles`` (G4) and ``scopes``
    describe the higher-scope chain."""

    model_config = ConfigDict(extra="forbid")

    primary: PromotionTargetKind = Field(..., discriminator="kind")
    gate_bundles: Optional[GateBundles] = None
    scopes: list[PromotionScope] = Field(default_factory=list)

    @model_validator(mode="after")
    def _registry_scope_needs_production(self) -> "PromotionTarget":
        # A registry_api primary only makes sense for a production scope.
        if isinstance(self.primary, RegistryApiTarget):
            if not any(s.id == "production" for s in self.scopes):
                raise ValueError(
                    "promotion_target: registry_api primary requires a 'production' scope"
                )
        return self


# ---------------------------------------------------------------------------
# Cross-cutting sections
# ---------------------------------------------------------------------------


class IdentityResolve(BaseModel):
    """``trial_identity.resolve`` — the G2 plugin selector. ``mode=declarative``
    means ``hash_fields`` hash is sufficient; ``mode=plugin`` delegates the
    multi-source synthesis (``data_split_id`` / ``seed`` / ``validation_mode``
    probes) that ``iteration_snapshot.build_trial_identity`` performs today to a
    sandboxed ``resolve_identity.py``."""

    model_config = ConfigDict(extra="forbid")

    mode: IdentityResolveMode = "declarative"
    plugin: Optional[str] = Field(
        default=None,
        description="Relative path of ``resolve_identity.py`` (mode=plugin only).",
    )

    @model_validator(mode="after")
    def _plugin_consistency(self) -> "IdentityResolve":
        if self.mode == "plugin" and not self.plugin:
            raise ValueError("trial_identity.resolve: mode=plugin requires a ``plugin`` path")
        if self.mode == "declarative" and self.plugin is not None:
            raise ValueError(
                "trial_identity.resolve: ``plugin`` must be omitted when mode=declarative"
            )
        return self


class TrialIdentityConfig(BaseModel):
    """Dedup trial-identity contract (ARC-011 §9 ``trial_identity``, G2).
    ``hash_fields`` covers the declarative common case; ``resolve`` selects the
    plugin for the multi-source synthesis."""

    model_config = ConfigDict(extra="forbid")

    hash_fields: list[str] = Field(default_factory=list)
    resolve: IdentityResolve = Field(default_factory=lambda: IdentityResolve(mode="declarative"))

    @model_validator(mode="after")
    def _declarative_needs_hash_fields(self) -> "TrialIdentityConfig":
        if self.resolve.mode == "declarative" and not self.hash_fields:
            raise ValueError(
                "trial_identity: declarative resolve mode requires non-empty ``hash_fields``"
            )
        return self


class BlockerClassification(BaseModel):
    """Actionable-blocker + per-phase evidence-key sets (G3). Reproduces
    ``_AGENT_ACTIONABLE_BLOCKERS`` and ``_PHASE_SPECIFIC_AGENT_KEYS`` (today at
    ``orchestrator.py``) as pure declarative data."""

    model_config = ConfigDict(extra="forbid")

    actionable_blockers: list[str] = Field(default_factory=list)
    phase_evidence_keys: dict[str, list[str]] = Field(default_factory=dict)


class StructuredHPOConfig(BaseModel):
    """Optional structured-HPO capability (ARC-011 §9 ``structured_hpo``)."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    plan_generator: Optional[str] = None
    max_trials: int = Field(default=200, ge=1)


class InsightsConfig(BaseModel):
    """Per-skill insights summarization (ARC-011 §9 ``insights``, G9)."""

    model_config = ConfigDict(extra="forbid")

    prompt_template: str
    model: Optional[str] = None
    max_chars: int = Field(default=500, ge=1)


class PromptConfig(BaseModel):
    """Prompt-assembly templates (ARC-011 §9 ``prompt``)."""

    model_config = ConfigDict(extra="forbid")

    setup_command: Optional[str] = None
    experiment_command: Optional[str] = None
    continuation_enabled: bool = True
    anti_waste_rules: Optional[str] = None


class UIConfig(BaseModel):
    """UI hints (ARC-011 §9 ``ui``). Advisory; not behaviorally load-bearing."""

    model_config = ConfigDict(extra="allow")

    form_fields: list[dict[str, Any]] = Field(default_factory=list)
    chart: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# The top-level manifest
# ---------------------------------------------------------------------------


class ResearchSkillManifest(BaseModel):
    """A validated ``research_skill.v1`` skill descriptor (ARC-011 P2-001).

    Covers every section in ARC-011 §9 plus the G3 ``blocker_classification``
    section. Load via ``skill_loader.load_skill_manifest`` (P2-002), which also
    resolves ``{settings.*}`` / ``{skill_params.*}`` placeholders (G6) and
    applies per-field defaults.
    """

    model_config = ConfigDict(extra="forbid")

    # ── Header ────────────────────────────────────────────────────────────
    schema_version: str = SCHEMA_VERSION
    id: str = Field(..., min_length=1)
    version: str
    category: Category
    display_name: str
    description: str

    # ── Identity / routing ────────────────────────────────────────────────
    llm: LLMConfig
    workspace: WorkspaceConfig
    subjects: Optional[SubjectsConfig] = None
    variants: Optional[VariantsConfig] = None

    # ── The eight required sections (spike §9 X-003 AC) ───────────────────
    param_schema: ParamSchema
    metric_schema: MetricSchema
    decision_vocabulary: DecisionVocabulary
    phase_plan: list[Phase] = Field(..., min_length=1)
    phase_advancement: PhaseAdvancement = Field(default_factory=PhaseAdvancement)
    command_policy: CommandPolicy
    output_parser: OutputParserConfig
    preflight: list[PreflightEntry] = Field(default_factory=list)
    promotion_target: PromotionTarget

    # ── Cross-cutting sections ────────────────────────────────────────────
    trial_identity: Optional[TrialIdentityConfig] = None
    blocker_classification: Optional[BlockerClassification] = None
    structured_hpo: StructuredHPOConfig = Field(default_factory=StructuredHPOConfig)
    insights: Optional[InsightsConfig] = None
    prompt: Optional[PromptConfig] = None
    ui: Optional[UIConfig] = None
    #: P5-001 / X-004: declared plugins + capability grants. Optional; the
    #: loader cross-checks paths against the package layout and the registry
    #: surfaces a resolved ``SkillLayout``. Consumed by ``PluginRunner`` (P5-005).
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    #: P5-028: when ``true``, completed-session insights are auto-fed into the
    #: system prompt on the next session. When ``false`` (default), insights
    #: land in ``knowledge/prior_findings/`` but require operator review first.
    auto_absorb_insights: bool = False
    #: P5-029: timestamp of the last operator review of the knowledge corpus.
    #: Drives the UI "knowledge stale" badge against ``refresh_cadence_days``.
    knowledge_last_reviewed: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp of the last knowledge-corpus review.",
    )
    #: P5-029: max age (days) before the knowledge corpus is flagged stale.
    refresh_cadence_days: Optional[int] = Field(
        default=None,
        ge=1,
        description="Days before the UI flags the knowledge corpus as stale.",
    )

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version {value!r}; expected {SCHEMA_VERSION!r} "
                f"(N-1 support is the loader's responsibility, P2-002)"
            )
        return value

    @model_validator(mode="after")
    def _unique_phase_ids(self) -> "ResearchSkillManifest":
        ids = [p.id for p in self.phase_plan]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"phase_plan: duplicate phase id(s): {sorted(dupes)}")
        return self

    @model_validator(mode="after")
    def _phase_evidence_keys_subset(self) -> "ResearchSkillManifest":
        """A per-phase ``advancement`` override must only reference known phases."""
        known = {p.id for p in self.phase_plan}
        for p in self.phase_plan:
            if p.advancement and p.advancement.mode == "plugin" and p.id not in known:
                # Defensive: phase ids come from the same list, so this is a no-op
                # today; kept as a forward-compat guard if overrides ever externalize.
                raise ValueError(
                    f"phase {p.id!r}: advancement override references unknown phase"
                )
        return self


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ManifestValidationError(ValueError):
    """Raised when a manifest fails structural validation. Wraps a pydantic
    ``ValidationError`` with a field-specific, human-readable summary (P2-001
    AC #3)."""

    def __init__(
        self,
        message: str,
        *,
        errors: Optional[list[Mapping[str, Any]]] = None,
    ) -> None:
        super().__init__(message)
        # ``Mapping`` is covariant, so callers may pass pydantic's
        # ``list[ErrorDetails]`` (a TypedDict) as well as ``list[dict]``.
        self.errors: list[Mapping[str, Any]] = list(errors) if errors else []


class ManifestVersionError(ManifestValidationError):
    """Raised by the loader (P2-002) for an unrecognized ``schema_version``."""


__all__ = [
    "SCHEMA_VERSION",
    "Category",
    "MetricGoal",
    "AdvancementMode",
    "IdentityResolveMode",
    "ParserFormat",
    "PreflightKind",
    "PromotionKind",
    "PluginKind",
    "PluginCaps",
    "PluginEntry",
    "PluginsConfig",
    # Sections
    "LLMConfig",
    "WorkspaceConfig",
    "SubjectField",
    "SubjectsConfig",
    "VariantsConfig",
    "ParamSchemaProperty",
    "ParamSchema",
    "PrimaryMetric",
    "MetricColumn",
    "MetricSchema",
    "DecisionVocabulary",
    "Phase",
    "PhaseAdvancementOverride",
    "PhaseAdvancement",
    "CommandPolicy",
    "OutputParserFallback",
    "FieldTypes",
    "OutputParserConfig",
    "PreflightEntry",
    "GateBundles",
    "PromotionScope",
    "FilePathPromotionTarget",
    "RegistryLookup",
    "RegistryApiTarget",
    "ArtifactStoreTarget",
    "GitBranchTarget",
    "PromotionTargetKind",
    "PromotionTarget",
    "TrialIdentityConfig",
    "IdentityResolve",
    "BlockerClassification",
    "StructuredHPOConfig",
    "InsightsConfig",
    "PromptConfig",
    "UIConfig",
    # Top-level
    "ResearchSkillManifest",
    # Errors
    "ManifestValidationError",
    "ManifestVersionError",
]
