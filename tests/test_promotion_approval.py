"""P0-020 / P0-021 — Mandatory signed production approval bound to a candidate (W18 v2).

Exercises the four acceptance criteria from the ARC-011 backlog
(`docs/adr/ARC-011-backlog.md` §P0-020/P0-021) plus the v2 candidate binding:

  AC #1  ``POST /promote/confirm`` with ``scope=production`` and missing /
         ``false`` ``approval.approved`` → 4xx.
  AC #2  Approval requires a signature field, verified against a configured
         HMAC-SHA256 verifier (fail-closed when the verifier is unset).
  AC #3  Other scopes are unaffected by the verifier gate.
  AC #4  The ``promotion.confirm`` audit event records the approver identity.

  v2 (BREAKING): the signature covers a canonical stable-JSON message that
  includes the approved candidate — ``iteration`` +
  ``config_snapshot_sha256`` + ``target_identity`` — under method
  ``hmac-sha256-v2`` (``production-approval.v2``). The legacy
  ``"{research_id}:{scope}:{approver}"`` string is intentionally rejected so
  a captured legacy signature cannot approve a substituted candidate. The
  API verifies the *supplied* candidate; core binds it to the actual preview
  before any write.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from src.api import promotion as promotion_module
from src.api.promotion import (
    PromotionApproval,
    PromotionPreviewRequest,
    PromotionScopeRequest,
    _verify_production_approval_signature,
)
from src.config import settings
from src.core.promotion_approval import (
    APPROVAL_METHOD,
    canonical_approval_message,
    target_identity,
    validate_candidate_binding,
)

API_TOKEN = "test-autoresearch-token"
VERIFIER_SECRET = "test-verifier-secret"
RESEARCH_ID = "res_w18"
TARGET_PATH = "/srv/app/configs/prod/DOGE_USDT_15m.yaml"
CANDIDATE = {
    "iteration": 7,
    "config_snapshot_sha256": hashlib.sha256(b"best-iteration-yaml").hexdigest(),
    "target_identity": target_identity(
        {"kind": "file_path", "target_path": TARGET_PATH}
    ),
}


# ---------------------------------------------------------------------------
# Signature helper — mirrors the server's canonical v2 message exactly.
# ---------------------------------------------------------------------------


def sign_approval(
    research_id: str, scope: str, approval: dict
) -> str:
    """Compute the expected HMAC-SHA256 signature the way the server does."""
    message = canonical_approval_message(research_id, scope, approval)
    return hmac.new(VERIFIER_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()


def full_approval(**overrides) -> dict:
    """A structurally valid v2 approval over the fixed candidate."""
    approval = {
        "approved": True,
        "approver": "alice@example.com",
        "method": APPROVAL_METHOD,
        "reason": "gates passed",
        **CANDIDATE,
    }
    approval.update(overrides)
    return approval


def signed_approval(**overrides) -> dict:
    """A v2 approval whose signature is correct for the (possibly edited) fields."""
    approval = full_approval(**overrides)
    if "signature" not in approval:
        approval["signature"] = sign_approval(RESEARCH_ID, "production", approval)
    return approval


def production_approval_body(**overrides) -> dict:
    """A valid-shaped production approval body (signature defaults to correct)."""
    return {"scope": "production", "approval": signed_approval(**overrides)}


# ---------------------------------------------------------------------------
# Minimal app + fakes (self-contained; mirrors tests/test_api_auth.py scaffolding).
# ---------------------------------------------------------------------------


class FakeStore:
    """Captures audit events so AC #4 can inspect the recorded approver."""

    def __init__(self) -> None:
        self.audit_events: list[dict] = []

    async def list_promotions(self, **kwargs):
        return []

    async def record_audit_event(self, **kwargs):
        event = {
            "event_id": f"aud_fake_{len(self.audit_events) + 1}",
            "timestamp": "2026-07-04T00:00:00+00:00",
            **kwargs,
        }
        self.audit_events.append(event)
        return event


