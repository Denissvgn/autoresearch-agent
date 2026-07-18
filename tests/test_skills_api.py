"""Skill & subject endpoint contract tests (ARC-011 P3-012, GEN-003).

Exercises the full skill API surface introduced in Phase 3:
``GET /skills``, ``GET /skills/{id}``, the schema/form/metric sub-resources,
``POST /skills/reload``, and the subject/variant enumeration endpoints.
Also asserts the OpenAPI contract documents them under ``/api/v1`` (not the
legacy ``/api`` prefix) and that auth is enforced.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import skills as skills_module
from src.api import subjects as subjects_module
from src.api.skills import router as skills_router
from src.api.subjects import router as subjects_router
from src.config import settings

API_TOKEN = "test-autoresearch-token"
_EXPECTED_SKILL_IDS = {"ml-direction", "ml-volatility", "ml-rl"}


def create_test_app() -> FastAPI:
    app = FastAPI()
    # /api/v1 is the canonical, schema-documented prefix; /api is the legacy
    # alias prefix (reachable but hidden from OpenAPI, matching main.py).
    app.include_router(skills_router, prefix="/api/v1")
    app.include_router(subjects_router, prefix="/api/v1")
    app.include_router(skills_router, prefix="/api", include_in_schema=False)
    app.include_router(subjects_router, prefix="/api", include_in_schema=False)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


@pytest.fixture(autouse=True)
def configure_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)
    skills_module._registry.discover()
    subjects_module._registry.discover()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_test_app())


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


# --- GET /skills (GEN-003) ---

def test_list_skills_returns_all_ml_skills(client: TestClient):
    response = client.get("/api/v1/skills", headers=auth_headers())
    assert response.status_code == 200
    ids = {s["id"] for s in response.json()}
    assert _EXPECTED_SKILL_IDS.issubset(ids)


def test_list_skills_carries_legacy_model_type_alias(client: TestClient):
    response = client.get("/api/v1/skills", headers=auth_headers())
    by_id = {s["id"]: s for s in response.json()}
    assert by_id["ml-direction"]["model_type"] == "direction"
    assert by_id["ml-volatility"]["model_type"] == "volatility"
    assert by_id["ml-rl"]["model_type"] == "rl"


def test_list_skills_category_filter(client: TestClient):
    response = client.get("/api/v1/skills?category=optimization", headers=auth_headers())
    assert response.status_code == 200
    for s in response.json():
        assert s["category"] == "optimization"


# --- GET /skills/{id} ---

def test_get_skill_returns_descriptor_with_links(client: TestClient):
    response = client.get("/api/v1/skills/ml-direction", headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "ml-direction"
    assert body["display_name"]
    assert body["links"]["self"] == "/skills/ml-direction"
    assert body["links"]["form_fields"] == "/skills/ml-direction/form-fields"
    assert body["model_type"] == "direction"


def test_get_skill_unknown_returns_404_with_hint(client: TestClient):
    response = client.get("/api/v1/skills/nonexistent-skill", headers=auth_headers())
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error"] == "skill_not_found"
    assert detail["skill_id"] == "nonexistent-skill"
    assert "available" in detail
    assert "hint" in detail


# --- Sub-resource endpoints ---

def test_get_param_schema(client: TestClient):
    response = client.get("/api/v1/skills/ml-direction/param-schema", headers=auth_headers())
    assert response.status_code == 200
    schema = response.json()
    assert schema["type"] == "object"
    assert "properties" in schema


def test_get_form_fields(client: TestClient):
    response = client.get("/api/v1/skills/ml-direction/form-fields", headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["skill_id"] == "ml-direction"
    assert isinstance(body["form_fields"], list)
    field_names = {f["name"] for f in body["form_fields"]}
    assert "enable_hpo" in field_names


def test_get_metric_schema(client: TestClient):
    response = client.get("/api/v1/skills/ml-direction/metric-schema", headers=auth_headers())
    assert response.status_code == 200
    schema = response.json()
    assert "primary" in schema
    assert schema["primary"]["field"]
    assert "chart_series" in schema
    assert "iteration_table_columns" in schema


def test_get_versions(client: TestClient):
    response = client.get("/api/v1/skills/ml-direction/versions", headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["skill_id"] == "ml-direction"
    assert len(body["versions"]) >= 1
    assert body["versions"][0]["current"] is True


def test_get_changelog(client: TestClient):
    response = client.get("/api/v1/skills/ml-direction/changelog", headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["skill_id"] == "ml-direction"
    assert "changelog" in body


# --- POST /skills/reload ---

def test_reload_skills(client: TestClient):
    response = client.post("/api/v1/skills/reload", headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["reloaded"] >= 0
    assert _EXPECTED_SKILL_IDS.issubset(set(body["available"]))


def test_reload_blocked_in_production(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """P3-008: hot-reload is a dev convenience and must be disabled in prod."""
    monkeypatch.setattr(settings, "environment", "production")
    response = client.post("/api/v1/skills/reload", headers=auth_headers())
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["error"] == "skills_reload_prod_disabled"
    assert detail["environment"] == "production"
    assert "hint" in detail


def test_reload_allowed_in_staging(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Non-production environments keep the dev convenience available."""
    monkeypatch.setattr(settings, "environment", "staging")
    response = client.post("/api/v1/skills/reload", headers=auth_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# --- Subjects (P3-009, P3-010) ---

def test_list_subjects(client: TestClient):
    response = client.get("/api/v1/subjects?skill_id=ml-direction", headers=auth_headers())
    assert response.status_code == 200
    subjects = response.json()
    assert isinstance(subjects, list)
    for s in subjects:
        assert "id" in s
        assert "label" in s


def test_list_subject_variants(client: TestClient):
    response = client.get(
        "/api/v1/subjects/DOGE_USDT/variants?skill_id=ml-direction",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["skill_id"] == "ml-direction"
    assert body["subject_id"] == "DOGE_USDT"
    assert isinstance(body["variants"], list)


def test_subjects_unknown_skill_returns_404(client: TestClient):
    response = client.get("/api/v1/subjects?skill_id=nonexistent", headers=auth_headers())
    assert response.status_code == 404


# --- Auth enforcement ---

def test_skills_require_auth(client: TestClient):
    assert client.get("/api/v1/skills").status_code == 401
    assert client.get("/api/v1/skills/ml-direction").status_code == 401


# --- OpenAPI contract (extends test_openapi_contract.py) ---

def test_openapi_documents_skills_endpoints_under_api_v1():
    app = create_test_app()
    paths = app.openapi()["paths"]
    for path in (
        "/api/v1/skills",
        "/api/v1/skills/{skill_id}",
        "/api/v1/skills/{skill_id}/form-fields",
        "/api/v1/skills/{skill_id}/param-schema",
        "/api/v1/skills/{skill_id}/metric-schema",
        "/api/v1/skills/{skill_id}/versions",
        "/api/v1/skills/{skill_id}/changelog",
        "/api/v1/skills/reload",
        "/api/v1/subjects",
        "/api/v1/subjects/{subject_id}/variants",
    ):
        assert path in paths, f"missing OpenAPI path {path}"


def test_openapi_hides_skills_endpoints_under_legacy_api_prefix():
    app = create_test_app()
    paths = app.openapi()["paths"]
    assert "/api/skills" not in paths
    assert "/api/subjects" not in paths
