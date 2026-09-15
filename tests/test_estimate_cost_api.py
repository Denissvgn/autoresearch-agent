"""POST /research/estimate-cost tests (P2 ops).

The endpoint replaces the UI's ``$0.24 × iterations`` heuristic with the
server-side estimator (``llm_provider.estimate_session_cost``) that shares
pricing with the post-call ledger. Pure compute — no store, no LLM.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.research import router as research_router
from src.config import settings
from src.core.llm_provider import estimate_session_cost

API_TOKEN = "test-autoresearch-token"


@pytest.fixture(autouse=True)
def configure_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(research_router, prefix="/api/v1")
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


def test_estimate_matches_shared_estimator(client: TestClient):
    response = client.post(
        "/api/v1/research/estimate-cost",
        json={"max_iterations": 30, "quick_mode": False},
        headers=_auth(),
    )
    assert response.status_code == 200
    body = response.json()
    expected = estimate_session_cost(iterations=30, quick_mode=False)
    assert body["total_usd"] == expected["total_usd"]
    assert body["per_iteration_usd"] == expected["per_iteration_usd"]
    assert body["capped_by_budget"] is False
    assert body["assumptions"]["calls_per_iteration"] == 3


def test_estimate_reports_budget_cap(client: TestClient):
    body = client.post(
        "/api/v1/research/estimate-cost",
        json={"max_iterations": 500, "quick_mode": False, "max_budget_usd": 10.0},
        headers=_auth(),
    ).json()
    assert body["uncapped_total_usd"] > 10.0
    assert body["capped_by_budget"] is True
    assert body["total_usd"] == pytest.approx(10.0)


def test_quick_mode_is_cheaper(client: TestClient):
    full = client.post(
        "/api/v1/research/estimate-cost",
        json={"max_iterations": 30, "quick_mode": False}, headers=_auth(),
    ).json()
    quick = client.post(
        "/api/v1/research/estimate-cost",
        json={"max_iterations": 30, "quick_mode": True}, headers=_auth(),
    ).json()
    assert quick["total_usd"] < full["total_usd"]


def test_estimate_requires_auth(client: TestClient):
    response = client.post(
        "/api/v1/research/estimate-cost", json={"max_iterations": 30},
    )
    assert response.status_code in (401, 403)


def test_estimate_rejects_out_of_range(client: TestClient):
    response = client.post(
        "/api/v1/research/estimate-cost",
        json={"max_iterations": 0}, headers=_auth(),
    )
    assert response.status_code == 422
