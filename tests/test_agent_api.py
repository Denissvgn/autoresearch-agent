"""Attached-agent API: scoped authority, validation, and contract tests.

An attached agent completes research with a run-scoped credential and no
global operator token; it can only touch its own run and can never declare
its own results verified or approve production promotion.
"""
from __future__ import annotations

import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.agent import init as init_agent
from src.api.agent import router as agent_router
from src.core.scoped_credentials import (
    PERM_EVALUATE,
    PERM_LIFECYCLE,
    PERM_READ,
    PERM_SUBMIT,
    issue_scoped_credential,
    revoke_scoped_credential,
)
from src.core.state_store import SQLiteStateStore

KEY = "test-credential-key"


class _OrchestratorProbe:
    def __init__(self):
        self.calls = []

    def request_pause(self, research_id):
        self.calls.append(("pause", research_id))

    def request_resume(self, research_id):
        self.calls.append(("resume", research_id))

    def request_stop(self, research_id):
        self.calls.append(("stop", research_id))


@pytest.fixture
def store(tmp_path):
    import asyncio

    async def _build():
        s = SQLiteStateStore(str(tmp_path / "state.db"))
        await s.initialize()
        return s

    return asyncio.run(_build())


@pytest.fixture
def client(store):
    app = FastAPI()
    app.include_router(agent_router, prefix="/api/v1")
    probe = _OrchestratorProbe()
    init_agent(store, orchestrator=probe, credential_key=KEY)
    return TestClient(app), probe