class FakePromoter:
    """Records confirm() invocations so tests can assert it was/wasn't reached."""

    def __init__(self) -> None:
        self.confirm_calls: list[dict] = []

    async def confirm(self, research_id: str, **kwargs):
        self.confirm_calls.append({"research_id": research_id, **kwargs})
        return {"research_id": research_id, "confirmed": True, **kwargs}

    async def preview(self, research_id: str, **kwargs):
        return {"research_id": research_id, "preview": True, **kwargs}


def create_test_app() -> FastAPI:
    app = FastAPI()
    for prefix in ("/api/v1", "/api"):
        app.include_router(promotion_module.router, prefix=prefix)
    return app


@pytest.fixture(autouse=True)
def configure_module(monkeypatch):
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)
    store = FakeStore()
    promotion_module.init(FakePromoter(), store)
    return store


@pytest.fixture
def client(configure_module: FakeStore) -> TestClient:
    return TestClient(create_test_app())


@pytest.fixture
def promoter(configure_module: FakeStore) -> FakePromoter:
    # The promoter is the first positional arg wired by promotion.init above.
    return promotion_module._promoter  # type: ignore[return-value]


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


def confirm_url(research_id: str = RESEARCH_ID) -> str:
    return f"/api/research/{research_id}/promote/confirm"


# ===========================================================================
# AC #1 — production + missing/false approval → 4xx (HTTP level)
# ===========================================================================


def test_production_scope_without_approval_returns_4xx(client: TestClient) -> None:
    response = client.post(
        confirm_url(), json={"scope": "production"}, headers=auth_headers()
    )
    assert response.status_code == 422


def test_production_scope_with_partial_approval_returns_4xx(
    client: TestClient,
) -> None:
    response = client.post(
        confirm_url(),
        json={
            "scope": "production",
            "approval": {"approved": True, "approver": "alice"},
        },
        headers=auth_headers(),
    )
    assert response.status_code == 422


def test_production_scope_with_false_approved_returns_4xx(client: TestClient) -> None:
    response = client.post(
        confirm_url(),
        json={
            "scope": "production",
            "approval": {
                "approved": False,
                "approver": "alice",
                "signature": "sig",
                "method": APPROVAL_METHOD,
                **CANDIDATE,
            },
        },
        headers=auth_headers(),
    )
    assert response.status_code == 422


# ===========================================================================
# AC #2 — verifier fail-closed (unit) + HMAC verification (unit + HTTP)
# ===========================================================================


def v2_request(approval: dict) -> PromotionScopeRequest:
    """Wrap an approval dict (including its signature) into the confirm model."""
    return PromotionScopeRequest(
        scope="production",
        approval=PromotionApproval(**approval),
    )


def test_verifier_rejects_when_secret_unset(monkeypatch) -> None:
    monkeypatch.setattr(settings, "production_approval_verifier", None)
    with pytest.raises(ValueError, match="verifier is not configured"):
        _verify_production_approval_signature(RESEARCH_ID, v2_request(signed_approval()))


def test_verifier_accepts_correct_signature(monkeypatch) -> None:
    monkeypatch.setattr(
        settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET)
    )
    # Returns None on success.
    assert _verify_production_approval_signature(
        RESEARCH_ID, v2_request(signed_approval())
    ) is None


def test_verifier_rejects_wrong_signature(monkeypatch) -> None:
    monkeypatch.setattr(
        settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET)
    )
    payload = v2_request(signed_approval(signature="not-the-right-signature"))
    with pytest.raises(ValueError, match="signature rejected"):
        _verify_production_approval_signature(RESEARCH_ID, payload)


def test_verifier_rejects_replayed_signature_for_different_research_id(
    monkeypatch,
) -> None:
    """A signature valid for one research_id must not validate for another."""
    monkeypatch.setattr(
        settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET)
    )
    # Sign for a different research_id than we present.
    approval = full_approval()
    stolen_sig = sign_approval("res_OTHER", "production", approval)
    payload = v2_request({**approval, "signature": stolen_sig})
    with pytest.raises(ValueError, match="signature rejected"):
        _verify_production_approval_signature(RESEARCH_ID, payload)


