"""Skill-parameter validation over the declared JSON Schema subset.

Review regressions: invalid bounds and missing required fields are rejected
before session side effects; omitted/null parameter objects are validated by
the one canonical resolution path; bool/number are distinct; enums and nested
structures are enforced with field-addressed errors; permitted extra
properties behave exactly as ``additionalProperties`` declares; defaults are
applied deliberately by resolution, never assumed from validation; and
OpenAPI request/response fixtures stay consistent with the server contract.
"""
from __future__ import annotations

import os
from typing import Any, Dict

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

from pathlib import Path as FsPath

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import research as research_module
from src.api.research import router as research_router
from src.config import settings
from src.core.skill_manifest import ParamSchema
from src.core.skill_params import (
    SCHEMA_DIALECT,
    SUPPORTED_KEYWORDS,
    apply_defaults,
    resolve_and_validate,
    unsupported_schema_keywords,
    validate_resolved,
)

API_TOKEN = "test-autoresearch-token"
REPO_ROOT = FsPath(__file__).resolve().parents[1]


class _StubSessionManager:
    """Records every start attempt so tests can assert side effects never began."""

    active_count = 0
    _active_pipelines: dict[str, object] = {}

    def __init__(self) -> None:
        self.start_calls: list[dict[str, Any]] = []
        self.captured_kwargs: Dict[str, Any] = {}

    async def start_session(self, **kwargs: Any) -> Dict[str, Any]:
        self.start_calls.append(dict(kwargs))
        self.captured_kwargs = dict(kwargs)
        return {
            "id": "res_test0001",
            "instrument": kwargs.get("instrument", ""),
            "timeframe": kwargs.get("timeframe", ""),
            "model_type": kwargs.get("model_type", ""),
            "skill_id": kwargs.get("skill_id", ""),
            "subject_id": kwargs.get("subject_id", ""),
            "variant": kwargs.get("variant", ""),
            "tag": kwargs.get("tag", "test"),
            "status": "running",
            "quick_mode": kwargs.get("quick_mode", False),
            "max_iterations": kwargs.get("max_iterations", 30),
            "max_budget_usd": kwargs.get("max_budget_usd", 10.0),
            "workspace_path": "/tmp/test",
            "best_metric": None,
            "best_iteration": None,
            "current_iteration": 0,
            "total_cost_usd": 0.0,
            "created_at": "2026-01-01T00:00:00Z",
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": None,
            "error_message": None,
        }


class _StubStore:
    def __init__(self) -> None:
        self.audit_events: list[dict[str, Any]] = []

    async def record_audit_event(self, **kwargs: Any) -> None:
        self.audit_events.append(kwargs)

    async def ping(self) -> bool:
        return True

    async def get_session(self, research_id: str) -> Dict[str, Any] | None:
        return None

    async def list_sessions(self, **kwargs: Any) -> list[Dict[str, Any]]:
        return []

    async def count_sessions(self, **kwargs: Any) -> int:
        return 0


_manager: _StubSessionManager | None = None


@pytest.fixture(autouse=True)
def _wire(monkeypatch: pytest.MonkeyPatch):
    global _manager
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)
    _manager = _StubSessionManager()
    research_module.init(_manager, _StubStore())
    yield


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(research_router, prefix="/api/v1")
    return TestClient(app)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


# --- declared subset and dialect -------------------------------------------


def test_declared_subset_covers_manifest_schemas():
    """Every bundled skill schema uses only the declared subset keywords."""
    for skill in ("db-config-tuning", "prompt-engineering", "code-refactor"):
        doc = yaml.safe_load(
            (REPO_ROOT / "skills" / skill / "SKILL.yaml").read_text(encoding="utf-8")
        )
        assert unsupported_schema_keywords(doc["param_schema"]) == frozenset()
    assert SCHEMA_DIALECT == "draft 2020-12"
    assert {"type", "properties", "required", "additionalProperties",
            "minimum", "maximum", "enum", "items", "default"} <= SUPPORTED_KEYWORDS


def test_manifest_with_unsupported_keyword_is_rejected_at_load():
    """A keyword outside the subset can never be silently ignored."""
    with pytest.raises(ValueError):
        ParamSchema.model_validate({
            "type": "object",
            "properties": {"x": {"type": "integer", "allOf": []}},
        })


# --- one canonical resolution path -----------------------------------------


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["eval_set"],
    "properties": {
        "eval_set": {"type": "string"},
        "target_metric": {"type": "string", "enum": ["a", "b"], "default": "a"},
        "cost": {"type": "number", "minimum": 0, "default": 0.5},
        "flag": {"type": "boolean", "default": False},
        "nested": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 1}},
            "required": ["n"],
        },
    },
}


def test_omitted_and_null_objects_face_required_fields() -> None:
    for raw in (None, {}):
        resolved, violations = resolve_and_validate("s", SCHEMA, raw)
        assert any(v["field"] == "skill_params" for v in violations), violations
        assert resolved == {} or "eval_set" not in resolved


def test_bool_is_not_a_number() -> None:
    _, violations = resolve_and_validate(
        "s", SCHEMA, {"eval_set": "e", "cost": True}
    )
    assert any(v["field"] == "skill_params.cost" for v in violations), violations


def test_numeric_bounds_are_enforced() -> None:
    _, violations = resolve_and_validate(
        "s", SCHEMA, {"eval_set": "e", "cost": -1}
    )
    assert any(v["field"] == "skill_params.cost" for v in violations)
    _, violations = resolve_and_validate("s", SCHEMA, {"eval_set": "e", "cost": 0})
    assert violations == []


