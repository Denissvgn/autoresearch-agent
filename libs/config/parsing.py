"""Shared lightweight parsing helpers for configuration values.

These functions provide consistent, tolerant parsing semantics across services.

Design principles:
- Accept already-parsed native types and return them unchanged.
- Handle common string coercions (bool/int/list) used in env + Vault sourced configs.
- Fail fast on obviously invalid integer conversions to surface misconfiguration early.
"""

from __future__ import annotations

from typing import Any, Iterable, List

__all__ = [
    "parse_bool",
    "parse_int",
    "parse_float",
    "parse_list",
]


def parse_bool(value: Any) -> bool:
    """Parse a boolean-ish value.

    Rules:
    - Booleans returned as-is.
    - Integers: 0 -> False, non-zero -> True.
    - Strings: case-insensitive membership in truthy / falsy sets.
    - Any other object -> bool(value) fallback.
    """
    if isinstance(value, bool):  # Fast path
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on", "y", "t"}:
            return True
        if lowered in {"false", "0", "no", "off", "n", "f"}:
            return False
        # Fallback: non-empty string truthiness
        return bool(lowered)
    return bool(value)


def parse_int(value: Any) -> int:
    """Parse an integer value.

    Accepts int (returned), float (truncated via int()), and digit-like strings.
    Raises ValueError on invalid string instead of silently swallowing errors to
    surface misconfiguration early.
    """
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        return int(stripped)  # Let ValueError propagate if not numeric
    raise ValueError(f"Cannot parse int from type {type(value)}: {value!r}")


def parse_float(value: Any) -> float:
    """Parse a floating-point value."""
    if isinstance(value, float):
        return value
    if isinstance(value, int):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        return float(stripped)
    raise ValueError(f"Cannot parse float from type {type(value)}: {value!r}")


def parse_list(value: Any, separator: str = ",") -> List[str]:
    """Parse a list of strings from a variety of inputs.

    Accepted inputs:
    - list/tuple/set of str -> normalized (stripped) list
    - comma-separated string (default) -> split + strip empties
    - single non-empty string without separator -> singleton list
    - None / empty string -> empty list
    Other types raise ValueError to surface misconfiguration.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        cleaned: list[str] = []
        for item in value:  # type: ignore[assignment]
            if not isinstance(item, str):
                raise ValueError(f"Non-string element in list: {item!r}")
            stripped = item.strip()
            if stripped:
                cleaned.append(stripped)
        return cleaned
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        parts = [p.strip() for p in raw.split(separator)]
        return [p for p in parts if p]
    raise ValueError(f"Cannot parse list from type {type(value)}: {value!r}")
