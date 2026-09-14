"""GET /skills/{id}/leaderboard contract tests (P0-4)."""
from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import skills as skills_module
from src.api.skills import router as skills_router
from src.config import settings

API_TOKEN = "test-autoresearch-token"


class _FakeStore:
    """Minimal list_sessions double: two scored sessions + one unscored."""

    def __init__(self) -> None:
        self.rows = [
            {
                "id": "res_aaa", "skill_id": "prompt-engineering",
                "subject_id": "default", "variant": "production",
                "tag": "run-a", "status": "completed", "best_metric": 0.42,
                "best_iteration": 7, "effective_iteration_count": 12,
                "total_api_cost_usd": 1.25, "started_at": "2026-09-01T00:00:00",
                "completed_at": "2026-09-01T01:00:00",
            },
            {
                "id": "res_bbb", "skill_id": "prompt-engineering",
                "subject_id": "default", "variant": "production",
                "tag": "run-b", "status": "completed", "best_metric": 0.91,
                "best_iteration": 5, "effective_iteration_count": 9,
                "total_api_cost_usd": 0.75, "started_at": "2026-09-02T00:00:00",
                "completed_at": "2026-09-02T01:00:00",
            },
            {
                "id": "res_ccc", "skill_id": "prompt-engineering",
                "subject_id": "default", "variant": "production",
                "tag": None, "status": "failed", "best_metric": None,
                "best_iteration": None, "total_api_cost_usd": 0.1,
                "started_at": "2026-09-03T00:00:00", "completed_at": None,
            },
        ]

    async def list_sessions(
        self, status=None, model_type=None, instrument=None,
        status_in=None, limit=None, offset=0, cursor=None, reverse=False,
    ):
        rows = [r for r in self.rows if r.get("best_metric") is not None]
        if model_type:
            rows = [r for r in rows if r.get("skill_id") == model_type]
        capped = limit if limit is not None else len(rows)
        return rows[:capped]


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(skills_router, prefix="/api/v1")
    return app


@pytest.fixture(autouse=True)
def configure_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)
    skills_module._registry.discover()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_test_app())


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


def test_leaderboard_unknown_skill_404(client: TestClient):
    r = client.get("/api/v1/skills/no-such-skill/leaderboard", headers=auth_headers())
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "skill_not_found"


def test_leaderboard_requires_auth(client: TestClient):
    r = client.get("/api/v1/skills/prompt-engineering/leaderboard")
    assert r.status_code in (401, 403)


def test_leaderboard_sorts_and_filters(client: TestClient, monkeypatch):
    monkeypatch.setattr(skills_module, "_store", _FakeStore())
    r = client.get(
        "/api/v1/skills/prompt-engineering/leaderboard",
        headers=auth_headers(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["skill_id"] == "prompt-engineering"
    assert body["metric"]["direction"] == "higher_is_better"
    ids = [item["research_id"] for item in body["items"]]
    # higher_is_better -> best first; unscored sessions excluded.
    assert ids == ["res_bbb", "res_aaa"]
    assert body["total"] == 2


def test_leaderboard_respects_limit(client: TestClient, monkeypatch):
    monkeypatch.setattr(skills_module, "_store", _FakeStore())
    r = client.get(
        "/api/v1/skills/prompt-engineering/leaderboard?limit=1",
        headers=auth_headers(),
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
    assert r.json()["total"] == 2


def test_leaderboard_graceful_without_store(client: TestClient, monkeypatch):
    monkeypatch.setattr(skills_module, "_store", None)
    r = client.get(
        "/api/v1/skills/prompt-engineering/leaderboard",
        headers=auth_headers(),
    )
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 0
