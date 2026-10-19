"""Skill descriptor endpoints — the generic skill API surface (ARC-011 P3-001..008, P3-011).

A new research domain is added by dropping a ``skills/<id>/`` directory and
reloading — **zero orchestrator or UI code changes** (ARC-011 §7.14). This
module exposes the installed skill manifests to the UI and API clients so the
*same* NewResearch form, MetricsChart, IterationsTable, and PromotionModal can
render any skill from descriptor data alone.

Endpoint family (all under ``/api/v1``):

* ``GET /skills``                       — list of installed skill summaries
* ``GET /skills/{id}``                  — full skill descriptor
* ``GET /skills/{id}/param-schema``     — the ``param_schema`` JSON Schema
* ``GET /skills/{id}/form-fields``      — UI form-field definitions
* ``GET /skills/{id}/metric-schema``    — the ``metric_schema`` (chart/table/gates)
* ``GET /skills/{id}/versions``         — declared versions
* ``GET /skills/{id}/changelog``        — the skill's ``CHANGELOG.md`` content
* ``POST /skills/reload``               — auth-gated hot reload (dev)

Design decisions (P1-007 house style):

* **Registry-backed, not import-time.** The ``SkillRegistry`` is injected via
  ``init()`` (same DI pattern as ``research``/``results``/``promotion``).
  Defaults to ``default_registry`` when not wired (tests can pass their own).
* **Manifest projection, not re-serialization.** Responses are built by calling
  ``.model_dump()`` on the validated Pydantic manifest models — the schema is the
  single source of truth, so the API and the runtime can never drift.
* **404 with installable-skills hint.** An unknown ``skill_id`` returns a 404
  whose body lists the available skills (P3-013 AC, §10 guarantee).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.api.audit import record_api_audit_event
from src.api.auth import require_api_auth
from src.config import settings
from src.core.comparison_context import describe_comparison_context
from src.core.legacy_alias import skill_id_to_model_type
from src.core.skill_manifest import ResearchSkillManifest
from src.core.skill_registry import (
    DEFAULT_SKILLS_ROOT,
    SkillNotRegisteredError,
    SkillRegistry,
    default_registry,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["skills"], dependencies=[Depends(require_api_auth)])

#: Hard cap on the size of a skill's ``CHANGELOG.md`` surfaced via
#: ``GET /skills/{id}/changelog``. A skill's changelog is operator-facing
#: documentation; a runaway file should not be slurped into a single JSON
#: response or block the event loop on read. 64 KiB comfortably fits the
#: largest realistic skill changelog while bounding the response.
_MAX_CHANGELOG_BYTES: int = 64 * 1024

# Injected by main.py; falls back to the module-level default_registry so the
# endpoints work in tests without explicit wiring.
_registry: SkillRegistry = default_registry
_store: Any = None


def init(registry: Optional[SkillRegistry] = None, store: Any = None) -> None:
    """Wire the skill registry and store into this module (called from lifespan)."""
    global _registry, _store
    if registry is not None:
        _registry = registry
    _store = store


# ------------------------------------------------------------------
# Manifest → response projection helpers
# ------------------------------------------------------------------


def _skill_summary(manifest: ResearchSkillManifest) -> Dict[str, Any]:
    """A lightweight summary for ``GET /skills`` list responses.

    Carries the identity + category + the legacy ``model_type`` alias so the
    UI skill picker and the legacy ``GET /models`` alias can both be served
    from one projection.
    """
    return {
        "id": manifest.id,
        "version": manifest.version,
        "category": manifest.category,
        "display_name": manifest.display_name,
        "description": manifest.description,
        "schema_version": manifest.schema_version,
        # Legacy alias — empty string for non-ML skills (§10 guarantee #5).
        "model_type": skill_id_to_model_type(manifest.id),
        # Advisory: whether this skill declares subjects/variants.
        "has_subjects": manifest.subjects is not None,
        "has_variants": manifest.variants is not None,
    }


def _skill_descriptor(manifest: ResearchSkillManifest) -> Dict[str, Any]:
    """The full descriptor for ``GET /skills/{id}`` — the validated manifest
    projected to a JSON-serializable dict plus a ``links`` block."""
    dump = manifest.model_dump(exclude_none=True, mode="json")
    dump["model_type"] = skill_id_to_model_type(manifest.id)
    # Published support/diagnostics travel with the descriptor the UI renders:
    # actionable, machine-readable, and never an execution-authority grant.
    from src.core.support_matrix import support_descriptor

    dump["support"] = support_descriptor(manifest)
    dump["links"] = {
        "self": f"/skills/{manifest.id}",
        "support": f"/skills/{manifest.id}/support",
        "param_schema": f"/skills/{manifest.id}/param-schema",
        "form_fields": f"/skills/{manifest.id}/form-fields",
        "metric_schema": f"/skills/{manifest.id}/metric-schema",
        "versions": f"/skills/{manifest.id}/versions",
        "changelog": f"/skills/{manifest.id}/changelog",
    }
    return dump


def _form_fields(manifest: ResearchSkillManifest) -> List[Dict[str, Any]]:
    """UI form-field definitions for ``GET /skills/{id}/form-fields``.

    Priority: the manifest's ``ui.form_fields`` list (author-curated) is used
    verbatim when present. Otherwise the fields are synthesized from
    ``param_schema.properties`` so a skill with no ``ui`` section still gets a
    renderable form (the generic fallback, P3-028).
    """
    if manifest.ui and manifest.ui.form_fields:
        return list(manifest.ui.form_fields)

    # Synthesize from param_schema properties (generic fallback).
    fields: List[Dict[str, Any]] = []
    for name, prop in manifest.param_schema.properties.items():
        field: Dict[str, Any] = {
            "name": name,
            "type": prop.type or "string",
        }
        if prop.default is not None:
            field["default"] = prop.default
        if prop.description:
            field["description"] = prop.description
        # Carry JSON-Schema bounds if present (extra="allow" on ParamSchemaProperty).
        raw = prop.model_dump(exclude_none=True)
        for bound_key in ("minimum", "maximum", "enum"):
            if bound_key in raw:
                ui_key = {"minimum": "min", "maximum": "max"}.get(bound_key, bound_key)
                field[ui_key] = raw[bound_key]
        fields.append(field)
    return fields


def _skill_dir(manifest_id: str) -> Path:
    """Resolve the on-disk skill package directory for ``manifest_id``."""
    return DEFAULT_SKILLS_ROOT / manifest_id


async def _audit(
    request: Request,
    *,
    action: str,
    outcome: str,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
):
    if _store is None:
        return None  # dev/test path — audit not wired, skip gracefully
    return await record_api_audit_event(
        request,
        _store,
        action=action,
        outcome=outcome,
        metadata=metadata,
        error_message=error_message,
    )


def _get_or_404(skill_id: str) -> ResearchSkillManifest:
    """Load a manifest by id, raising 404 with an installable-skills hint."""
    try:
        return _registry.get(skill_id)
    except SkillNotRegisteredError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "skill_not_found",
                "skill_id": skill_id,
                "available": exc.available,
                "hint": (
                    f"Install the skill by dropping a directory under "
                    f"skills/{skill_id}/ with a SKILL.yaml, then call "
                    f"POST /skills/reload."
                ),
            },
        ) from exc


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("/skills")
async def list_skills(
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List installed skill summaries.

    Optional ``category`` filter (e.g. ``optimization``, ``analysis``).
    """
    summaries = [_skill_summary(_registry.get(sid)) for sid in _registry.available()]
    if category:
        summaries = [s for s in summaries if s.get("category") == category]
    return summaries


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    """Full skill descriptor (manifest + links)."""
    return _skill_descriptor(_get_or_404(skill_id))


