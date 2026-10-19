"""Run/attempt-scoped credentials for attached agents.

An attached agent authenticates with a short-lived, signed credential that
is scoped to one run (or attempt) and carries only research permissions.
Scoped authority is deliberately distinct from operator and promotion-
approver authority: those permissions cannot be granted to a scoped
credential at all. Revocation covers the service's lifetime; expiry bounds
what revocation cannot.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

PERM_READ = "read"
PERM_SUBMIT = "submit"
PERM_EVALUATE = "evaluate"
PERM_LIFECYCLE = "lifecycle"
SCOPED_PERMISSIONS = frozenset(
    {PERM_READ, PERM_SUBMIT, PERM_EVALUATE, PERM_LIFECYCLE}
)

# Authority an attached agent must never hold.
NON_GRANTABLE_PERMISSIONS = frozenset(
    {"operator", "admin", "promote:approve", "settings", "evidence:declare"}
)


class ScopedAuthError(Exception):
    """A scoped credential was refused."""


class CredentialExpired(ScopedAuthError):
    """The credential's short lifetime has passed."""


class CredentialRevoked(ScopedAuthError):
    """The credential was explicitly revoked."""


class CredentialDenied(ScopedAuthError):
    """The credential's scope or permissions do not allow this operation."""


@dataclass(frozen=True)
class ScopedPrincipal:
    """The verified attached-agent identity behind a scoped credential."""

    token_id: str
    subject: str
    run_id: str
    tenant_id: str
    permissions: frozenset[str]
    expires_at: float


_REVOKED: set[str] = set()


def issue_scoped_credential(
    *,
    subject: str,
    run_id: str,
    tenant_id: str = "default",
    permissions: Iterable[str] = (PERM_READ, PERM_SUBMIT, PERM_EVALUATE),
    ttl_s: float = 900.0,
    key: str,
    now: Optional[float] = None,
) -> str:
    """Issue a signed, short-lived, run-scoped credential.

    Operator and promotion-approver authority cannot be granted here.
    """
    granted = frozenset(permissions)
    illegal = granted & NON_GRANTABLE_PERMISSIONS
    if illegal:
        raise CredentialDenied(
            f"scoped credentials cannot carry: {sorted(illegal)}"
        )
    unknown = granted - SCOPED_PERMISSIONS
    if unknown:
        raise CredentialDenied(f"unknown permissions: {sorted(unknown)}")
    issued_at = time.time() if now is None else now
    payload = {
        "token_id": secrets.token_hex(8),
        "subject": subject,
        "run_id": run_id,
        "tenant_id": tenant_id,
        "permissions": sorted(granted),
        "issued_at": issued_at,
        "expires_at": issued_at + ttl_s,
    }
    return _encode(payload, key)


def revoke_scoped_credential(token: str, *, key: str) -> str:
    """Revoke a credential by id (service-lifetime revocation)."""
    payload = _decode(token, key)
    token_id = str(payload["token_id"])
    _REVOKED.add(token_id)
    return token_id


def verify_scoped_credential(
    token: str,
    *,
    key: str,
    run_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    required_permissions: Iterable[str] = (),
    now: Optional[float] = None,
) -> ScopedPrincipal:
    """Verify a scoped credential against the operation it guards."""
    payload = _decode(token, key)
    current = time.time() if now is None else now
    token_id = str(payload["token_id"])
    if token_id in _REVOKED:
        raise CredentialRevoked(f"credential {token_id} was revoked")
    if current >= float(payload["expires_at"]):
        raise CredentialExpired(f"credential {token_id} has expired")
    if run_id is not None and payload["run_id"] != run_id:
        raise CredentialDenied("credential is scoped to a different run")
    if tenant_id is not None and payload["tenant_id"] != tenant_id:
        raise CredentialDenied("credential belongs to a different tenant")
    permissions = frozenset(payload["permissions"])
    missing = frozenset(required_permissions) - permissions
    if missing:
        raise CredentialDenied(f"missing permissions: {sorted(missing)}")
    return ScopedPrincipal(
        token_id=token_id,
        subject=str(payload["subject"]),
        run_id=str(payload["run_id"]),
        tenant_id=str(payload["tenant_id"]),
        permissions=permissions,
        expires_at=float(payload["expires_at"]),
    )


def _encode(payload: Mapping[str, Any], key: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(
        key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{body}.{signature}"


def _decode(token: str, key: str) -> dict[str, Any]:
    try:
        body, signature = token.rsplit(".", 1)
    except ValueError:
        raise CredentialDenied("malformed credential") from None
    expected = hmac.new(
        key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise CredentialDenied("credential signature is invalid")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise CredentialDenied("malformed credential") from None
    for field in ("token_id", "subject", "run_id", "permissions", "expires_at"):
        if field not in payload:
            raise CredentialDenied(f"credential missing {field}")
    return payload


def clear_revocations() -> None:
    """Test hook: forget revocations (short-lived tokens expire anyway)."""
    _REVOKED.clear()


__all__ = [
    "CredentialDenied",
    "CredentialExpired",
    "CredentialRevoked",
    "NON_GRANTABLE_PERMISSIONS",
    "PERM_EVALUATE",
    "PERM_LIFECYCLE",
    "PERM_READ",
    "PERM_SUBMIT",
    "SCOPED_PERMISSIONS",
    "ScopedAuthError",
    "ScopedPrincipal",
    "clear_revocations",
    "issue_scoped_credential",
    "revoke_scoped_credential",
    "verify_scoped_credential",
]