def test_verifier_rejects_legacy_signature_format(monkeypatch) -> None:
    """A legacy ``{research_id}:{scope}:{approver}`` signature must never verify.

    The same approver under the legacy string format signs a different message,
    so the HMAC cannot match the v2 canonical JSON — proving the v1 signature
    (and anything replayed into v2 shape) is rejected, not silently accepted.
    """
    monkeypatch.setattr(
        settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET)
    )
    approval = full_approval()
    legacy_message = f"{RESEARCH_ID}:production:{approval['approver']}".encode("utf-8")
    legacy_sig = hmac.new(
        VERIFIER_SECRET.encode("utf-8"), legacy_message, hashlib.sha256
    ).hexdigest()
    payload = v2_request({**approval, "signature": legacy_sig})
    with pytest.raises(ValueError, match="signature rejected"):
        _verify_production_approval_signature(RESEARCH_ID, payload)


def test_structural_validator_rejects_legacy_method() -> None:
    """method=hmac-sha256 is the legacy scheme; v2 is mandatory for production."""
    with pytest.raises(ValidationError, match="hmac-sha256-v2"):
        v2_request(full_approval(method="hmac-sha256", signature="legacy-sig"))


def test_structural_validator_rejects_missing_candidate_field() -> None:
    approval = full_approval(signature="placeholder-signature")
    del approval["config_snapshot_sha256"]
    with pytest.raises(ValidationError, match="config_snapshot_sha256"):
        v2_request(approval)


def test_structural_validator_rejects_non_integer_iteration() -> None:
    # strict int: a client-sent string "7" must not silently coerce into the
    # signed candidate.
    with pytest.raises(ValidationError):
        v2_request(full_approval(iteration="7"))


def test_structural_validator_rejects_malformed_digest() -> None:
    with pytest.raises(ValidationError):
        v2_request(full_approval(config_snapshot_sha256="deadbeef"))


