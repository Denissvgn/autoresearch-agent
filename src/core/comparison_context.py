"""Comparable-context identity for result ranking.

Results rank only within one comparable context: the same objective and
units, the same dataset/scorer/fidelity pins, and matching subject and
variant constraints. Sessions whose context is unknown (legacy rows, or
runs that recorded no pins) stay in their own group — never merged into
a shared champion table, where a differing scorer or dataset could
manufacture a misleading winner.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Optional

COMPARISON_CONTEXT_SCHEMA = "comparison-context.v1"

_PIN_KEYS = ("dataset", "scorer", "fidelity")


def build_comparison_context(
    *,
    objective: str,
    units: str,
    subject: Optional[str] = None,
    variant: Optional[str] = None,
    pins: Optional[Mapping[str, Any]] = None,
) -> str:
    """Canonical, ordered identity: the grouping key for rankings.

    Missing pins are recorded as the explicit value ``"unknown"`` so a
    partially known context is distinguishable from a fully pinned one.
    """
    source = dict(pins or {})
    identity = {
        "schema": COMPARISON_CONTEXT_SCHEMA,
        "objective": objective or "unknown",
        "units": units or "unknown",
        "dataset": str(source.get("dataset") or "unknown"),
        "scorer": str(source.get("scorer") or "unknown"),
        "fidelity": str(source.get("fidelity") or "unknown"),
        "subject": subject or "any",
        "variant": variant or "any",
    }
    return json.dumps(identity, sort_keys=True, separators=(",", ":"))


def describe_comparison_context(context: Optional[str]) -> dict[str, Any]:
    """The label a ranking surface shows for one comparable group."""
    if not context:
        return {
            "context": None,
            "label": "unknown / legacy context",
            "known": False,
        }
    try:
        parsed = json.loads(context)
    except Exception:
        return {
            "context": context,
            "label": "unparseable context",
            "known": False,
        }
    parts = [
        f"objective={parsed.get('objective', 'unknown')}",
        f"units={parsed.get('units', 'unknown')}",
    ]
    for key in _PIN_KEYS:
        value = parsed.get(key, "unknown")
        if value != "unknown":
            parts.append(f"{key}={value}")
    if parsed.get("subject") not in (None, "any"):
        parts.append(f"subject={parsed['subject']}")
    if parsed.get("variant") not in (None, "any"):
        parts.append(f"variant={parsed['variant']}")
    return {"context": parsed, "label": ", ".join(parts), "known": True}
