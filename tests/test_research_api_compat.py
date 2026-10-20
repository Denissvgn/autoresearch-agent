"""Research-API backward-compatibility test suite (ARC-011 P3-020, GEN-001/002/004).

Validates the dual-shape guarantee (§10 #1, #4): legacy clients sending
``{instrument, timeframe, model_type}`` still work identically, and every
response carries **both** canonical (``skill_id``/``subject_id``/``variant``)
and legacy (``model_type``/``instrument``/``timeframe``) fields.
"""

from __future__ import annotations

import os
from typing import Any, Dict

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import research as research_module
from src.api.research import router as research_router
from src.config import settings

API_TOKEN = "test-autoresearch-token"


class FakeSessionManager:
    """Minimal stub — returns a canned session dict for start_session."""

    active_count = 0
    _active_pipelines: dict[str, object] = {}

    def __init__(self) -> None:
        # ARC-011 review C1: capture forwarded kwargs so tests can assert the
        # canonical shape actually reaches the session manager.
        self.captured_kwargs: Dict[str, Any] = {}

    async def start_session(self, **kwargs: Any) -> Dict[str, Any]:
        self.captured_kwargs = dict(kwargs)
        return {
            "id": "res_test0001",
            "instrument": kwargs.get("instrument", ""),
            "timeframe": kwargs.get("timeframe", ""),
            "model_type": kwargs.get("model_type", ""),
            # ARC-012 P7-005: the real store now persists the canonical
            # identity natively — mirror it (a non-ML row carries
            # model_type="" and its skill_id only here).
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
            "total_api_cost_usd": 0.0,
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": None,
            "error_message": None,
            "resumed_from": None,
            "skill_name": kwargs.get("skill_id", "") or kwargs.get("model_type", ""),
        }

    async def start_pipeline(self, **kwargs: Any) -> Dict[str, Any]:
        return {"id": "pipe_test001", "status": "running", **kwargs}


class FakeStore:
    def __init__(self) -> None:
        self.audit_events: list[dict[str, Any]] = []
        self.appended_events: list[dict[str, Any]] = []
        self._sessions: list[dict[str, Any]] = [
            {
                "id": "res_test0001",
                "instrument": "DOGE_USDT",
                "timeframe": "15m",
                "model_type": "direction",
                "tag": "test",
                "status": "running",
                "quick_mode": False,
                "max_iterations": 30,
                "max_budget_usd": 10.0,
                "workspace_path": "/tmp/test",
                "best_metric": None,
                "best_iteration": None,
                "total_api_cost_usd": 0.0,
                "started_at": "2026-01-01T00:00:00Z",
                "completed_at": None,
                "error_message": None,
                "resumed_from": None,
                "skill_name": "direction",
            }
        ]

    async def append_event(self, **kwargs: Any) -> None:
        self.appended_events.append(dict(kwargs))
        return None

    async def ping(self) -> bool:
        return True

    async def record_audit_event(self, **kwargs: Any) -> None:
        self.audit_events.append(kwargs)

    async def get_session(self, research_id: str) -> Dict[str, Any] | None:
        for s in self._sessions:
            if s["id"] == research_id:
                return dict(s)
        return None

    async def list_sessions(
        self, *, status: str | None = None, model_type: str | None = None,
        instrument: str | None = None, limit: int | None = None,
        offset: int = 0, cursor: tuple | None = None,
    ) -> list[Dict[str, Any]]:
        items = self._sessions
        if status:
            items = [s for s in items if s["status"] == status]
        if model_type:
            items = [s for s in items if s["model_type"] == model_type]
        if instrument:
            items = [s for s in items if s["instrument"] == instrument]
        return [dict(s) for s in items]

    async def count_sessions(
        self, *, status: str | None = None, model_type: str | None = None,
        instrument: str | None = None,
    ) -> int:
        return len(await self.list_sessions(
            status=status, model_type=model_type, instrument=instrument,
        ))


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(research_router, prefix="/api/v1")
    app.state.audit_store = FakeStore()
    return app


_test_store: FakeStore | None = None


@pytest.fixture(autouse=True)
def configure(monkeypatch: pytest.MonkeyPatch):
    global _test_store
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)
    _test_store = FakeStore()
    research_module.init(FakeSessionManager(), _test_store)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_test_app())


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


# --- GEN-001: legacy request shape is translated, then skill-checked ---

