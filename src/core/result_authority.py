"""Authoritative evaluator results: receipts, verification, and honest labels.

Model-visible nonces never establish authority: the W11 echo check only
shows that a payload passed through a context that had seen the nonce.
This module binds result content to the server-created attempt and the
exact candidate/evaluator/dataset identities, and issues a receipt over
that binding so any change to metric, gate, candidate, or attempt identity
invalidates it. The receipt mirrors the kernel ``ResultReceipt`` contract
(``execution_contracts``) field-for-field so it can lift across a trust
boundary later; for local execution the trusted evaluator-to-server channel
is the authority and the receipt provides tamper evidence, replay
protection, and idempotent delivery.

Authority labels recorded on every ingested result (honest, never upgraded
retroactively):

* ``receipt_verified`` — delivered through the trusted evaluator channel
  and bound by an issued receipt.
* ``model_proposed`` — authored in model output; annotations/proposals
  only, regardless of any echoed nonce.
* ``unverified_imported`` — third-party or non-evaluator content.
* ``nonce_only`` — legacy echo-verification provenance with no receipt.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any, Mapping, Optional, Sequence

from src.core.execution_contracts import canonical_digest

RECEIPT_SCHEMA_VERSION = "autoresearch_result_receipt.v1"

AUTHORITY_RECEIPT_VERIFIED = "receipt_verified"
AUTHORITY_MODEL_PROPOSED = "model_proposed"
AUTHORITY_UNVERIFIED_IMPORTED = "unverified_imported"
AUTHORITY_NONCE_ONLY = "nonce_only"

#: Marker fields that make up the authoritative result content: the
#: metric, the gate outcome, and the scored candidate snapshot. Anything a
#: receipt binds must live here so tampering with it invalidates the
#: receipt.
VERIFIED_RESULT_FIELDS = (
    "primary_metric",
    "metric_name",
    "training_gates_passed",
    "all_gates_passed",
    "status",
    "artifact_hash",
    "canonical_config_hash",
    "config_snapshot_sha256",
    "trial_identity_hash",
)


def result_payload(marker: Mapping[str, Any]) -> dict[str, Any]:
    """The canonical verified-content subset of a result marker."""

    payload: dict[str, Any] = {}
    for field in VERIFIED_RESULT_FIELDS:
        if field in marker and marker[field] is not None:
            payload[field] = marker[field]
    return payload


def protected_result_names(extension: Mapping[str, Any]) -> tuple[str, ...]:
    """Names candidate file tools must never write.

    The declared result channel (marker/result handoff files) is written by
    the pinned evaluator subprocess only — a candidate-written result file
    is forgery. Evaluation data and the standard ``results.json`` handoff
    are included.
    """

    return (
        tuple(extension.get("write_protected_files") or ())
        + tuple(extension.get("output_files") or ())
        + ("results.json",)
    )


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _receipt_material(receipt: Mapping[str, Any]) -> bytes:
    # Deterministic over the bound envelope and ownership — deliberately
    # excluding the per-issue nonce so re-issuing identical content yields
    # the same receipt id (idempotent duplicate delivery).
    return _canonical(
        {
            "envelope_digest": receipt.get("envelope_digest"),
            "ownership_epoch": receipt.get("ownership_epoch"),
            "sequence": receipt.get("sequence"),
            "attempt_id": receipt.get("attempt_id"),
            "candidate_digest": receipt.get("candidate_digest"),
            "evaluator_digest": receipt.get("evaluator_digest"),
            "dataset_digests": list(receipt.get("dataset_digests") or ()),
        }
    )


def _receipt_id(material: bytes, key: Optional[str]) -> str:
    if key:
        digest = hmac.new(key.encode("utf-8"), material, hashlib.sha256).hexdigest()
        return f"hmac-sha256:{digest}"
    digest = hashlib.sha256(material).hexdigest()
    return f"sha256:{digest}"


def issue_result_receipt(
    *,
    payload: Mapping[str, Any],
    attempt_id: str,
    candidate_digest: str,
    evaluator_digest: str,
    dataset_digests: Sequence[str],
    ownership_epoch: int,
    sequence: int,
    key: Optional[str] = None,
) -> dict[str, Any]:
    """Issue the receipt binding one result to one attempt.

    ``receipt_id`` is deterministic over the bound envelope (idempotent:
    re-issuing for identical content yields the same id, so duplicate
    delivery cannot create a second result) and becomes an HMAC when a
    server-side ``key`` is configured — the authenticated form used when
    results cross a trust boundary. ``nonce`` is server-generated and
    never model-visible.
    """

    envelope = {
        "payload": dict(payload),
        "attempt_id": attempt_id,
        "candidate_digest": candidate_digest,
        "evaluator_digest": evaluator_digest,
        "dataset_digests": list(dataset_digests),
    }
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "nonce": secrets.token_hex(16),
        "ownership_epoch": int(ownership_epoch),
        "sequence": int(sequence),
        "envelope_digest": canonical_digest(envelope),
        "attempt_id": attempt_id,
        "candidate_digest": candidate_digest,
        "evaluator_digest": evaluator_digest,
        "dataset_digests": list(dataset_digests),
        "signing": "hmac-sha256-v1" if key else "sha256-v1",
    }
    receipt["receipt_id"] = _receipt_id(_receipt_material(receipt), key)
    return receipt


def verify_result_receipt(
    receipt: Mapping[str, Any],
    *,
    payload: Mapping[str, Any],
    attempt_id: Optional[str] = None,
    candidate_digest: Optional[str] = None,
    evaluator_digest: Optional[str] = None,
    dataset_digests: Optional[Sequence[str]] = None,
    key: Optional[str] = None,
) -> list[str]:
    """Validate a receipt against the content and identities it claims.

    Returns the list of violations (empty means the receipt holds):
    changing any metric, gate, candidate, or attempt identity changes the
    canonical envelope and invalidates ``envelope_digest``; presenting the
    receipt for a different attempt or candidate fails the binding check.
    """

    errors: list[str] = []
    bound_attempt = receipt.get("attempt_id")
    if attempt_id is not None and attempt_id != bound_attempt:
        errors.append(
            f"receipt belongs to attempt {bound_attempt!r}, not {attempt_id!r}"
        )
    bound_candidate = receipt.get("candidate_digest")
    if candidate_digest is not None and candidate_digest != bound_candidate:
        errors.append("receipt candidate identity does not match")
    bound_evaluator = receipt.get("evaluator_digest")
    if evaluator_digest is not None and evaluator_digest != bound_evaluator:
        errors.append("receipt evaluator identity does not match")
    bound_datasets = list(receipt.get("dataset_digests") or ())
    if dataset_digests is not None and list(dataset_digests) != bound_datasets:
        errors.append("receipt dataset identities do not match")

    envelope = {
        "payload": dict(payload),
        "attempt_id": bound_attempt,
        "candidate_digest": bound_candidate,
        "evaluator_digest": bound_evaluator,
        "dataset_digests": bound_datasets,
    }
    if canonical_digest(envelope) != receipt.get("envelope_digest"):
        errors.append("result content does not match the receipt envelope")
    if _receipt_id(_receipt_material(receipt), key) != receipt.get("receipt_id"):
        errors.append("receipt id does not bind this envelope")
    return errors