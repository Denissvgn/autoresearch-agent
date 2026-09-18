"""Pure production-approval v2 encoding and candidate binding (no I/O).

The HMAC covers the caller's candidate, never a substituted current winner.
Core confirmation must compare that candidate to its actual preview before writes.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

APPROVAL_METHOD = "hmac-sha256-v2"
APPROVAL_VERSION = "production-approval.v2"
CANDIDATE_FIELDS = ("iteration", "config_snapshot_sha256", "target_identity")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def canonical_json(value: Mapping[str, Any]) -> bytes:
    """Stable UTF-8 JSON: sorted keys, compact separators, ASCII escapes, no NaN."""
    return json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")


def target_identity(descriptor: Mapping[str, Any]) -> str:
    """Hash identity()'s kind/path/endpoint descriptor, excluding credentials."""
    kind = descriptor.get("kind")
    expected = {"kind", "target_path"}
    if kind == "webhook":
        expected.add("endpoint")
    elif kind != "file_path":
        raise ValueError("unsupported production approval target identity kind")
    if set(descriptor) != expected or any(
        not isinstance(descriptor.get(key), str) or not descriptor[key].strip()
        for key in expected
    ):
        raise ValueError("invalid production approval target identity descriptor")
    return hashlib.sha256(canonical_json(descriptor)).hexdigest()


def candidate_fields(candidate: Mapping[str, Any] | None) -> dict[str, Any]:
    """Require exact candidate types: integer iteration and lowercase SHA256s.

    The strict ``type(...) is int`` check is intentional: ``bool`` is a
    subclass of ``int`` in Python, and an approval for ``iteration=True``
    must never validate.
    """
    if not isinstance(candidate, Mapping):
        raise ValueError("production approval candidate is missing")
    iteration = candidate.get("iteration")
    if type(iteration) is not int or iteration < 0:  # noqa: E721 - bool must not pass as int
        raise ValueError(
            "production approval candidate iteration is missing or invalid"
        )
    for field in CANDIDATE_FIELDS[1:]:
        value = candidate.get(field)
        if not isinstance(value, str) or not _DIGEST.fullmatch(value):
            raise ValueError(
                f"production approval candidate {field} is missing or invalid"
            )
    return {field: candidate[field] for field in CANDIDATE_FIELDS}


def validate_candidate_binding(
    approval: Mapping[str, Any] | None, preview: Mapping[str, Any],
) -> None:
    """Fail closed if the approved candidate differs from the actual preview."""
    supplied = candidate_fields(approval)
    actual = candidate_fields(preview)
    for field in CANDIDATE_FIELDS:
        if supplied[field] != actual[field]:
            raise ValueError(
                f"production approval candidate mismatch: {field}; "
                "preview and re-sign"
            )


def canonical_approval_message(
    research_id: str, scope: str, approval: Mapping[str, Any],
) -> bytes:
    """Encode v2 signed provenance and candidate. Scope must already be canonical."""
    if scope != "production" or not research_id:
        raise ValueError("production approval requires canonical production scope and research_id")
    if approval.get("method") != APPROVAL_METHOD:
        raise ValueError("production approval requires hmac-sha256-v2; legacy signatures rejected")
    if approval.get("approved") is not True:
        raise ValueError("production approval requires approved=true")
    approver = approval.get("approver")
    reason = approval.get("reason")
    if not isinstance(approver, str) or not approver.strip():
        raise ValueError("production approval requires approver")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("production approval reason must be a string or null")
    return canonical_json({
        "version": APPROVAL_VERSION,
        "research_id": research_id,
        "scope": scope,
        "approved": True,
        "approver": approver,
        "method": APPROVAL_METHOD,
        "reason": reason,
        **candidate_fields(approval),
    })
