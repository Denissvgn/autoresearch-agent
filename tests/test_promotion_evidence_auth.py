"""Part B (post-res_99469dfc1088) — PromotionEvidenceCollector must send
service-to-service admin Bearer-token auth on inference-service /admin/* calls.

Background: live evidence in session ``res_99469dfc1088`` (2026-05-20 23:00 UTC)
showed Gap 3's diagnostics emit ``adapter_preflight_status_404`` and
``reload_dry_run_status_404``. Investigation revealed two issues:

1. The deployed inference-service image was stale and did not contain the
   ``/admin/adapter/preflight`` / ``/admin/composite/reload`` routes (added
   in source on 2026-05-15 by commit 304dd5444, image built 2026-05-09).
   That's an infrastructure rebuild — out of this codebase's scope.

2. Once the routes are registered, the endpoints require a JWT admin
   Bearer token via ``require_admin_role`` in inference-service. The
   autoresearch-agent's PromotionEvidenceCollector was sending no
   ``Authorization`` header, so post-rebuild the calls would return 401
   instead of 404. Part B closes this by reading a token from
   ``settings.inference_service_auth_token`` (falling back to
   ``mlflow_service_auth_token``) and sending it on both POSTs.

These tests verify the new auth wiring directly:
- POST calls include the expected ``Authorization: Bearer <token>`` and
  ``X-Service-Name`` headers when a token is configured.
- When NO token is configured the collector short-circuits with the
  diagnostic error ``inference_auth_token_not_configured`` so operators
  see WHY the call wasn't even attempted, distinct from a real HTTP failure.
- The fallback from ``inference_service_auth_token`` to
  ``mlflow_service_auth_token`` works (operators with a single
  ``SERVICE_AUTH_TOKEN`` / ``ML_ADMIN_TOKEN`` do not need to set both).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from src.config import settings
from src.core.promotion_evidence_collector import PromotionEvidenceCollector
from src.core.results_store import ResultsStore


async def _seed(store: ResultsStore) -> str:
    session_id = "res_auth_test"
    await store.create_session(
        session_id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="auth",
        workspace_path="/ws",
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )
    await store.add_iteration(
        research_id=session_id,
        iteration=1,
        primary_metric=0.6443,
        metric_name="composite_direction_score",
        all_gates_passed=True,
        decision="keep",
        description="best",
        config_snapshot="instrument: DOGE_USDT\n",
        metrics_json=json.dumps({"primary_metric": 0.6443, "signal_rate": 0.18}),
        training_time_s=120.0,
        mlflow_run_id="run-42",
        canonical_config_hash="hash-42",
        search_phase="promotion_proposal",
    )
    return session_id


def _capture_factory(
    responses: List[Dict[str, Any]],
) -> Tuple[Any, List[Dict[str, Any]]]:
    """Like _http_factory in test_promotion_evidence_collector but records
    each POST's url/headers/json into a captures list for assertion."""
    captures: List[Dict[str, Any]] = []
    state = {"i": 0}

    def factory(timeout_s: float):
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        async def post(url, **kw):
            captures.append({
                "url": url,
                "headers": dict(kw.get("headers") or {}),
                "json": kw.get("json"),
            })
            i = state["i"]
            state["i"] += 1
            spec = (
                responses[i]
                if i < len(responses)
                else {"status_code": 200, "json": {}}
            )
            resp = MagicMock()
            resp.status_code = spec.get("status_code", 200)
            resp.json = MagicMock(return_value=spec.get("json", {}))
            return resp

        client.post = post
        return client

    return factory, captures


# --- Happy path: token set → Authorization header sent ----------------- #


