"""Artifact reference normalization for autoresearch metadata."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


SENTINEL_ARTIFACT_STRINGS = frozenset({"", "none", "null", "n/a", "na"})

ARTIFACT_REFERENCE_KEYS = frozenset(
    {
        "mlflow_run_id",
        "artifact_hash",
        "model_artifact_hash",
        "artifact_uri",
        "result_artifact_path",
        "result_artifact_sha256",
        "feature_schema_hash",
        "schema_hash",
        "data_hash",
        "dataset_hash",
        "rl_economic_replay_artifact_hash",
        "economic_replay_artifact_hash",
        "replay_artifact_hash",
        "feature_bundle_hash",
        "rl_feature_bundle_hash",
    }
)


def normalize_optional_artifact_ref(value: Any) -> str | None:
    """Return a real artifact reference string or None for sentinel values."""

    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in SENTINEL_ARTIFACT_STRINGS:
        return None
    return text


def is_sentinel_artifact_ref(value: Any) -> bool:
    """Return True when an explicit artifact reference value is a sentinel."""

    return (
        isinstance(value, str)
        and value.strip().lower() in SENTINEL_ARTIFACT_STRINGS
    )


def first_valid_artifact_ref(*values: Any) -> str | None:
    """Return the first normalized artifact reference from candidates."""

    for value in values:
        normalized = normalize_optional_artifact_ref(value)
        if normalized:
            return normalized
    return None


def normalize_artifact_references_in_mapping(
    payload: MutableMapping[str, Any],
    *,
    keys: frozenset[str] = ARTIFACT_REFERENCE_KEYS,
) -> bool:
    """Normalize known artifact-reference fields in a nested mapping.

    Returns True when at least one value changed.
    """

    changed = False

    def visit(value: Any) -> None:
        nonlocal changed
        if isinstance(value, MutableMapping):
            for key, item in list(value.items()):
                if key in keys:
                    normalized = normalize_optional_artifact_ref(item)
                    if normalized != item:
                        value[key] = normalized
                        changed = True
                visit(value.get(key))
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return changed
