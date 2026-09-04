"""Normalize composite manifest component references across service versions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

COMPONENT_ROLES = ("direction", "volatility", "rl_agent")

_FLAT_KEYS = {
    "direction": ("direction_model_version",),
    "volatility": ("volatility_model_version",),
    "rl_agent": ("rl_agent_version", "rl_model_version"),
}

_NESTED_KEYS = {
    "direction": ("direction",),
    "volatility": ("volatility",),
    "rl_agent": ("rl_agent", "rl"),
}


def component_ref_to_string(model_name: Any, version: Any) -> str | None:
    """Return ``model_name:version`` when both parts are present."""
    if model_name in (None, "") or version in (None, ""):
        return None
    return f"{model_name}:{version}"


def normalize_component_refs(manifest: Mapping[str, Any] | None) -> dict[str, str | None]:
    """Return canonical ``role -> model_name:version`` component refs.

    The trainer's canonical manifest stores nested components:
    ``components.direction.model_name`` and ``components.direction.version``.
    Older inference/mlflow-service payloads store flattened strings such as
    ``direction_model_version = "name:version"``.  This helper accepts both
    shapes and prefers nested component refs when present.
    """
    manifest = manifest or {}
    components = manifest.get("components")
    if not isinstance(components, Mapping):
        components = {}

    refs: dict[str, str | None] = {}
    for role in COMPONENT_ROLES:
        nested_ref = next(
            (
                ref
                for ref in (
                    _nested_component_ref(components.get(key))
                    for key in _NESTED_KEYS[role]
                )
                if ref is not None
            ),
            None,
        )
        refs[role] = nested_ref if nested_ref is not None else _flat_component_ref(manifest, role)
    return refs


def _nested_component_ref(component: Any) -> str | None:
    if not isinstance(component, Mapping):
        return None
    ref = component_ref_to_string(
        component.get("model_name") or component.get("name"),
        component.get("version") or component.get("model_version"),
    )
    if ref is not None:
        return ref
    raw = component.get("model_version_ref") or component.get("version_ref")
    return _valid_ref(raw)


def _flat_component_ref(manifest: Mapping[str, Any], role: str) -> str | None:
    for key in _FLAT_KEYS[role]:
        ref = _valid_ref(manifest.get(key))
        if ref is not None:
            return ref
    return None


def _valid_ref(value: Any) -> str | None:
    if value in (None, ""):
        return None
    ref = str(value)
    return ref if ":" in ref else None
