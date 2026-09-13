"""Subject & variant enumeration endpoints (ARC-011 P3-009, P3-010, P3-011).

A *subject* is the entity a research session tunes (an instrument for ML skills,
a database for db-config-tuning, a code repo for code-refactor). A *variant* is
a per-subject sweep dimension (a timeframe, a question set, etc.). Together
they replace the legacy hardcoded ``instrument`` / ``timeframe`` pair with a
generic, skill-declared enumeration (G12).

Endpoints (all under ``/api/v1``):

* ``GET /subjects?skill_id=…``                — subjects for a skill
* ``GET /subjects/{subject_id}/variants?skill_id=…``  — variants for a subject

The legacy ``GET /instruments`` alias was removed with the trading-skills
cleanup; the canonical skill-parameterized ``GET /subjects`` surface below
is the only enumeration API.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import require_api_auth
from src.config import settings
from src.core.skill_manifest import ResearchSkillManifest
from src.core.skill_registry import (
    SkillNotRegisteredError,
    SkillRegistry,
    default_registry,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["subjects"], dependencies=[Depends(require_api_auth)])

_registry: SkillRegistry = default_registry


def init(registry: Optional[SkillRegistry] = None) -> None:
    global _registry
    if registry is not None:
        _registry = registry


def _get_manifest_or_404(skill_id: str) -> ResearchSkillManifest:
    """Load a manifest by id, raising 404 with the installable-skills hint.

    Mirrors ``skills._get_or_404`` so the two endpoints that take a
    ``skill_id`` (``/skills/{id}`` and ``/subjects?skill_id=…``) return the
    same structured 404 detail shape (``error``/``skill_id``/``available``/
    ``hint``) for an unknown skill.
    """
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


def _enumerate_subjects(manifest: ResearchSkillManifest) -> List[Dict[str, Any]]:
    """Resolve a skill's subject list.

    Priority: ``subjects.static`` (inline) → config-file glob fall-back for ML
    skills → empty list. The full enumerator-subprocess execution is deferred;
    this keeps the API responsive and testable.
    """
    subjects_cfg = manifest.subjects
    if subjects_cfg is None:
        return []
    if subjects_cfg.static:
        return [
            {"id": s.id, "label": s.label or s.id}
            for s in subjects_cfg.static
        ]
    return []


def _enumerate_variants(manifest: ResearchSkillManifest, subject_id: str) -> List[str]:
    """Resolve a skill's variant list for a given subject."""
    variants_cfg = manifest.variants
    if variants_cfg is None:
        return []
    if variants_cfg.static:
        return list(variants_cfg.static)
    return []


@router.get("/subjects")
async def list_subjects(skill_id: str) -> List[Dict[str, Any]]:
    """List subjects for a skill (P3-009)."""
    manifest = _get_manifest_or_404(skill_id)
    return _enumerate_subjects(manifest)


@router.get("/subjects/{subject_id}/variants")
async def list_subject_variants(subject_id: str, skill_id: str) -> Dict[str, Any]:
    """List variants for a subject under a skill (P3-010)."""
    manifest = _get_manifest_or_404(skill_id)
    variants = _enumerate_variants(manifest, subject_id)
    return {"skill_id": skill_id, "subject_id": subject_id, "variants": variants}