def test_legacy_start_of_uninstalled_trio_returns_404_naming_translated_skill(
    client: TestClient,
):
    """ARC-012 P7-010 / D3: a legacy ``{model_type: direction}`` request is
    translated through the alias map (→ ``ml-direction``) and then faces the
    same installed-skill check as a canonical request. ``ml-direction`` is
    not installed → 404 ``skill_not_found`` naming the translated id — never
    a 201 for a session that would crash on its first tick (blocker B2/S1),
    and never a special "legacy rejected" error."""
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "model_type": "direction",
        },
    )
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error"] == "skill_not_found"
    assert detail["skill_id"] == "ml-direction"
    assert "prompt-engineering" in detail["available"]


def test_legacy_start_of_installed_skill_returns_201_with_dual_shape(
    client: TestClient,
):
    """The legacy shape still starts a session when it names an installed
    skill (identity fallback: a non-alias ``model_type`` is its own skill
    id). Per D1 the non-ML skill has no legacy alias, so the dual-shape
    response carries ``model_type=""`` — the caller's legacy value lost to
    the canonical identity, and the conflict is audited."""
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "instrument": "default",
            "timeframe": "production",
            "model_type": "prompt-engineering",
            "skill_params": {"eval_set": "eval/eval_set.jsonl"},
        },
    )
    assert response.status_code == 201
    body = response.json()
    # Canonical fields.
    assert body["skill_id"] == "prompt-engineering"
    assert body["subject_id"] == "default"
    assert body["variant"] == "production"
    # Legacy fields derived from canonical (dual-shape, P7-006/D1).
    assert body["model_type"] == ""
    assert body["instrument"] == "default"
    assert body["timeframe"] == "production"
    assert "links" in body


# --- Canonical request → 201 with dual-shape body ---

def test_canonical_start_returns_201_with_dual_shape(client: TestClient):
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "skill_id": "prompt-engineering",
            "subject_id": "default",
            "skill_params": {"eval_set": "eval/eval_set.jsonl"},
            "variant": "production",
        },
    )
    assert response.status_code == 201
    body = response.json()
    # Canonical fields.
    assert body["skill_id"] == "prompt-engineering"
    assert body["subject_id"] == "default"
    assert body["variant"] == "production"
    # Legacy fields derived from canonical (dual-shape). ARC-012 P7-006/D1:
    # a non-ML skill has no legacy alias — model_type is "", never the id.
    assert body["model_type"] == ""
    assert body["instrument"] == "default"
    assert body["timeframe"] == "production"


# --- Unknown skill_id → 404 with installable-skills hint ---

def test_canonical_start_unknown_skill_returns_404(client: TestClient):
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={"skill_id": "nonexistent-skill", "subject_id": "x", "variant": "y"},
    )
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error"] == "skill_not_found"
    assert "available" in detail


# --- GEN-002: GET /research/{id} still returns legacy fields ---

def test_get_research_returns_dual_shape(client: TestClient):
    response = client.get(
        "/api/v1/research/res_test0001", headers=auth_headers()
    )
    assert response.status_code == 200
    body = response.json()
    # Legacy fields (GEN-002).
    assert body["instrument"] == "DOGE_USDT"
    assert body["timeframe"] == "15m"
    assert body["model_type"] == "direction"
    # Canonical fields (dual-shape).
    assert body["skill_id"] == "ml-direction"
    assert body["subject_id"] == "DOGE_USDT"
    assert body["variant"] == "15m"


# --- Both shapes present → canonical wins ---

def test_both_shapes_canonical_wins(client: TestClient):
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "skill_id": "prompt-engineering",
            "subject_id": "default",
            "skill_params": {"eval_set": "eval/eval_set.jsonl"},
            "variant": "production",
            "model_type": "prompt-engineering",  # also legacy — canonical wins
        },
    )
    assert response.status_code == 201


# --- Missing both shapes → 422 ---

def test_missing_both_shapes_returns_422(client: TestClient):
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={"tag": "no-shape"},
    )
    assert response.status_code == 422


# ====================================================================
# Phase-3 review fixes — A-stream tests
# ====================================================================

# --- A1: conflicting shapes → canonical wins (not just "both present") ---

