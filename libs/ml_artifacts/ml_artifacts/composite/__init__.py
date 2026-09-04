"""Composite manifest compatibility helpers."""

from .manifest import (
    COMPONENT_ROLES,
    component_ref_to_string,
    normalize_component_refs,
)

__all__ = [
    "COMPONENT_ROLES",
    "component_ref_to_string",
    "normalize_component_refs",
]
