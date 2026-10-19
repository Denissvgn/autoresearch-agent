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
    """Ranking double: grouped, direction-aware, windowed rows."""

    def __init__(self) -> None:
        self.rows = [
            {
                "id": "res_aaa", "skill_id": "prompt-engineering",
                "subject_id": "default", "variant": "production",
                "tag": "run-a", "status": "completed", "best_metric": 0.42,
                "metric_name": "score", "best_iteration": 7,
                "effective_iteration_count": 12,
                "total_api_cost_usd": 1.25, "started_at": "2026-09-01T00:00:00",
                "completed_at": "2026-09-01T01:00:00",
                "comparison_context": '{"schema":"comparison-context.v1","objective":"score"}',
            },
            {
                "id": "res_bbb", "skill_id": "prompt-engineering",
                "subject_id": "default", "variant": "production",
                "tag": "run-b", "status": "completed", "best_metric": 0.91,
                "metric_name": "score", "best_iteration": 5,
                "effective_iteration_count": 9,
                "total_api_cost_usd": 0.75, "started_at": "2026-09-02T00:00:00",
                "completed_at": "2026-09-02T01:00:00",
                "comparison_context": '{"schema":"comparison-context.v1","objective":"score"}',
            },
            {
                "id": "res_ccc", "skill_id": "prompt-engineering",
                "subject_id": "default", "variant": "production",
                "tag": None, "status": "failed", "best_metric": None,
                "best_iteration": None, "total_api_cost_usd": 0.1,
                "started_at": "2026-09-03T00:00:00", "completed_at": None,
                "comparison_context": None,
            },
            {
                "id": "res_ddd", "skill_id": "prompt-engineering",
                "subject_id": "legacy", "variant": "v1",
                "tag": "legacy-run", "status": "completed", "best_metric": 0.99,
                "metric_name": "score", "best_iteration": 3,
                "effective_iteration_count": 3,
                "total_api_cost_usd": 0.5, "started_at": "2026-08-01T00:00:00",
                "completed_at": "2026-08-01T01:00:00",
                "comparison_context": None,
            },
        ]

    async def rank_leaderboard_groups(
        self, *, model_types, direction="maximize", limit=20, offset=0,
    ):
        eligible = [
            r for r in self.rows
            if r.get("best_metric") is not None and r.get("skill_id") in model_types
        ]
        contexts = sorted(
            {r.get("comparison_context") for r in eligible},
            key=lambda c: (c is None, c or ""),
        )
        order = -1 if direction == "maximize" else 1
        groups = []
        for context in contexts:
            rows = [r for r in eligible if r.get("comparison_context") == context]
            rows = sorted(rows, key=lambda r: (order * r["best_metric"], r["id"]))
            groups.append(
                {
                    "comparison_context": context,
                    "items": rows[offset:offset + limit],
                    "total": len(rows),
                    "limit": limit,
                    "offset": offset,
                }
            )
        return groups


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


def test_leaderboard_ranks_within_comparable_groups(client: TestClient, monkeypatch):
    monkeypatch.setattr(skills_module, "_store", _FakeStore())
    r = client.get(
        "/api/v1/skills/prompt-engineering/leaderboard",
        headers=auth_headers(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["skill_id"] == "prompt-engineering"
    assert body["metric"]["direction"] == "higher_is_better"
    assert body["ranking_scope"] == "global within comparable-context groups"
    known = [g for g in body["groups"] if g["known_context"]]
    unknown = [g for g in body["groups"] if not g["known_context"]]
    assert len(known) == 1 and len(unknown) == 1
    ids = [item["research_id"] for item in known[0]["items"]]
    # higher_is_better -> best first; unscored sessions excluded.
    assert ids == ["res_bbb", "res_aaa"]
    assert known[0]["total"] == 2
    # the legacy/unknown-context session ranks only in its own group —
    # its 0.99 never becomes the known group's shared winner
    assert [i["research_id"] for i in unknown[0]["items"]] == ["res_ddd"]
    assert "unknown" in unknown[0]["label"]


def test_leaderboard_window_semantics(client: TestClient, monkeypatch):
    monkeypatch.setattr(skills_module, "_store", _FakeStore())
    r = client.get(
        "/api/v1/skills/prompt-engineering/leaderboard?limit=1",
        headers=auth_headers(),
    )
    assert r.status_code == 200
    known = [g for g in r.json()["groups"] if g["known_context"]][0]
    assert len(known["items"]) == 1
    assert known["total"] == 2
    assert known["limit"] == 1
    # the next window continues the same ranking
    r2 = client.get(
        "/api/v1/skills/prompt-engineering/leaderboard?limit=1&offset=1",
        headers=auth_headers(),
    )
    known2 = [g for g in r2.json()["groups"] if g["known_context"]][0]
    assert [i["research_id"] for i in known2["items"]] == ["res_aaa"]
    assert known2["offset"] == 1


def test_leaderboard_graceful_without_store(client: TestClient, monkeypatch):
    monkeypatch.setattr(skills_module, "_store", None)
    r = client.get(
        "/api/v1/skills/prompt-engineering/leaderboard",
        headers=auth_headers(),
    )
    assert r.status_code == 200
    assert r.json()["groups"] == []