@pytest.mark.asyncio
async def test_preflight_call_includes_bearer_token_when_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``inference_service_auth_token`` configured → POST carries
    ``Authorization: Bearer <token>`` and ``X-Service-Name`` on both
    ``/admin/adapter/preflight`` and ``/admin/composite/reload``.
    """
    monkeypatch.setattr(
        settings, "inference_service_auth_token", SecretStr("inf-token-abc"),
    )

    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    session_id = await _seed(store)

    factory, captures = _capture_factory([
        {"status_code": 200, "json": {"loaded": True}},
        {"status_code": 200, "json": {
            "composite_reload_passed": True,
            "rollback_ready": True,
        }},
    ])
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    patch = await collector.collect_and_patch(session_id, 1)

    # Both POSTs were attempted (no auth short-circuit).
    assert len(captures) == 2, f"Expected 2 POSTs, captured {len(captures)}"

    # Each carries the expected Authorization header...
    for cap in captures:
        assert cap["headers"].get("Authorization") == "Bearer inf-token-abc", (
            f"Authorization header missing or wrong on {cap['url']}: "
            f"{cap['headers']}"
        )
        # ...and the X-Service-Name service identifier.
        assert cap["headers"].get("X-Service-Name"), (
            f"X-Service-Name header missing on {cap['url']}"
        )

    # Endpoint URLs are the expected admin paths.
    urls = {cap["url"] for cap in captures}
    assert any("/admin/adapter/preflight" in u for u in urls)
    assert any("/admin/composite/reload" in u for u in urls)

    # Success branches populated the patch.
    assert patch["inference_parity"]["adapter_loading_passed"] is True
    assert patch["inference_parity"]["composite_reload_passed"] is True
    assert "inference_preflight" not in patch.get(
        "promotion_evidence_collection_errors", {}
    )


# --- No-token path: short-circuit with diagnostic error --------------- #


@pytest.mark.asyncio
async def test_preflight_returns_token_not_configured_when_unset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No token configured (neither ``inference_service_auth_token`` nor
    ``mlflow_service_auth_token``) → both POSTs short-circuit and the
    collector records ``inference_auth_token_not_configured`` for each.

    No HTTP call is made — verified by the empty captures list.
    """
    monkeypatch.setattr(settings, "inference_service_auth_token", None)
    monkeypatch.setattr(settings, "mlflow_service_auth_token", None)

    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    session_id = await _seed(store)

    factory, captures = _capture_factory([])
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    patch = await collector.collect_and_patch(session_id, 1)

    # No POSTs attempted — the helper returned None before the HTTP call.
    assert captures == [], (
        f"No HTTP call should be made without a token; got: {captures}"
    )

    errors = patch.get("promotion_evidence_collection_errors", {})
    assert errors.get("inference_preflight") == "inference_auth_token_not_configured"
    assert errors.get("inference_reload") == "inference_auth_token_not_configured"

    # The inference_parity payload was NOT populated (we never got the success
    # branch); signal_health from the local-signal_rate path IS still populated.
    assert "inference_parity" not in patch
    assert patch.get("signal_health", {}).get("operational", {}).get("signal_rate") == 0.18


# --- Fallback: mlflow_service_auth_token used when dedicated unset --- #


@pytest.mark.asyncio
async def test_reload_dry_run_uses_mlflow_token_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dedicated ``inference_service_auth_token`` unset but
    ``mlflow_service_auth_token`` set → the fallback path picks up the
    mlflow token and includes it on the reload-dry-run POST. Operators
    with a single ``SERVICE_AUTH_TOKEN`` / ``ML_ADMIN_TOKEN`` env var do
    not need to configure two separate tokens.
    """
    monkeypatch.setattr(settings, "inference_service_auth_token", None)
    monkeypatch.setattr(
        settings, "mlflow_service_auth_token", SecretStr("mlflow-token-xyz"),
    )

    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    session_id = await _seed(store)

    factory, captures = _capture_factory([
        {"status_code": 200, "json": {"loaded": True}},
        {"status_code": 200, "json": {
            "composite_reload_passed": True,
            "rollback_ready": True,
        }},
    ])
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    await collector.collect_and_patch(session_id, 1)

    # Find the reload POST and assert it carried the mlflow fallback token.
    reload_caps = [c for c in captures if "/admin/composite/reload" in c["url"]]
    assert len(reload_caps) == 1, (
        f"Expected exactly one /admin/composite/reload POST; got {len(reload_caps)}"
    )
    assert reload_caps[0]["headers"].get("Authorization") == "Bearer mlflow-token-xyz", (
        "Reload-dry-run POST must use the mlflow_service_auth_token fallback "
        f"when inference_service_auth_token is unset; got: {reload_caps[0]['headers']}"
    )

    # And so does the preflight POST.
    preflight_caps = [c for c in captures if "/admin/adapter/preflight" in c["url"]]
    assert preflight_caps[0]["headers"].get("Authorization") == "Bearer mlflow-token-xyz"
