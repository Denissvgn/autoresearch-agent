"""Skill descriptor endpoints — the generic skill API surface (ARC-011 P3-001..008, P3-011).

A new research domain is added by dropping a ``skills/<id>/`` directory and
reloading — **zero orchestrator or UI code changes** (ARC-011 §7.14). This
module exposes the installed skill manifests to the UI and API clients so the
*same* NewResearch form, MetricsChart, IterationsTable, and PromotionModal can
render any skill from descriptor data alone (GEN-003, §8.3).

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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.audit import record_api_audit_event
from src.api.auth import require_api_auth
from src.config import settings
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
    dump["links"] = {
        "self": f"/skills/{manifest.id}",
        "param_schema": f"/skills/{manifest.id}/param-schema",
        "form_fields": f"/skills/{manifest.id}/form-fields",
        "metric_schema": f"/skills/{manifest.id}/metric-schema",
        "versions": f"/skills/{manifest.id}/versions",
        "changelog": f"/skills/{manifest.id}/changelog",
    }
    return dump


def _form_fields(manifest: ResearchSkillManifest) -> List[Dict[str, Any]]:
    """UI form-field definitions for ``GET /skills/{id}/form-fields`` (P3-004).

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
    """List installed skill summaries (GEN-003).

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
    """The ``param_schema`` JSON Schema for ``skill_params`` validation (P3-003)."""
    manifest = _get_or_404(skill_id)
    return manifest.param_schema.model_dump(exclude_none=True, mode="json")


@router.get("/skills/{skill_id}/form-fields")
async def get_skill_form_fields(skill_id: str):
    """UI form-field definitions for the dynamic form renderer (P3-004, P3-022)."""
    manifest = _get_or_404(skill_id)
    return {"skill_id": skill_id, "form_fields": _form_fields(manifest)}


@router.get("/skills/{skill_id}/metric-schema")
async def get_skill_metric_schema(skill_id: str):
    """The ``metric_schema`` — primary metric, gates, chart series, table columns (P3-005)."""
    manifest = _get_or_404(skill_id)
    return manifest.metric_schema.model_dump(exclude_none=True, mode="json")


@router.get("/skills/{skill_id}/versions")
async def get_skill_versions(skill_id: str):
    """Declared skill versions (P3-006)."""
    manifest = _get_or_404(skill_id)
    return {
        "skill_id": skill_id,
        "versions": [
            {
                "version": manifest.version,
                "schema_version": manifest.schema_version,
                "current": True,
            }
        ],
    }


@router.get("/skills/{skill_id}/changelog")
async def get_skill_changelog(skill_id: str):
    """The skill's ``CHANGELOG.md`` content (P3-007).

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
    """Auth-gated hot reload of all skill manifests (dev convenience, P3-008).

    Re-reads every cached manifest from disk so a skill author can edit YAML
    and pick up the change without a server restart.

    Disabled outside development/staging environments: hot-reloading manifests
    on a production server can swap the validated command policy / promotion
    target out from under in-flight sessions. The router already requires a
    valid API token; this guard adds the dev-only constraint (P3-008 AC).
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
