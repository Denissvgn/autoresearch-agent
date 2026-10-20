"""Skill-manifest loader (ARC-011 P2-002).

Loads a ``research_skill.v1`` ``SKILL.yaml`` (P2-001 schema) and resolves its
``{settings.<name>}`` / ``{skill_params.<name>}`` placeholders (G6). This module
owns the *loader semantics* that the schema deliberately leaves open (P2-001
only *allows* the placeholders; substitution happens here).

The split is deliberate (spike G6):

* ``skill_manifest.py`` (P2-001) — the schema. Allows placeholders as opaque
  strings; rejects structurally wrong manifests with field-specific errors.
* ``skill_loader.py`` (P2-002, this file) — yaml parse + G6 interpolation +
  version-compat gate + per-field defaults. Produces a ready ``ResearchSkillManifest``.

Design decisions (P1-007 house style):

* **Interpolation is pre-validation.** ``{settings.*}`` / ``{skill_params.*}``
  tokens are substituted in the raw YAML dict *before* pydantic sees it, so the
  schema validates the *resolved* value (e.g. a URL string, not a placeholder).
  This keeps validation errors field-specific against the post-substitution
  shape an operator would actually see.
* **``settings_obj`` is injectable.** Defaults to the singleton ``settings``
  (``src.config``), so production uses live server settings; tests inject a
  stub. Mirrors ``service_preflight.build_service_preflight_targets``'s
  ``settings_obj=settings`` parameter (P1-021 house style).
* **``skill_params`` interpolation is opt-in.** ``{skill_params.<name>}`` is only
  resolvable when a session supplies ``skill_params`` (P2-017); a manifest that
  references ``{skill_params.*}`` at load time (no session context) raises a
  field-specific error. ``settings.*`` is always resolvable.
* **Version-compat gate.** ``research_skill.v1`` is accepted; unknown versions
  raise ``ManifestVersionError``. N-1 support is forward-compat scaffolding
  (a v1.1 that drops to v1) — not exercised today.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Mapping, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.core.skill_manifest import (
    SCHEMA_VERSION,
    ManifestValidationError,
    ManifestVersionError,
    PluginCaps,
    PluginEntry,
    PluginKind,
    ResearchSkillManifest,
)

logger = logging.getLogger(__name__)

#: Match ``{settings.<attr>}`` placeholders in any string field. The attribute
#: name is restricted to identifiers so ``{settings.a.b}`` (nested) is *not*
#: matched — settings attrs are flat.
_SETTINGS_PATTERN = re.compile(r"\{settings\.([A-Za-z_]\w*)\}")

#: Match ``{skill_params.<key>}`` placeholders. Same flat-attr restriction.
_SKILL_PARAMS_PATTERN = re.compile(r"\{skill_params\.([A-Za-z_]\w*)\}")

#: All placeholder namespaces the loader knows how to resolve. An unrecognized
#: namespace (e.g. ``{foo.bar}``) is left untouched and surfaces later as a
#: validation error or a runtime ``KeyError`` — surfaced loudly, not silently.
_KNOWN_NAMESPACES = ("settings", "skill_params")


# ---------------------------------------------------------------------------
# Full skill-package layout (ARC-011 §5.3 / P5-001)
# ---------------------------------------------------------------------------

#: The canonical plugin filename for each kind (ARC-011 §5.3). When a skill
#: omits ``plugins.entries`` in the manifest but the file exists on disk, the
#: loader materializes a default-capped entry for it (X-004 §6 per-kind caps).
_DEFAULT_PLUGIN_FILES: dict[PluginKind, str] = {
    "bootstrap": "bootstrap.py",
    "parser": "parser.py",
    "preflight": "preflight.py",
    "resolve_identity": "resolve_identity.py",
}

#: X-004 §6 ``Default caps per kind`` — applied by ``load_layout`` when a skill
#: declares a plugin via file presence (no explicit ``plugins.entries``) or
#: when a manifest entry omits ``caps``.
_DEFAULT_CAPS_BY_KIND: dict[PluginKind, PluginCaps] = {
    "parser": PluginCaps(fs_write="none", network_egress=[], env=[]),
    "resolve_identity": PluginCaps(fs_write="none", network_egress=[], env=[]),
    "preflight": PluginCaps(fs_write="none", network_egress=[], env=[]),
    "bootstrap": PluginCaps(fs_write="workspace", network_egress=[], env=[]),
    # phase_advancement resolvers decide plan transitions: read-only, no
    # egress, bounded — the same posture as parsers/identity resolvers.
    "phase_advancement": PluginCaps(fs_write="none", network_egress=[], env=[]),
}


class SkillLayout(BaseModel):
    """Resolved on-disk layout of a skill package (ARC-011 §5.3, P5-001).

    Pure metadata: which optional files/dirs exist, which plugins are declared,
    and the resolved capability grant per plugin. Produces *no* side effects —
    nothing is executed here. The ``BootstrapRunner`` (P5-005) and the
    ``PluginRunner`` consume the resolved layout + caps at session start.

    Design decisions (P1-007 house style):
    * **Path-existence checks only.** Resolution reads the filesystem; it never
      imports or runs the discovered modules. Trust boundary enforced at the
      ``PluginRunner`` subprocess (X-004 D2/D4).
    * **Back-compat.** Every optional field defaults to absent; existing skills
      with only ``SKILL.yaml``/``SKILL.md`` produce a valid (minimal) layout.
    * **Caps are resolved, not authored.** The manifest's ``plugins.entries``
      may omit ``caps``; resolution back-fills the X-004 per-kind default. A
      manifest that *narrows* a default keeps its narrower grant; one that
      *widens* beyond the kind default is rejected (R10 defense in depth).
    """

    model_config = ConfigDict(extra="forbid")

    #: Absolute path of the skill package directory (``skills/<id>/``).
    skill_dir: Path
    #: ``bootstrap.py`` present? (P5-005 runs it once at session start.)
    has_bootstrap: bool = False
    #: ``scaffold/`` template dir present? (rendered into the workspace by the
    #: bootstrap plugin.)
    has_scaffold: bool = False
    #: ``knowledge/`` corpus present? (RAG primer / heuristics / prior findings.)
    has_knowledge: bool = False
    #: ``eval/`` harness present? (the skill-local evaluation runner.)
    has_eval: bool = False
    #: ``tools/`` optional domain-tool plugins present?
    has_tools: bool = False
    #: Resolved plugins keyed by kind, with caps materialized to the X-004
    #: per-kind default when the manifest omitted them.
    plugins: dict[PluginKind, PluginEntry] = Field(default_factory=dict)
    #: Plugin paths that are declared in the manifest but absent on disk
    #: (an authoring/deployment error; the loader surfaces it but does not raise
    #: — the caller decides whether missing plugins are fatal).
    missing_plugin_paths: list[str] = Field(default_factory=list)


def _resolve_caps(
    kind: PluginKind,
    declared: Optional[PluginCaps],
) -> PluginCaps:
    """Return the effective capability grant for a plugin, honoring the X-004
    "narrow but never widen" rule (R10)."""
    default = _DEFAULT_CAPS_BY_KIND[kind]
    if declared is None:
        return default
    # Narrow-but-never-widen checks (R10): the manifest grant must be a subset
    # of (or equal to) the per-kind default.
    if declared.fs_write == "workspace" and default.fs_write == "none":
        raise ManifestValidationError(
            f"plugins.{kind}: fs_write=workspace widens the per-kind default "
            f"(none) — manifests may narrow, not widen, plugin caps"
        )
    extra_env = set(declared.env) - set(default.env)
    if extra_env:
        raise ManifestValidationError(
            f"plugins.{kind}: env {sorted(extra_env)} not permitted by the "
            f"per-kind default (allowed: {sorted(default.env) or '<none>'})"
        )
    extra_egress = set(declared.network_egress) - set(default.network_egress)
    if extra_egress:
        raise ManifestValidationError(
            f"plugins.{kind}: network_egress {sorted(extra_egress)} not permitted "
            f"by the per-kind default (allowed: {sorted(default.network_egress) or '<none>'})"
        )
    # Caps the manifest may legitimately tighten (smaller is safer):
    return PluginCaps(
        fs_write=declared.fs_write,
        network_egress=list(declared.network_egress),
        env=list(declared.env),
        timeout_s=min(declared.timeout_s, default.timeout_s),
        max_rss_mb=min(declared.max_rss_mb, default.max_rss_mb),
        max_cpu_s=min(declared.max_cpu_s, default.max_cpu_s),
    )


def load_layout(
    skill_dir: Union[str, Path],
    manifest: Optional[ResearchSkillManifest] = None,
) -> SkillLayout:
    """Resolve the on-disk layout of a skill package (ARC-011 §5.3, P5-001).

    ``skill_dir`` is the package root containing ``SKILL.yaml``. If ``manifest``
    is omitted, it is loaded from ``skill_dir/SKILL.yaml``. Plugin entries
    declared in the manifest are cross-checked against the files on disk; any
    plugin file present but undeclared is materialized with the X-004 per-kind
    default caps (so a skill that ships ``bootstrap.py`` without a manifest
    ``plugins`` block still bootstraps).

    Does NOT execute anything — pure path/capability resolution. The
    ``PluginRunner`` (P5-005) is the runtime consumer.
    """
    root = Path(skill_dir)
    layout = SkillLayout(
        skill_dir=root,
        has_bootstrap=(root / "bootstrap.py").is_file(),
        has_scaffold=(root / "scaffold").is_dir(),
        has_knowledge=(root / "knowledge").is_dir(),
        has_eval=(root / "eval").is_dir(),
        has_tools=(root / "tools").is_dir(),
    )

    if manifest is None:
        manifest_path = root / "SKILL.yaml"
        if manifest_path.is_file():
            manifest = load_skill_manifest(manifest_path)

    # Start from manifest-declared plugins (caps resolved to defaults).
    resolved: dict[PluginKind, PluginEntry] = {}
    missing: list[str] = []
    if manifest is not None:
        for entry in manifest.plugins.entries:
            resolved_caps = _resolve_caps(entry.kind, entry.caps)
            resolved[entry.kind] = PluginEntry(
                kind=entry.kind, path=entry.path, caps=resolved_caps
            )
            if not (root / entry.path).is_file():
                missing.append(entry.path)

    # Back-fill from on-disk presence: a skill shipping ``bootstrap.py`` etc.
    # without a manifest declaration still gets a default-capped entry.
    for kind, filename in _DEFAULT_PLUGIN_FILES.items():
        if kind in resolved:
            continue
        if (root / filename).is_file():
            resolved[kind] = PluginEntry(
                kind=kind, path=filename, caps=_DEFAULT_CAPS_BY_KIND[kind]
            )

    layout.plugins = resolved
    layout.missing_plugin_paths = sorted(set(missing))
    return layout





def _interpolate_string(
    value: str,
    *,
    settings_obj: Any,
    skill_params: Optional[Mapping[str, Any]],
    field_path: str,
) -> str:
    """Resolve ``{settings.*}`` / ``{skill_params.*}`` in one string.

    Raises ``ManifestValidationError`` if a referenced attribute is missing on
    the settings object or in ``skill_params`` (field-specific, per P2-001 AC #3
    and G6).
    """

    def resolve_settings(match: re.Match[str]) -> str:
        attr = match.group(1)
        try:
            resolved = getattr(settings_obj, attr)
        except AttributeError as exc:
            raise ManifestValidationError(
                f"{field_path}: {{{{settings.{attr}}}}} references unknown setting "
                f"(not an attribute of {type(settings_obj).__name__})"
            ) from exc
        if resolved is None:
            raise ManifestValidationError(
                f"{field_path}: {{{{settings.{attr}}}}} resolves to None "
                f"(setting present but unset)"
            )
        return str(resolved)

    def resolve_skill_params(match: re.Match[str]) -> str:
        attr = match.group(1)
        if skill_params is None:
            raise ManifestValidationError(
                f"{field_path}: {{{{skill_params.{attr}}}}} cannot be resolved at "
                f"load time (no session skill_params supplied)"
            )
        if attr not in skill_params:
            raise ManifestValidationError(
                f"{field_path}: {{{{skill_params.{attr}}}}} not in the supplied "
                f"skill_params"
            )
        return str(skill_params[attr])

    value = _SETTINGS_PATTERN.sub(resolve_settings, value)
    value = _SKILL_PARAMS_PATTERN.sub(resolve_skill_params, value)
    return value


def _interpolate(
    node: Any,
    *,
    settings_obj: Any,
    skill_params: Optional[Mapping[str, Any]],
    field_path: str,
) -> Any:
    """Recursively interpolate placeholders in a raw YAML value (pre-validation)."""
    if isinstance(node, str):
        return _interpolate_string(
            node,
            settings_obj=settings_obj,
            skill_params=skill_params,
            field_path=field_path,
        )
    if isinstance(node, dict):
        return {
            k: _interpolate(
                v,
                settings_obj=settings_obj,
                skill_params=skill_params,
                field_path=f"{field_path}.{k}" if field_path else k,
            )
            for k, v in node.items()
        }
    if isinstance(node, list):
        return [
            _interpolate(
                item,
                settings_obj=settings_obj,
                skill_params=skill_params,
                field_path=f"{field_path}[{idx}]",
            )
            for idx, item in enumerate(node)
        ]
    return node


def _wrap_validation_error(exc: ValidationError) -> ManifestValidationError:
    """Turn a pydantic ``ValidationError`` into a field-specific, human-readable
    ``ManifestValidationError`` (P2-001 AC #3)."""
    errors = exc.errors()
    lines = []
    for err in errors:
        loc = ".".join(str(part) for part in err["loc"]) or "<root>"
        lines.append(f"  {loc}: {err['msg']}")
    summary = "manifest validation failed:\n" + "\n".join(lines)
    return ManifestValidationError(summary, errors=errors)


def load_skill_manifest(
    source: Union[str, Path, Mapping[str, Any]],
    *,
    settings_obj: Any = None,
    skill_params: Optional[Mapping[str, Any]] = None,
) -> ResearchSkillManifest:
    """Load and validate a ``research_skill.v1`` manifest.

    Parameters
    ----------
    source:
        A path to a ``SKILL.yaml`` file, a YAML string, or an already-parsed
        dict. Paths/strings are parsed with ``yaml.safe_load``.
    settings_obj:
        Object exposing ``{settings.*}`` attributes (G6). Defaults to the
        singleton ``src.config.settings``. Tests inject a stub.
    skill_params:
        Optional session-supplied params for ``{skill_params.*}`` resolution.
        Usually ``None`` at registry-load time (a manifest referencing
        ``{skill_params.*}`` then raises a field-specific error); supplied when
        a session builds its runtime (P2-007 / P2-017).

    Returns
    -------
    ResearchSkillManifest
        A validated, interpolation-resolved manifest.

    Raises
    ------
    ManifestVersionError
        If ``schema_version`` is not ``research_skill.v1``.
    ManifestValidationError
        If structural validation or placeholder resolution fails (field-specific
        message).
    """
    # Deferred import: ``src.config.settings`` instantiation requires env vars
    # (ANTHROPIC_BASE_URL etc.); importing it lazily lets this module load in
    # environments where settings aren't configured (e.g. some unit tests).
    if settings_obj is None:
        from src.config import settings as _settings

        settings_obj = _settings

    # ── Parse ──────────────────────────────────────────────────────────────
    if isinstance(source, Mapping):
        data: dict[str, Any] = dict(source)  # already a dict (e.g. tests)
    elif isinstance(source, Path):
        text = Path(source).read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
        if not isinstance(parsed, dict):
            raise ManifestValidationError(
                f"manifest must be a YAML mapping, got {type(parsed).__name__}"
            )
        data = parsed
    elif isinstance(source, str):
        # A path string vs an inline YAML string: a real path is short, single-
        # line, and exists on disk; otherwise treat as inline YAML.
        candidate = Path(source)
        if "\n" not in source and candidate.exists():
            text = candidate.read_text(encoding="utf-8")
        else:
            text = source
        parsed = yaml.safe_load(text)
        if not isinstance(parsed, dict):
            raise ManifestValidationError(
                f"manifest must be a YAML mapping, got {type(parsed).__name__}"
            )
        data = parsed
    else:
        raise ManifestValidationError(
            f"load_skill_manifest: unsupported source type {type(source).__name__}"
        )

    # ── Version-compat gate (before interpolation; cheap structural check) ──
    declared_version = data.get("schema_version")
    if declared_version != SCHEMA_VERSION:
        raise ManifestVersionError(
            f"unsupported schema_version {declared_version!r}; expected {SCHEMA_VERSION!r} "
            f"(loader accepts {SCHEMA_VERSION} only; N-1 support is forward-compat)",
        )

    # ── G6: interpolate placeholders in the raw dict (pre-validation) ──────
    data = _interpolate(
        data,
        settings_obj=settings_obj,
        skill_params=skill_params,
        field_path="",
    )

    # ── Validate ───────────────────────────────────────────────────────────
    try:
        return ResearchSkillManifest.model_validate(data)
    except ValidationError as exc:
        raise _wrap_validation_error(exc) from exc


__all__ = [
    "SkillLayout",
    "load_layout",
    "load_skill_manifest",
]