def test_conflicting_shapes_canonical_overrides_legacy(client: TestClient):
    """When skill_id and model_type disagree, canonical (skill_id) wins and
    the conflicting legacy value is overridden — not silently kept (P3-013
    risk fix)."""
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "skill_id": "prompt-engineering",   # → model_type "prompt-engineering"
            "subject_id": "default",
            "skill_params": {"eval_set": "eval/eval_set.jsonl"},
            "variant": "production",
            "model_type": "volatility",        # CONFLICTS — canonical must win
            "instrument": "BTC_USDT",          # CONFLICTS — canonical must win
            "timeframe": "1h",                 # CONFLICTS — canonical must win
        },
    )
    assert response.status_code == 201
    body = response.json()
    # Canonical values must win over the conflicting legacy ones. P7-006/D1:
    # the canonical model_type of a non-ML skill is "" (no legacy alias) —
    # the conflicting legacy "volatility" must not survive.
    assert body["model_type"] == "", (
        f"canonical lost to conflicting legacy: model_type={body['model_type']}"
    )
    assert body["instrument"] == "default"
    assert body["timeframe"] == "production"


def test_conflicting_shapes_recorded_in_audit(client: TestClient):
    """Conflicts are audited as a warning (P3-013 risk: "warn in audit")."""
    client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "skill_id": "prompt-engineering",
            "subject_id": "default",
            "skill_params": {"eval_set": "eval/eval_set.jsonl"},
            "variant": "production",
            "model_type": "volatility",
        },
    )
    assert _test_store is not None
    assert _test_store is not None
    conflict_audits = [
        e for e in _test_store.audit_events
        if e.get("action") == "research.shape_conflict"
    ]
    assert len(conflict_audits) == 1, (
        f"expected 1 shape_conflict audit, got {len(conflict_audits)}"
    )
    meta = conflict_audits[0].get("request_metadata", {})
    conflicts = meta.get("conflicts", [])
    assert any(c["field"] == "model_type" for c in conflicts), (
        f"model_type conflict not recorded: {conflicts}"
    )


# --- A2: skill_params validation ---

def test_skill_params_valid_passes(client: TestClient):
    """Valid skill_params (matching the skill's param_schema) → 201."""
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "skill_id": "prompt-engineering",
            "subject_id": "default",
            "variant": "production",
            "skill_params": {"eval_set": "eval/eval_set.jsonl"},
        },
    )
    assert response.status_code == 201


def test_skill_params_unknown_key_returns_422(client: TestClient):
    """Unknown skill_params key → 422 with field pointer (additionalProperties:
    false)."""
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "skill_id": "prompt-engineering",
            "subject_id": "default",
            "variant": "production",
            "skill_params": {"bogus_field": 42},
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "skill_params_invalid"
    assert any("bogus_field" in v["field"] for v in detail["violations"])


def test_skill_params_wrong_type_returns_422(client: TestClient):
    """Wrong type in skill_params → 422 with field pointer."""
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "skill_id": "prompt-engineering",
            "subject_id": "default",
            "variant": "production",
            "skill_params": {"eval_set": 123},
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "skill_params_invalid"
    assert any("eval_set" in v["field"] for v in detail["violations"])


# --- A3: GET /research items have dual-shape fields ---

