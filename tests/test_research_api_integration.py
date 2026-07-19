"""ARC-011 Phase 3 — HTTP-level integration tests (P3-015/016/017).

The back-compat suite (``test_research_api_compat.py``) covers the dual-shape
session contract. These tests exercise the **live router → helper path
end-to-end** for the enriched iteration + promotion endpoints, which until now
were only covered at the helper-unit level (``_enrich_iteration``,
``_inject_target_kind`` in ``test_generalization_falsifiability.py``).

Covered:

* **P3-015/016** — ``GET /research/{id}/iterations`` returns rows carrying the
  canonical ``skill_id``/``skill_phase``/``evidence_keys`` fields *alongside*
  the legacy ``search_phase`` (the additive canonical surface, §10 guarantee
  #4), exercised through the real FastAPI router.
* **P3-017** — ``POST /research/{id}/promote/preview`` carries ``target_kind``
  derived from the skill manifest's ``promotion_target.primary.kind`` when the
  registry is wired, and defaults to ``file_path`` for legacy sessions when it
  is not.
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

from src.api import promotion as promotion_module
from src.api import results as results_module
from src.api.promotion import router as promotion_router
from src.api.results import router as results_router
from src.config import settings

API_TOKEN = "test-autoresearch-token"


class _Store:
    """Minimal store stub with the session + iteration read surface."""

    def __init__(self) -> None:
        self._session = {
            "id": "res_int0001",
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "model_type": "direction",
            "tag": "test",
            "status": "running",
            "quick_mode": False,
            "max_iterations": 30,
            "max_budget_usd": 10.0,
            "workspace_path": "/tmp/test",
            "best_metric": 0.72,
            "best_iteration": 2,
            "total_api_cost_usd": 0.0,
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": None,
            "error_message": None,
            "resumed_from": None,
            "skill_name": "direction",
        }
        self._iterations = [
            {
                "id": 1,
                "research_id": "res_int0001",
                "iteration": 2,
                "primary_metric": 0.72,
                "metric_name": "auc",
                "all_gates_passed": 1,
                "decision": "promote",
                "description": "hpo-screened baseline",
                "config_snapshot": "agent_strategy: BALA",
                "search_phase": "validation",
                "metrics_json": (
                    '{"auc": 0.72, "phase_evidence": {"fold_a": 1, "fold_b": 1}}'
                ),
                "training_time_s": 120.0,
                "created_at": "2026-01-01T00:10:00Z",
            }
        ]

    async def ping(self) -> bool:
        return True

    async def record_audit_event(self, **kwargs: Any) -> None:
        return None

    async def get_session(self, research_id: str) -> Dict[str, Any] | None:
        if research_id == self._session["id"]:
            return dict(self._session)
        return None

    async def get_iterations(
        self,
        research_id: str,
        *,
        limit: int | None = None,
        cursor: tuple | None = None,
    ) -> list[Dict[str, Any]]:
        return [dict(it) for it in self._iterations]


class _FakePromoter:
    """Returns a canned preview dict; ``target_kind`` is injected downstream."""

    async def preview(self, research_id, *, scope="development", approval=None):
        return {
            "research_id": research_id,
            "iteration": 2,
            "model_type": "direction",
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "scope": scope,
            "target_path": "<host_configs>/instrument_configs/DOGE_USDT_15m.yaml",
            "best_metric": 0.72,
        }


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(results_router, prefix="/api/v1")
    app.include_router(promotion_router, prefix="/api/v1")
    return app


_store: _Store | None = None


@pytest.fixture(autouse=True)
def _wire(monkeypatch: pytest.MonkeyPatch):
    global _store
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)
    _store = _Store()
    results_module.init(_store, mlflow_external_url="http://localhost:5000")
    # Promotion router: no skill registry wired by default → target_kind must
    # default to file_path (the legacy-session path). Per-test wiring overrides.
    promotion_module.init(_FakePromoter(), _store, skill_registry=None)
    yield
    # Clear module globals so per-test registry wiring does not leak into other
    # suites (the falsifiability suite reads _registry). Uses the dedicated
    # reset() helper rather than hand-snapshotting the triple — semantically
    # equivalent (all three end at None) and robust to new globals being added.
    promotion_module.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(_create_test_app())


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


# ---------------------------------------------------------------------------
# P3-015 / P3-016 — GET /research/{id}/iterations (HTTP-level)
# ---------------------------------------------------------------------------


def test_get_iterations_returns_enriched_canonical_fields(client: TestClient):
    """The live iterations endpoint enriches each row with the canonical
    ``skill_id``/``skill_phase``/``evidence_keys`` fields, derived from the
    legacy ``search_phase`` + the metrics ``phase_evidence`` payload (P3-015,
    P3-016 read-time synthesis)."""
    response = client.get(
        "/api/v1/research/res_int0001/iterations", headers=_auth()
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]

    # Legacy field preserved (additive, not replacement).
    assert row["search_phase"] == "validation"
    # Canonical fields synthesized from legacy + metrics payload.
    assert row["skill_id"] == "ml-direction"  # ← model_type via alias registry
    assert row["skill_phase"] == "validation"  # ← search_phase
    # evidence_keys ← metrics.phase_evidence dict keys.
    assert sorted(row["evidence_keys"]) == ["fold_a", "fold_b"]


# ---------------------------------------------------------------------------
# P3-017 — POST /research/{id}/promote/preview (HTTP-level)
# ---------------------------------------------------------------------------


def test_promotion_preview_defaults_to_file_path_without_registry(
    client: TestClient,
):
    """With no skill registry wired (legacy session), the preview response
    carries ``target_kind = "file_path"`` — the incumbent ML promotion target."""
    response = client.post(
        "/api/v1/research/res_int0001/promote/preview",
        headers=_auth(),
        json={"scope": "development"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["target_kind"] == "file_path"
    # The original preview payload is preserved (additive enrichment).
    assert body["research_id"] == "res_int0001"
    assert body["best_metric"] == 0.72


class _StubManifest:
    def __init__(self, kind: str) -> None:
        # Minimal shim matching promotion._inject_target_kind's access pattern.
        class _Primary:
            def __init__(self, kind_: str) -> None:
                self.kind = kind_

        class _Target:
            def __init__(self, kind_: str) -> None:
                self.primary = _Primary(kind_)

        self.promotion_target = _Target(kind)


class _StubRegistry:
    """Returns a manifest with a configurable promotion target kind."""

    def __init__(self, kind: str) -> None:
        self._manifest = _StubManifest(kind)

    def get(self, skill_id: str):  # noqa: ARG002 — registry contract
        return self._manifest


@pytest.mark.parametrize(
    "kind",
    ["file_path", "registry_api", "git_branch", "artifact_store"],
)
def test_promotion_preview_carries_target_kind_from_registry(
    client: TestClient, kind: str
):
    """When the skill registry is wired, ``target_kind`` comes from the skill
    manifest's ``promotion_target.primary.kind`` — every ARC-011 §7 promotion
    target kind is surfaced to the UI through the same discriminator (P3-017)."""
    promotion_module.init(
        _FakePromoter(), _store, skill_registry=_StubRegistry(kind)
    )
    response = client.post(
        "/api/v1/research/res_int0001/promote/preview",
        headers=_auth(),
        json={"scope": "development"},
    )
    assert response.status_code == 200
    assert response.json()["target_kind"] == kind