@router.get("/skills/{skill_id}/param-schema")
async def get_skill_param_schema(skill_id: str):
    """The ``param_schema`` JSON Schema for ``skill_params`` validation."""
    manifest = _get_or_404(skill_id)
    return manifest.param_schema.model_dump(exclude_none=True, mode="json")


@router.get("/skills/{skill_id}/form-fields")
async def get_skill_form_fields(skill_id: str):
    """UI form-field definitions for the dynamic form renderer."""
    manifest = _get_or_404(skill_id)
    return {"skill_id": skill_id, "form_fields": _form_fields(manifest)}


@router.get("/skills/{skill_id}/support")
async def get_skill_support(skill_id: str):
    """Machine-readable support descriptor + actionable diagnostics.

    Publishes the support matrix (which declarations have implementing
    behavior), any unsupported-declaration diagnostics with remedies, and
    toolchain availability notes (path lookup only — never an authority
    grant).
    """
    manifest = _get_or_404(skill_id)
    from src.core.support_matrix import support_descriptor

    return support_descriptor(manifest)


@router.get("/skills/{skill_id}/metric-schema")
async def get_skill_metric_schema(skill_id: str):
    """The ``metric_schema`` — primary metric, gates, chart series, table columns."""
    manifest = _get_or_404(skill_id)
    return manifest.metric_schema.model_dump(exclude_none=True, mode="json")