def test_list_research_items_have_dual_shape(client: TestClient):
    """GET /research returns items with both canonical and legacy fields
    (P3-014 applied to list_research — previously only single sessions had
    dual-shape)."""
    response = client.get("/api/v1/research", headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert len(body["items"]) > 0
    item = body["items"][0]
    # Legacy fields.
    assert item["model_type"] == "direction"
    assert item["instrument"] == "DOGE_USDT"
    assert item["timeframe"] == "15m"
    # Canonical fields (dual-shape).
    assert item["skill_id"] == "ml-direction"
    assert item["subject_id"] == "DOGE_USDT"
    assert item["variant"] == "15m"
    # Links block.
    assert "links" in item
    assert item["links"]["self"] == "/research/res_test0001"


# --- A4: Pipeline rows are the documented empty-canonical case ---

def test_pipeline_row_dual_shape_fields():
    """A pipeline row (``model_type="pipeline"``) is a multi-skill container.
    With the identity alias fallback every ``model_type`` maps to a
    ``skill_id`` value, and ``subject_id``/``variant`` derive from the legacy
    fields (value-neutral labels)."""
    from src.api.research import _dual_shape_session

    pipeline_row = {
        "id": "pipe_test001",
        "model_type": "pipeline",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "status": "running",
    }
    shaped = _dual_shape_session(pipeline_row)
    # Legacy fields always populated.
    assert shaped["model_type"] == "pipeline"
    assert shaped["instrument"] == "DOGE_USDT"
    assert shaped["timeframe"] == "15m"
    # Canonical fields follow the identity fallback (pipeline is not an
    # installed skill, but the alias never yields a missing value).
    assert shaped["skill_id"] == "pipeline"
    assert shaped["subject_id"] == "DOGE_USDT"  # ← instrument passthrough
    assert shaped["variant"] == "15m"            # ← timeframe passthrough


# ====================================================================
# ARC-011 implementation review C1 (2026-08-15) — canonical fields are
# forwarded, not validated-then-dropped
# ====================================================================


def _session_manager() -> FakeSessionManager:
    mgr = research_module._session_manager
    assert isinstance(mgr, FakeSessionManager)
    return mgr


def test_canonical_fields_forwarded_to_session_manager(client: TestClient):
    """C1: ``{skill_id, subject_id, variant, skill_params}`` survive the trip
    to ``start_session`` — previously only the translated legacy fields were
    passed, so canonical HPO params were silently ignored and ``skill_id``
    never reached ``ResearchConfig``."""
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "skill_id": "prompt-engineering",
            "subject_id": "default",
            "variant": "production",
            "skill_params": {"eval_set": "eval/eval_set.jsonl", "target_metric": "f1"},
        },
    )
    assert response.status_code == 201
    captured = _session_manager().captured_kwargs
    assert captured["skill_id"] == "prompt-engineering"
    assert captured["skill_params"]["eval_set"] == "eval/eval_set.jsonl"
    assert captured["skill_params"]["target_metric"] == "f1"
    # Defaults are applied deliberately by the canonical resolution path
    # (validation never inserts values — resolution does).
    assert captured["skill_params"]["cost_ceiling_per_run_usd"] == 0.50
    assert captured["subject_id"] == "default"
    assert captured["variant"] == "production"
    # The translated legacy shape is still passed alongside (dual shape).
    # P7-006/D1: a non-ML skill translates to model_type="" — never the id.
    assert captured["model_type"] == ""
    assert captured["instrument"] == "default"
    assert captured["timeframe"] == "production"


def test_canonical_params_recorded_in_start_audit(client: TestClient):
    """C1: the research.start audit metadata now records the winning
    canonical values (previously only shape_conflict records existed, never
    the values that won)."""
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "skill_id": "prompt-engineering",
            "subject_id": "default",
            "variant": "production",
            "skill_params": {"eval_set": "eval/eval_set.jsonl", "target_metric": "f1"},
        },
    )
    assert response.status_code == 201
    assert _test_store is not None
    start_events = [
        e for e in _test_store.audit_events
        if e.get("action") == "research.start"
    ]
    assert len(start_events) == 1
    metadata = start_events[0]["request_metadata"]
    assert metadata["skill_id"] == "prompt-engineering"
    assert metadata["skill_params"] == {
        "eval_set": "eval/eval_set.jsonl", "target_metric": "f1",
    }
    assert metadata["subject_id"] == "default"
    assert metadata["variant"] == "production"


def test_legacy_start_translates_to_canonical_fields(client: TestClient):
    """ARC-012 P7-010/D3: a legacy request is translated to the canonical
    shape (alias map, then legacy identity fields) *before* it reaches the
    session manager — the manager always sees a skill_id, never a
    model_type-only payload that would 201-then-crash (B2)."""
    response = client.post(
        "/api/v1/research/start",
        headers=auth_headers(),
        json={
            "instrument": "default",
            "timeframe": "production",
            "model_type": "prompt-engineering",
            "skill_params": {"eval_set": "eval/eval_set.jsonl"},
        },
    )
    assert response.status_code == 201
    captured = _session_manager().captured_kwargs
    assert captured["skill_id"] == "prompt-engineering"
    assert captured["subject_id"] == "default"
    assert captured["variant"] == "production"
    # Non-ML skills carry no legacy alias (D1): model_type arrives empty.
    assert captured["model_type"] == ""
    # The audit metadata records the winning canonical identity.
    assert _test_store is not None
    start_events = [
        e for e in _test_store.audit_events
        if e.get("action") == "research.start"
    ]
    metadata = start_events[0]["request_metadata"]
    assert metadata["skill_id"] == "prompt-engineering"