def test_enums_are_enforced() -> None:
    _, violations = resolve_and_validate(
        "s", SCHEMA, {"eval_set": "e", "target_metric": "zzz"}
    )
    assert any(v["field"] == "skill_params.target_metric" for v in violations)
    _, violations = resolve_and_validate(
        "s", SCHEMA, {"eval_set": "e", "target_metric": "b"}
    )
    assert violations == []


def test_nested_structures_are_addressed_field_by_field() -> None:
    _, violations = resolve_and_validate(
        "s", SCHEMA, {"eval_set": "e", "nested": {"n": 0}}
    )
    assert [v["field"] for v in violations] == ["skill_params.nested.n"], violations


def test_extra_properties_follow_the_declared_policy() -> None:
    # additionalProperties: false → rejected, addressed per key.
    _, violations = resolve_and_validate("s", SCHEMA, {"eval_set": "e", "extra": 1})
    assert violations == [{
        "field": "skill_params.extra",
        "message": "unknown field (additionalProperties is false)",
    }]
    # additionalProperties: true → permitted exactly as declared.
    open_schema = dict(SCHEMA, additionalProperties=True)
    resolved, violations = resolve_and_validate(
        "s", open_schema, {"eval_set": "e", "extra": 1}
    )
    assert violations == []
    assert resolved["extra"] == 1


def test_defaults_are_applied_by_resolution_not_validation() -> None:
    # The raw object missing a defaulted field is not violated by validation…
    raw = {"eval_set": "e"}
    assert validate_resolved("s", SCHEMA, raw) == []
    # …resolution applies the declared defaults deliberately.
    resolved = apply_defaults(SCHEMA, raw)
    assert resolved == {
        "eval_set": "e", "target_metric": "a", "cost": 0.5, "flag": False,
    }
    # And the resolved object still validates once.
    assert validate_resolved("s", SCHEMA, resolved) == []


# --- bounds regressions at the API boundary ---------------------------------


def test_f12_invalid_bounds_rejected_before_session_side_effects() -> None:
    """The bounds reproduction: out-of-bounds DB parameters never start a session."""
    client = _client()
    for params in (
        {"target_latency_ms": -10},
        {"bench_duration_s": 99999},
    ):
        response = client.post(
            "/api/v1/research/start",
            headers=_headers(),
            json={
                "skill_id": "db-config-tuning",
                "subject_id": "default",
                "variant": "production",
                "skill_params": params,
            },
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"] == "skill_params_invalid"
        field = "skill_params." + next(iter(params))
        assert any(v["field"] == field for v in detail["violations"]), detail
    # Rejected before session side effects: no start ever reached the manager.
    assert _manager is not None
    assert _manager.start_calls == []


def test_missing_required_field_rejected_even_when_params_omitted() -> None:
    client = _client()
    for body in (
        {"skill_id": "prompt-engineering", "subject_id": "default", "variant": "production"},
        {
            "skill_id": "prompt-engineering", "subject_id": "default",
            "variant": "production", "skill_params": None,
        },
    ):
        response = client.post(
            "/api/v1/research/start", headers=_headers(), json=body
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"] == "skill_params_invalid"
        assert any(v["field"] == "skill_params" for v in detail["violations"])
    assert _manager is not None
    assert _manager.start_calls == []


def test_valid_request_returns_201_with_defaults_applied() -> None:
    client = _client()
    response = client.post(
        "/api/v1/research/start",
        headers=_headers(),
        json={
            "skill_id": "db-config-tuning",
            "subject_id": "default",
            "variant": "production",
            "skill_params": {"target_latency_ms": 25},
        },
    )
    assert response.status_code == 201
    assert _manager is not None
    forwarded = _manager.captured_kwargs["skill_params"]
    assert forwarded["target_latency_ms"] == 25
    # The declared default is applied deliberately by resolution.
    assert forwarded["bench_duration_s"] == 60


# --- OpenAPI request/response fixtures --------------------------------------


def _openapi_components() -> dict:
    return yaml.safe_load(
        (REPO_ROOT / "openapi.yaml").read_text(encoding="utf-8")
    )["components"]["schemas"]


def test_openapi_fixtures_match_server_authority() -> None:
    """Request fixtures validate against the documented request schema; the
    invalid response carries the field-addressed contract a UI form binds to."""
    from jsonschema import Draft202012Validator

    components = _openapi_components()
    request_schema = components["StartResearchRequest"]
    validator = Draft202012Validator(request_schema)

    valid_fixture = {
        "skill_id": "db-config-tuning",
        "subject_id": "default",
        "variant": "production",
        "skill_params": {"target_latency_ms": 25},
    }
    assert validator.is_valid(valid_fixture)

    client = _client()
    ok = client.post(
        "/api/v1/research/start", headers=_headers(), json=valid_fixture
    )
    assert ok.status_code == 201

    bad_fixture = dict(valid_fixture, skill_params={"target_latency_ms": -10})
    assert validator.is_valid(bad_fixture)  # the shape is legal…
    bad = client.post("/api/v1/research/start", headers=_headers(), json=bad_fixture)
    assert bad.status_code == 422  # …the declared bounds are the authority.
    violations = bad.json()["detail"]["violations"]
    assert all(set(v) == {"field", "message"} for v in violations)
    assert all(v["field"].startswith("skill_params") for v in violations)
