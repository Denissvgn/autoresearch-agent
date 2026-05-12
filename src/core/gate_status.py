"""Compatibility helpers for autoresearch gate-status fields."""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping, MutableMapping, Optional

_TRUE_VALUES = {"true", "1", "yes", "y", "passed", "pass"}
_FALSE_VALUES = {"false", "0", "no", "n", "failed", "fail"}


def coerce_bool(value: Any, default: bool = False) -> bool:
    """Coerce common marker/API bool encodings to a real bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE_VALUES:
            return True
        if lowered in _FALSE_VALUES:
            return False
    return default


def parse_metrics_payload(raw: Any) -> dict[str, Any]:
    """Return a metrics_json payload as a mapping, or an empty dict."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def training_gates_passed_from(
    payload: Mapping[str, Any],
    *,
    default: bool = False,
) -> bool:
    """Read the canonical training-gates flag with legacy fallback."""
    if "training_gates_passed" in payload:
        return coerce_bool(payload.get("training_gates_passed"), default)
    if "all_gates_passed" in payload:
        return coerce_bool(payload.get("all_gates_passed"), default)
    return default


def training_gates_passed_from_iteration(
    row: Mapping[str, Any],
    *,
    default: bool = False,
) -> bool:
    """Read training gates from an iteration row and its metrics_json."""
    metrics = parse_metrics_payload(row.get("metrics_json"))
    if "training_gates_passed" in metrics or "all_gates_passed" in metrics:
        return training_gates_passed_from(metrics, default=default)
    return training_gates_passed_from(row, default=default)


def normalize_training_gate_aliases(
    payload: MutableMapping[str, Any],
    *,
    legacy_value: Any = None,
    default: bool = False,
    logger: Optional[logging.Logger] = None,
    context: str = "",
) -> bool:
    """Populate canonical and legacy training gate keys on a mutable payload.

    ``training_gates_passed`` is authoritative. ``all_gates_passed`` remains a
    compatibility alias while older markers and DB rows migrate.
    """
    has_training = "training_gates_passed" in payload
    has_legacy = "all_gates_passed" in payload

    if has_training:
        training = coerce_bool(payload.get("training_gates_passed"), default)
        if has_legacy:
            legacy = coerce_bool(payload.get("all_gates_passed"), default)
            if legacy != training and logger is not None:
                suffix = f" for {context}" if context else ""
                logger.warning(
                    "Conflicting gate aliases%s: training_gates_passed=%s "
                    "all_gates_passed=%s; using training_gates_passed",
                    suffix,
                    training,
                    legacy,
                )
    elif has_legacy:
        training = coerce_bool(payload.get("all_gates_passed"), default)
    elif legacy_value is not None:
        training = coerce_bool(legacy_value, default)
    else:
        training = default

    payload["training_gates_passed"] = training
    payload["all_gates_passed"] = training
    return training


def consistency_report_passed(report: Any) -> Optional[bool]:
    """Return report.passed when a consistency report mapping is available."""
    parsed = parse_metrics_payload(report)
    if not parsed:
        return None
    return coerce_bool(parsed.get("passed"), False)
