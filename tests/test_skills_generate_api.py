"""POST /skills/generate endpoint tests (P2 Skill SDK).

Contract: feature-flagged (403 when ``skill_generator_enabled`` is off),
audited, validated drafts into ``skills/_drafts/<id>/`` via the real
``SkillGenerator`` with a stubbed LLM provider. Promotion is deliberately
NOT offered here — moving drafts into the live tree stays an operator act
(``autoresearch promote-skill``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.skills import router as skills_router
from src.config import settings
from src.core import llm_provider as llm_provider_module
from src.core import skill_registry as skill_registry_module

API_TOKEN = "test-autoresearch-token"


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(skills_router, prefix="/api/v1")
    return app


class _StubProvider:
    name = "stub"

    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(self, *, model, prompt, max_tokens, system=None) -> str:
        return self._response


def _payload(*, skill_id: str = "api-gen-skill") -> dict[str, Any]:
    manifest = {
        "schema_version": "research_skill.v1",
        "id": skill_id,
        "version": "1.0.0",
        "category": "optimization",
        "display_name": "API Gen Skill",
        "description": "An endpoint test skill.",
        "llm": {"provider": "anthropic", "primary_model": "m"},
        "workspace": {"session_path_template": "runs/{skill_id}"},
        "variants": {"static": ["v1"]},
        "param_schema": {"type": "object"},
        "metric_schema": {
            "primary": {"field": "m", "label": "M", "direction": "higher_is_better"}
        },
        "decision_vocabulary": {"base": ["keep"]},
        "phase_plan": [{"id": "p1", "min_iterations": 1, "max_iterations": 2}],
        "command_policy": {"allowed_scripts": ["run.sh"]},
        "output_parser": {"format": "delimited_kv"},
        "preflight": [],
        "promotion_target": {
            "primary": {"kind": "file_path", "path_template": "/tmp/x"}
        },
    }
    return {
        "skill_id": skill_id,
        "manifest_yaml": yaml.safe_dump(manifest),
        "bootstrap_py": "import json\nprint(json.dumps({'rendered': []}))\n",
        "eval_run_py": "",
        "skill_md": "# API Gen Skill\n",
    }


@pytest.fixture(autouse=True)
def hermetic_skills_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> Path:
    """Keep drafts out of the packaged skills/ tree and pin the auth token."""
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    monkeypatch.setattr(skill_registry_module, "DEFAULT_SKILLS_ROOT", skills_root)
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)
    return skills_root


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_test_app())


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


def test_generate_disabled_by_default(client: TestClient):
    response = client.post(
        "/api/v1/skills/generate",
        json={"goal": "tune a database configuration"},
        headers=_auth(),
    )
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["error"] == "skill_generator_disabled"
    assert "AUTORESEARCH_SKILL_GENERATOR_ENABLED" in detail["hint"]


def test_generate_creates_draft_when_enabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
    hermetic_skills_tree: Path,
):
    monkeypatch.setattr(settings, "skill_generator_enabled", True)
    monkeypatch.setattr(
        llm_provider_module, "build_provider",
        lambda name, **kw: _StubProvider(json.dumps(_payload())),
    )
    response = client.post(
        "/api/v1/skills/generate",
        json={"goal": "tune a database configuration"},
        headers=_auth(),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["skill_id"] == "api-gen-skill"
    assert body["lifecycle_state"] == "draft"
    assert "SKILL.yaml" in body["files"]
    assert body["policy_findings"] == []
    assert "promote-skill --id api-gen-skill" in body["next"]
    draft = hermetic_skills_tree / "_drafts" / "api-gen-skill"
    assert (draft / "SKILL.yaml").is_file()


def test_generate_reports_critical_findings(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "skill_generator_enabled", True)
    payload = _payload()
    import yaml as _yaml

    manifest = _yaml.safe_load(payload["manifest_yaml"])
    manifest["command_policy"] = {
        "allowed_scripts": ["run.sh", "rm -rf /tmp/evil"],
    }
    payload["manifest_yaml"] = _yaml.safe_dump(manifest)
    monkeypatch.setattr(
        llm_provider_module, "build_provider",
        lambda name, **kw: _StubProvider(json.dumps(payload)),
    )
    response = client.post(
        "/api/v1/skills/generate",
        json={"goal": "tune a database configuration"},
        headers=_auth(),
    )
    assert response.status_code == 201
    findings = response.json()["policy_findings"]
    assert any(f["severity"] == "critical" for f in findings)


def test_generate_invalid_llm_output_is_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
    hermetic_skills_tree: Path,
):
    monkeypatch.setattr(settings, "skill_generator_enabled", True)
    monkeypatch.setattr(
        llm_provider_module, "build_provider",
        lambda name, **kw: _StubProvider("garbage not json"),
    )
    response = client.post(
        "/api/v1/skills/generate",
        json={"goal": "tune a database configuration"},
        headers=_auth(),
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "skill_generation_failed"
    assert not (hermetic_skills_tree / "_drafts" / "api-gen-skill").exists()


def test_generate_requires_auth(client: TestClient):
    response = client.post(
        "/api/v1/skills/generate", json={"goal": "tune a database configuration"},
    )
    assert response.status_code in (401, 403)
