"""Subject & variant enumeration endpoints (ARC-011 P3-009, P3-010, P3-011).

A *subject* is the entity a research session tunes (an instrument for ML skills,
a database for db-config-tuning, a code repo for code-refactor). A *variant* is
a per-subject sweep dimension (a timeframe, a question set, etc.). Together
they replace the legacy hardcoded ``instrument`` / ``timeframe`` pair with a
generic, skill-declared enumeration (G12).

Endpoints (all under ``/api/v1``):

* ``GET /subjects?skill_id=…``                — subjects for a skill
* ``GET /subjects/{subject_id}/variants?skill_id=…``  — variants for a subject

The legacy ``GET /instruments`` endpoint stays in ``research.py`` (§10
guarantee #5) and is unaffected; this module adds the canonical
skill-parameterized surface.
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
    return _legacy_instrument_glob(manifest)


def _legacy_instrument_glob(manifest: ResearchSkillManifest) -> List[Dict[str, Any]]:
    """Fall-back subject enumeration for ML skills: glob instrument config files.

    Mirrors the existing ``GET /instruments`` logic so ML skills that declare
    ``subjects.enumerator: scripts/list_subjects.py`` still get a useful list
    without a subprocess call.
    """
    import glob
    import os

    subjects: List[Dict[str, Any]] = []
    instrument_dir = os.path.join(settings.configs_dir, "instrument_configs")
    if os.path.isdir(instrument_dir):
        for path in sorted(glob.glob(os.path.join(instrument_dir, "*.yaml"))):
            filename = os.path.basename(path)
            name = filename.rsplit(".", 1)[0]
            parts = name.rsplit("_", 1)
            if len(parts) == 2 and parts[1] in (
                "1m", "5m", "15m", "30m", "1h", "4h", "1d",
            ):
                instrument = "_".join(parts[0].split("_")[:2])
                subjects.append({"id": instrument, "label": instrument})
            else:
                subjects.append({"id": name, "label": name})
    seen: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for s in subjects:
        if s["id"] not in seen:
            seen.add(s["id"])
            unique.append(s)
    return unique


def _enumerate_variants(manifest: ResearchSkillManifest, subject_id: str) -> List[str]:
    """Resolve a skill's variant list for a given subject."""
    variants_cfg = manifest.variants
    if variants_cfg is None:
        return []
    if variants_cfg.static:
        return list(variants_cfg.static)
    return _legacy_timeframe_glob(manifest, subject_id)


def _legacy_timeframe_glob(
    manifest: ResearchSkillManifest, subject_id: str
) -> List[str]:
    """Fall-back variant enumeration for ML skills: derive timeframes from
    instrument config filenames."""
    import glob
    import os

    instrument_dir = os.path.join(settings.configs_dir, "instrument_configs")
    timeframes: List[str] = []
    if os.path.isdir(instrument_dir):
        for path in sorted(glob.glob(os.path.join(instrument_dir, "*.yaml"))):
            filename = os.path.basename(path)
            name = filename.rsplit(".", 1)[0]
            parts = name.rsplit("_", 1)
            if len(parts) == 2:
                instrument = "_".join(parts[0].split("_")[:2])
                if instrument == subject_id and parts[1] in (
                    "1m", "5m", "15m", "30m", "1h", "4h", "1d",
                ):
                    timeframes.append(parts[1])
    return timeframes or ["5m", "15m", "1h", "4h"]


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
