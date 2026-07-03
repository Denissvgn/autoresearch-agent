"""P0-020 / P0-021 — Mandatory production approval (W18).

Exercises the four acceptance criteria from the ARC-011 backlog
(`docs/adr/ARC-011-backlog.md` §P0-020/P0-021):

  AC #1  ``POST /promote/confirm`` with ``scope=production`` and missing /
         ``false`` ``approval.approved`` → 4xx.
  AC #2  Approval requires a signature field, verified against a configured
         HMAC-SHA256 verifier (fail-closed when the verifier is unset).
  AC #3  Other scopes are unaffected by the verifier gate.
  AC #4  The ``promotion.confirm`` audit event records the approver identity.

The structural gate (AC #1 / AC #3 non-production) is already provided by
``PromotionScopeRequest._enforce_production_approval`` and is covered at the
Pydantic-model layer in ``test_hardening_phase1_to_5.py``; the HTTP-level and
verifier (AC #2) and audit (AC #4) coverage lives here.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from src.api import promotion as promotion_module
from src.api.promotion import (
    PromotionApproval,
    PromotionScopeRequest,
    _verify_production_approval_signature,
)
from src.config import settings

API_TOKEN = "test-autoresearch-token"
VERIFIER_SECRET = "test-verifier-secret"
RESEARCH_ID = "res_w18"


# ---------------------------------------------------------------------------
# Signature helper — mirrors the server's canonical message exactly.
# ---------------------------------------------------------------------------


def sign_approval(research_id: str, scope: str, approver: str) -> str:
    """Compute the expected HMAC-SHA256 signature the way the server does."""
    message = f"{research_id}:{scope}:{approver}".encode("utf-8")
    return hmac.new(VERIFIER_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()


def production_approval_body(
    *,
    approver: str = "alice@example.com",
    signature: str | None = None,
    method: str = "hmac-sha256",
) -> dict:
    """A valid-shaped production approval body (signature defaults to correct)."""
    sig = signature if signature is not None else sign_approval(
        RESEARCH_ID, "production", approver
    )
    return {
        "scope": "production",
        "approval": {
            "approved": True,
            "approver": approver,
            "signature": sig,
            "method": method,
        },
    }


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
                "method": "hmac-sha256",
            },
        },
        headers=auth_headers(),
    )
    assert response.status_code == 422


# ===========================================================================
# AC #2 — verifier fail-closed (unit) + HMAC verification (unit + HTTP)
# ===========================================================================


def test_verifier_rejects_when_secret_unset(monkeypatch) -> None:
    monkeypatch.setattr(settings, "production_approval_verifier", None)
    payload = PromotionScopeRequest(
        scope="production",
        approval=PromotionApproval(
            approved=True,
            approver="alice",
            signature="any-nonempty-sig",
            method="hmac-sha256",
        ),
    )
    with pytest.raises(ValueError, match="verifier is not configured"):
        _verify_production_approval_signature(RESEARCH_ID, payload)


def test_verifier_accepts_correct_signature(monkeypatch) -> None:
    monkeypatch.setattr(
        settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET)
    )
    approver = "alice@example.com"
    payload = PromotionScopeRequest(
        scope="production",
        approval=PromotionApproval(
            approved=True,
            approver=approver,
            signature=sign_approval(RESEARCH_ID, "production", approver),
            method="hmac-sha256",
        ),
    )
    # Returns None on success.
    assert _verify_production_approval_signature(RESEARCH_ID, payload) is None


def test_verifier_rejects_wrong_signature(monkeypatch) -> None:
    monkeypatch.setattr(
        settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET)
    )
    payload = PromotionScopeRequest(
        scope="production",
        approval=PromotionApproval(
            approved=True,
            approver="alice@example.com",
            signature="not-the-right-signature",
            method="hmac-sha256",
        ),
    )
    with pytest.raises(ValueError, match="signature rejected"):
        _verify_production_approval_signature(RESEARCH_ID, payload)


def test_verifier_rejects_replayed_signature_for_different_research_id(
    monkeypatch,
) -> None:
    """A signature valid for one research_id must not validate for another."""
    monkeypatch.setattr(
        settings, "production_approval_verifier", SecretStr(VERIFIER_SECRET)
    )
    approver = "alice@example.com"
    # Sign for a different research_id than we present.
    stolen_sig = sign_approval("res_OTHER", "production", approver)
    payload = PromotionScopeRequest(
        scope="production",
        approval=PromotionApproval(
            approved=True,
            approver=approver,
            signature=stolen_sig,
            method="hmac-sha256",
        ),
    )
    with pytest.raises(ValueError, match="signature rejected"):
        _verify_production_approval_signature(RESEARCH_ID, payload)


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
    assert metadata["approval_method"] == "hmac-sha256"
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