def test_http_confirm_fail_closed_when_verifier_unset(
    client: TestClient,
    promoter: FakePromoter,
    configure_module: FakeStore,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "production_approval_verifier", None)
    response = client.post(
        confirm_url(),
        json=production_approval_body(),
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert "verifier is not configured" in response.json()["detail"]
    # The promoter must NOT have been reached (fail-closed before side effects).
    assert promoter.confirm_calls == []


def test_http_confirm_rejects_wrong_signature(
    client: TestClient,
    promoter: FakePromoter,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET)
    )
    response = client.post(
        confirm_url(),
        json=production_approval_body(signature="wrong-signature"),
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert "signature rejected" in response.json()["detail"]
    assert promoter.confirm_calls == []


def test_http_confirm_accepts_valid_signature(
    client: TestClient,
    promoter: FakePromoter,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET)
    )
    response = client.post(
        confirm_url(),
        json=production_approval_body(),
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.json()["confirmed"] is True
    # The promoter was reached and received the threaded approval payload.
    assert len(promoter.confirm_calls) == 1
    assert promoter.confirm_calls[0]["scope"] == "production"
    assert promoter.confirm_calls[0]["approval"] is not None


# ===========================================================================
# AC #3 — non-production scopes are unaffected by the verifier gate
# ===========================================================================


def test_development_scope_unaffected_without_verifier(
    client: TestClient,
    promoter: FakePromoter,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "production_approval_verifier", None)
    response = client.post(
        confirm_url(),
        json={"scope": "development"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert len(promoter.confirm_calls) == 1


def test_canary_scope_unaffected_without_verifier(
    client: TestClient,
    promoter: FakePromoter,
    monkeypatch,
) -> None:
    # canary is non-development but also non-production — proves the gate is
    # production-only, not "all non-dev scopes".
    monkeypatch.setattr(settings, "production_approval_verifier", None)
    response = client.post(
        confirm_url(),
        json={"scope": "canary"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert len(promoter.confirm_calls) == 1


# ===========================================================================
# AC #4 — the promotion.confirm audit event records the approver identity
# ===========================================================================


def _confirm_audit_event(store: FakeStore) -> dict:
    events = [
        e for e in store.audit_events if e.get("action") == "promotion.confirm"
    ]
    assert events, "no promotion.confirm audit event was recorded"
    return events[-1]


def test_audit_records_approver_on_success(
    client: TestClient,
    configure_module: FakeStore,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET)
    )
    approver = "alice@example.com"
    client.post(
        confirm_url(),
        json=production_approval_body(approver=approver),
        headers=auth_headers(),
    )

    event = _confirm_audit_event(configure_module)
    assert event["outcome"] == "success"
    metadata = event["request_metadata"]
    assert metadata["scope"] == "production"
    assert metadata["approver"] == approver
    assert metadata["approval_method"] == APPROVAL_METHOD
    for field, value in CANDIDATE.items():
        assert metadata[field] == value
    # actor_id (the API caller's identity) is written separately by
    # record_api_audit_event; it must be present and non-empty.
    assert event["actor_id"]


def test_audit_records_approver_on_signature_failure(
    client: TestClient,
    configure_module: FakeStore,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET)
    )
    approver = "alice@example.com"
    response = client.post(
        confirm_url(),
        json=production_approval_body(approver=approver, signature="forged"),
        headers=auth_headers(),
    )
    assert response.status_code == 400

    event = _confirm_audit_event(configure_module)
    assert event["outcome"] == "failure"
    metadata = event["request_metadata"]
    # The approver is recorded even on the failure path (forensic provenance).
    assert metadata["scope"] == "production"
    assert metadata["approver"] == approver
    assert event["error_message"]


def test_audit_records_scope_only_for_non_production(
    client: TestClient,
    configure_module: FakeStore,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "production_approval_verifier", None)
    client.post(
        confirm_url(),
        json={"scope": "development"},
        headers=auth_headers(),
    )

    event = _confirm_audit_event(configure_module)
    metadata = event["request_metadata"]
    assert metadata["scope"] == "development"
    # No approval was supplied, so no approver/method keys are added.
    assert "approver" not in metadata
    assert "approval_method" not in metadata


@pytest.mark.parametrize("scope", ["prod", "live", " production ", "PRODUCTION"])
def test_production_alias_requires_signed_approval(client, promoter, scope):
    response = client.post(
        confirm_url(),
        json={"scope": scope, "approval": {"approver": "alice", "approved": True}},
        headers=auth_headers(),
    )
    assert response.status_code == 422
    assert not promoter.confirm_calls


@pytest.mark.parametrize("scope", ["prod", "live", " production ", "PRODUCTION"])
@pytest.mark.parametrize("configured", [False, True])
def test_production_alias_cannot_bypass_verifier(
    client, promoter, monkeypatch, scope, configured,
):
    monkeypatch.setattr(
        settings, "production_approval_verifier",
        SecretStr(VERIFIER_SECRET) if configured else None,
    )
    body = production_approval_body(signature="forged")
    body["scope"] = scope
    response = client.post(confirm_url(), json=body, headers=auth_headers())
    assert response.status_code == 400
    assert not promoter.confirm_calls


@pytest.mark.parametrize("scope", ["prod", "live", " production ", "PRODUCTION"])
def test_production_alias_uses_canonical_signature(client, promoter, monkeypatch, scope):
    monkeypatch.setattr(settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET))
    body = production_approval_body()
    body["scope"] = scope
    response = client.post(confirm_url(), json=body, headers=auth_headers())
    assert response.status_code == 200
    assert promoter.confirm_calls[0]["scope"] == "production"