def _token(run_id="res-scoped", subject="agent-1", tenant="tenant-a", **kw):
    return issue_scoped_credential(
        subject=subject,
        run_id=run_id,
        tenant_id=tenant,
        key=KEY,
        permissions=(PERM_READ, PERM_SUBMIT, PERM_EVALUATE, PERM_LIFECYCLE),
        **kw,
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_agent_completes_research_without_operator_token(client):
    http, probe = client
    token = _token()
    created = http.post(
        "/api/v1/agent/runs",
        json={"mode": "create", "instrument": "EURUSD"},
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["run_id"] == "res-scoped"
    assert "/agent/tenant-a/res-scoped" in body["workspace"]

    constraints = http.get(
        "/api/v1/agent/runs/res-scoped/constraints", headers=_auth(token)
    )
    assert constraints.status_code == 200
    assert constraints.json()["max_budget_usd"] == 7.5

    content = "candidate payload"
    digest = hashlib.sha256(content.encode()).hexdigest()
    submitted = http.post(
        "/api/v1/agent/runs/res-scoped/candidates",
        json={"digest": digest, "content": content},
        headers={**_auth(token), "Idempotency-Key": "k1"},
    )
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["authority"] == "model_proposed"

    evaluation = http.post(
        "/api/v1/agent/runs/res-scoped/evaluations", headers=_auth(token)
    )
    assert evaluation.status_code == 202

    results = http.get(
        "/api/v1/agent/runs/res-scoped/results", headers=_auth(token)
    )
    assert results.status_code == 200

    lifecycle = http.post(
        "/api/v1/agent/runs/res-scoped/lifecycle",
        json={"action": "pause"},
        headers=_auth(token),
    )
    assert lifecycle.status_code == 200
    assert probe.calls == [("pause", "res-scoped")]

    preview = http.get(
        "/api/v1/agent/runs/res-scoped/promotion-preview",
        headers=_auth(token),
    )
    assert preview.status_code == 200
    assert preview.json()["preview_only"] is True


def test_cross_run_identity_denial(client):
    http, _ = client
    token = _token(run_id="res-mine")
    http.post(
        "/api/v1/agent/runs",
        json={"mode": "create"},
        headers=_auth(token),
    )
    for path in (
        "/api/v1/agent/runs/res-other/constraints",
        "/api/v1/agent/runs/res-other/results",
        "/api/v1/agent/runs/res-other/promotion-preview",
    ):
        denied = http.get(path, headers=_auth(token))
        assert denied.status_code == 403, (path, denied.text)


def test_cross_tenant_identity_denial():
    from src.core.scoped_credentials import CredentialDenied, verify_scoped_credential

    token = _token(run_id="res-1", tenant="tenant-a")
    with pytest.raises(CredentialDenied):
        verify_scoped_credential(
            token,
            key=KEY,
            run_id="res-1",
            tenant_id="tenant-b",
        )


def test_expired_and_revoked_tokens_are_refused(client):
    http, _ = client
    expired = _token(ttl_s=-1.0)
    assert (
        http.get(
            "/api/v1/agent/runs/res-scoped/constraints",
            headers=_auth(expired),
        ).status_code
        == 403
    )
    revoked = _token()
    revoke_scoped_credential(revoked, key=KEY)
    assert (
        http.get(
            "/api/v1/agent/runs/res-scoped/constraints",
            headers=_auth(revoked),
        ).status_code
        == 403
    )


def test_forged_authority_is_never_upgraded(client):
    http, _ = client
    token = _token()
    http.post(
        "/api/v1/agent/runs",
        json={"mode": "create"},
        headers=_auth(token),
    )
    content = "self-declared"
    digest = hashlib.sha256(content.encode()).hexdigest()
    submitted = http.post(
        "/api/v1/agent/runs/res-scoped/candidates",
        json={
            "digest": digest,
            "content": content,
            "authority": "receipt_verified",
        },
        headers={**_auth(token), "Idempotency-Key": "forged"},
    )
    assert submitted.status_code == 201
    # the authority label comes from the channel, never from the payload
    assert submitted.json()["authority"] == "model_proposed"


def test_duplicate_submission_is_idempotent_and_conflict_safe(client):
    http, _ = client
    token = _token()
    http.post(
        "/api/v1/agent/runs",
        json={"mode": "create"},
        headers=_auth(token),
    )
    content = "same content"
    digest = hashlib.sha256(content.encode()).hexdigest()
    headers = {**_auth(token), "Idempotency-Key": "dup-key"}
    first = http.post(
        "/api/v1/agent/runs/res-scoped/candidates",
        json={"digest": digest, "content": content},
        headers=headers,
    )
    second = http.post(
        "/api/v1/agent/runs/res-scoped/candidates",
        json={"digest": digest, "content": content},
        headers=headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json() == first.json()
    # the same key with a different request is a conflict
    other = "different content"
    other_digest = hashlib.sha256(other.encode()).hexdigest()
    conflict = http.post(
        "/api/v1/agent/runs/res-scoped/candidates",
        json={"digest": other_digest, "content": other},
        headers=headers,
    )
    assert conflict.status_code == 409


def test_digest_mismatch_size_and_rate_limits(client):
    http, _ = client
    token = _token()
    http.post(
        "/api/v1/agent/runs",
        json={"mode": "create"},
        headers=_auth(token),
    )
    # a digest that does not match the content is refused
    mismatch = http.post(
        "/api/v1/agent/runs/res-scoped/candidates",
        json={"digest": "0" * 64, "content": "payload"},
        headers={**_auth(token), "Idempotency-Key": "m1"},
    )
    assert mismatch.status_code == 422
    # an oversized submission is refused
    oversized = "x" * (64 * 1024 + 1)
    too_big = http.post(
        "/api/v1/agent/runs/res-scoped/candidates",
        json={
            "digest": hashlib.sha256(oversized.encode()).hexdigest(),
            "content": oversized,
        },
        headers={**_auth(token), "Idempotency-Key": "big1"},
    )
    assert too_big.status_code == 413
    # a burst beyond the rate limit is refused
    codes = set()
    for _ in range(130):
        codes.add(
            http.get(
                "/api/v1/agent/runs/res-scoped/constraints",
                headers=_auth(token),
            ).status_code
        )
    assert 429 in codes


def test_scoped_authority_is_distinct_from_operator_and_approver():
    from src.core.scoped_credentials import (
        CredentialDenied,
        issue_scoped_credential,
    )

    for illegal in ("operator", "promote:approve", "evidence:declare"):
        with pytest.raises(CredentialDenied):
            issue_scoped_credential(
                subject="agent-1",
                run_id="res-1",
                permissions=(illegal,),
                key=KEY,
            )


def test_scoped_token_cannot_approve_production_promotion(monkeypatch):
    # the promotion confirm surface authenticates with the operator token;
    # a run-scoped credential is refused there, while the agent's own
    # promotion surface is preview-only
    from src.api.promotion import router as promotion_router
    from src.config import settings

    monkeypatch.setattr(
        settings, "autoresearch_api_token", "operator-token"
    )
    app = FastAPI()
    app.include_router(promotion_router, prefix="/api/v1")
    http = TestClient(app)
    scoped_token = _token()
    denied = http.post(
        "/api/v1/research/res-scoped/promote/confirm",
        json={"approved": True},
        headers=_auth(scoped_token),
    )
    assert denied.status_code in (401, 403), denied.text