@router.get("/skills/{skill_id}/leaderboard")
async def get_skill_leaderboard(
    skill_id: str,
    limit: int = Query(default=20, ge=1, le=100, title="Limit"),
    offset: int = Query(default=0, ge=0, title="Offset"),
):
    """Cross-session leaderboard for one skill — comparable groups only.

    Results rank inside explicit comparable-context groups (objective,
    units, dataset/scorer/fidelity pins, subject/variant constraints),
    computed in storage over the full history — there is no recent-N
    prefilter, so older champions are never dropped while the ranking is
    described as global. Contexts are never merged into one champion
    table: sessions without a recorded context rank only in their own
    unknown/legacy group.
    """
    manifest = _get_or_404(skill_id)
    metric_dump = manifest.metric_schema.model_dump(exclude_none=True, mode="json")
    primary = metric_dump.get("primary", {}) or {}
    direction = primary.get("direction", "higher_is_better")
    direction_name = "maximize" if direction == "higher_is_better" else "minimize"

    groups: List[Dict[str, Any]] = []
    if _store is not None:
        aliases = sorted(
            {skill_id, skill_id_to_model_type(skill_id)} - {""}
        )
        raw_groups = await _store.rank_leaderboard_groups(
            model_types=aliases,
            direction=direction_name,
            limit=limit,
            offset=offset,
        )
        for group in raw_groups:
            label = describe_comparison_context(group.get("comparison_context"))
            groups.append(
                {
                    "context": label["context"],
                    "label": label["label"],
                    "known_context": label["known"],
                    "items": [
                        {
                            "research_id": row.get("id"),
                            "subject_id": row.get("subject_id")
                            or row.get("instrument"),
                            "variant": row.get("variant")
                            or row.get("timeframe"),
                            "tag": row.get("tag"),
                            "status": row.get("status"),
                            "best_metric": row.get("best_metric"),
                            "metric_name": row.get("metric_name"),
                            "best_iteration": row.get("best_iteration"),
                            "iterations": row.get("effective_iteration_count")
                            or row.get("best_iteration")
                            or 0,
                            "total_api_cost_usd": row.get("total_api_cost_usd")
                            or 0.0,
                            "started_at": row.get("started_at"),
                            "completed_at": row.get("completed_at"),
                        }
                        for row in group.get("items", [])
                    ],
                    "total": group.get("total", 0),
                    "limit": group.get("limit", limit),
                    "offset": group.get("offset", offset),
                }
            )
    return {
        "skill_id": skill_id,
        "metric": {
            "field": primary.get("field", "primary_metric"),
            "label": primary.get("label", "Primary metric"),
            "direction": direction,
            "format": primary.get("format", ".4f"),
        },
        "ranking_scope": "global within comparable-context groups",
        "groups": groups,
    }


@router.get("/skills/{skill_id}/versions")
async def get_skill_versions(skill_id: str):
    """Declared skill versions + best-effort git-tag history.

    The declared block is the manifest's own version (the source of truth).
    The ``tags`` list surfaces ``skill/<id>/<version>`` git tags recorded by
    ``autoresearch promote-skill`` — a docker deployment without git simply
    reports an empty list.
    """
    manifest = _get_or_404(skill_id)
    tags = _skill_git_tags(skill_id)
    return {
        "skill_id": skill_id,
        "versions": [
            {
                "version": manifest.version,
                "schema_version": manifest.schema_version,
                "current": True,
                "tagged": f"skill/{skill_id}/{manifest.version}" in tags,
            }
        ],
        "tags": tags,
    }


def _skill_git_tags(skill_id: str) -> List[str]:
    """Git tags recorded for this skill (``skill/<id>/*``), newest-last.

    Best-effort: any failure (no git, not a repo, timeout) returns ``[]`` —
    the versions endpoint must never fail because git is unavailable.
    """
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "tag", "--list", f"skill/{skill_id}/*", "--sort=version:refname"],
            cwd=str(_skill_dir(skill_id).parent), capture_output=True,
            text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


@router.get("/skills/{skill_id}/changelog")
async def get_skill_changelog(skill_id: str):
    """The skill's ``CHANGELOG.md`` content.

    Capped at ``_MAX_CHANGELOG_BYTES`` to keep the response bounded — a skill
    whose changelog has outgrown that ceiling returns 413 with a structured
    detail so the operator knows to read the file directly rather than through
    the API."""
    _get_or_404(skill_id)  # validate the skill exists
    changelog_path = _skill_dir(skill_id) / "CHANGELOG.md"
    if not changelog_path.is_file():
        return {"skill_id": skill_id, "changelog": None}
    size = changelog_path.stat().st_size
    if size > _MAX_CHANGELOG_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "changelog_too_large",
                "skill_id": skill_id,
                "size_bytes": size,
                "max_bytes": _MAX_CHANGELOG_BYTES,
                "hint": (
                    f"CHANGELOG.md for skill {skill_id!r} is {size} bytes "
                    f"(>{_MAX_CHANGELOG_BYTES}); read the file directly "
                    f"instead of through this endpoint."
                ),
            },
        )
    return {"skill_id": skill_id, "changelog": changelog_path.read_text(encoding="utf-8")}


