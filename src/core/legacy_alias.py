"""Legacy alias registry — ``model_type ↔ skill_id`` (ARC-011 P2-019).

The back-compat bridge between the legacy ``model_type`` field
(``direction``/``volatility``/``rl``) and the canonical ``skill_id``
(``ml-direction``/``ml-volatility``/``ml-rl``). Legacy API callers that send
``model_type`` (ARC-011 §10 guarantee #5) are auto-translated to ``skill_id``
here; the orchestrator and SkillRuntime reach for ``skill_id`` only.

Design note (P1-007 house style):

* The canonical manifest skill ids (``ml-direction`` etc.) are distinct from the
  legacy on-disk primer directory names (``direction-autotuner`` etc.) the
  transitional ``_SKILL_IDENTITY`` map in ``skill_runtime.py`` uses. This module
  owns the ``model_type ↔ manifest skill_id`` mapping; the primer-dir mapping
  is transitional and retired by P2-021. The two are reconciled here so callers
  can pass either form.
"""

from __future__ import annotations

#: Legacy ``model_type`` → canonical manifest ``skill_id``.
_MODEL_TYPE_TO_SKILL_ID: dict[str, str] = {
    "direction": "ml-direction",
    "volatility": "ml-volatility",
    "rl": "ml-rl",
}

#: Reverse lookup (canonical manifest ``skill_id`` → legacy ``model_type``).
_SKILL_ID_TO_MODEL_TYPE: dict[str, str] = {v: k for k, v in _MODEL_TYPE_TO_SKILL_ID.items()}


def model_type_to_skill_id(model_type: str) -> str:
    """Translate a legacy ``model_type`` to its canonical ``skill_id``.

    Known legacy values map to their canonical skill ids; any other non-empty
    value is already a canonical ``skill_id`` and is returned unchanged
    (``skill_id`` is the universal vocabulary — non-legacy skills are their own
    ``model_type`` alias). Empty string stays empty.
    """
    if not model_type:
        return ""
    return _MODEL_TYPE_TO_SKILL_ID.get(model_type, model_type)


def skill_id_to_model_type(skill_id: str) -> str:
    """Translate a canonical ``skill_id`` back to its legacy ``model_type``.

    Known canonical ids map to their legacy short names; any other non-empty
    id is its own ``model_type`` alias (empty string stays empty).
    """
    if not skill_id:
        return ""
    return _SKILL_ID_TO_MODEL_TYPE.get(skill_id, skill_id)


def is_known_model_type(model_type: str) -> bool:
    """Whether ``model_type`` maps to a Phase-2 skill (excludes ``pipeline``)."""
    return model_type in _MODEL_TYPE_TO_SKILL_ID


__all__ = [
    "model_type_to_skill_id",
    "skill_id_to_model_type",
    "is_known_model_type",
]