@router.post("/skills/reload")
async def reload_skills(request: Request):
    """Auth-gated hot reload of all skill manifests (dev convenience).

    Re-reads every cached manifest from disk so a skill author can edit YAML
    and pick up the change without a server restart.

    Disabled outside development/staging environments: hot-reloading manifests
    on a production server can swap the validated command policy / promotion
    target out from under in-flight sessions. The router already requires a
    valid API token; this guard adds the dev-only constraint.
    """
    if settings.environment == "production":
        await _audit(
            request,
            action="skills.reload",
            outcome="denied",
            metadata={"reason": "prod_disabled", "environment": settings.environment},
            error_message="skills.reload disabled in production",
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "skills_reload_prod_disabled",
                "environment": settings.environment,
                "hint": (
                    "Hot-reloading skill manifests is a development convenience "
                    "and is disabled in production. Restart the service to pick "
                    "up manifest changes."
                ),
            },
        )
    count = _registry.reload_all()
    await _audit(
        request,
        action="skills.reload",
        outcome="success",
        metadata={"reloaded": count, "available": _registry.available()},
    )
    return {
        "status": "ok",
        "reloaded": count,
        "available": _registry.available(),
    }


# ------------------------------------------------------------------
# Skill generation (P2 Skill SDK — the API face of `autoresearch new-skill`)
# ------------------------------------------------------------------


class GenerateSkillRequest(BaseModel):
    """Body for ``POST /skills/generate``."""

    goal: str = Field(
        min_length=8,
        description="Natural-language description of the research domain.",
    )
    skill_id: Optional[str] = Field(
        default=None,
        description="Override the generated kebab-case skill id.",
    )
    provider: Literal["anthropic", "openai"] = Field(default="anthropic")
    model: Optional[str] = Field(
        default=None,
        description="Model id (default: settings.anthropic_model).",
    )


@router.post("/skills/generate", status_code=201)
async def generate_skill(body: GenerateSkillRequest, request: Request):
    """Draft a new skill package from a goal (P2 Skill SDK).

    The ``autoresearch new-skill`` CLI parity endpoint for UIs. Feature-flagged
    (``AUTORESEARCH_SKILL_GENERATOR_ENABLED``): generation spends real LLM
    tokens and writes a validated-but-untrusted draft into
    ``skills/_drafts/<id>/`` — off by default, operator opt-in. Promotion of a
    draft into the live tree stays an operator act (CLI ``promote-skill``);
    this endpoint never moves files.
    """
    from src.core.llm_provider import build_provider
    from src.core.skill_generator import (
        SkillGenerationError,
        SkillGenerator,
    )

    if not settings.skill_generator_enabled:
        await _audit(
            request,
            action="skills.generate",
            outcome="denied",
            metadata={"reason": "flag_disabled"},
            error_message="skill generator is disabled",
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "skill_generator_disabled",
                "hint": (
                    "Set AUTORESEARCH_SKILL_GENERATOR_ENABLED=true to expose "
                    "LLM skill generation (it spends tokens and writes "
                    "drafts into skills/_drafts/)."
                ),
            },
        )
    model = body.model or settings.anthropic_model
    try:
        provider = build_provider(body.provider)
        draft = await SkillGenerator().generate(
            description=body.goal,
            provider=provider,
            model=model,
            skill_id=body.skill_id,
        )
    except SkillGenerationError as exc:
        await _audit(
            request,
            action="skills.generate",
            outcome="failure",
            metadata={"goal": body.goal[:200]},
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=422,
            detail={"error": "skill_generation_failed", "reason": str(exc)},
        ) from exc
    except Exception as exc:  # noqa: BLE001 — provider/credential failures
        await _audit(
            request,
            action="skills.generate",
            outcome="failure",
            metadata={"goal": body.goal[:200]},
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "skill_generator_unavailable",
                "reason": str(exc),
                "hint": "generation needs real LLM credentials configured.",
            },
        ) from exc
    await _audit(
        request,
        action="skills.generate",
        outcome="success",
        metadata={
            "skill_id": draft.skill_id,
            "findings": len(draft.policy_findings),
            "critical": sum(
                1 for f in draft.policy_findings if f.severity == "critical"
            ),
        },
    )
    return {
        "skill_id": draft.skill_id,
        "draft_dir": str(draft.skill_dir),
        "files": [
            name
            for name, present in (
                ("SKILL.yaml", True),
                ("bootstrap.py", True),
                ("SKILL.md", bool(draft.skill_md)),
                ("eval/run.py", bool(draft.eval_run_py)),
            )
            if present
        ],
        "lifecycle_state": "draft",
        "policy_findings": [
            {
                "severity": f.severity,
                "reason": f.reason,
                "location": f.location,
            }
            for f in draft.policy_findings
        ],
        "next": (
            "Review the draft, then promote via the CLI: "
            f"autoresearch promote-skill --id {draft.skill_id}"
        ),
    }
