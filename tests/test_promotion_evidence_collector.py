"""Tests for the PromotionEvidenceCollector.

Fix 3: at session-end auto-promotion, the orchestrator should run a
server-side evidence collector to resolve infrastructure-side blockers
(inference adapter load / composite reload / smoke validation / signal
health) that the autoresearch agent itself cannot produce. This module
verifies the collector's contract.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.promotion_evidence_collector import PromotionEvidenceCollector
from src.core.results_store import ResultsStore


async def _seed(store: ResultsStore, *, metrics: Dict[str, Any]) -> str:
    session_id = "res_evidence_test"
    await store.create_session(
        session_id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="evidence",
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
        metrics_json=json.dumps(metrics),
        training_time_s=120.0,
        mlflow_run_id="run-42",
        canonical_config_hash="hash-42",
        search_phase="promotion_proposal",
    )
    return session_id


def _http_factory(responses: List[Dict[str, Any]]):
    """Return a factory creating an AsyncClient whose POSTs replay
    ``responses`` in order (one per call).
    """

    state = {"i": 0}

    def factory(timeout_s: float):
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        async def post(url, **kw):
            i = state["i"]
            state["i"] += 1
            spec = responses[i] if i < len(responses) else {"status_code": 200, "json": {}}
            resp = MagicMock()
            resp.status_code = spec.get("status_code", 200)
            resp.json = MagicMock(return_value=spec.get("json", {}))
            return resp

        client.post = post
        return client

    return factory


@pytest.mark.asyncio
async def test_collector_patches_signal_health_from_signal_rate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Part B (post-res_99469dfc1088): inference-service /admin/* endpoints
    # now require a Bearer token. Provide one so the existing happy-path
    # assertions continue to exercise the success branch.
    from pydantic import SecretStr
    from src.config import settings as _settings
    monkeypatch.setattr(
        _settings, "inference_service_auth_token", SecretStr("test-token"),
    )

    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    session_id = await _seed(
        store,
        metrics={
            "primary_metric": 0.6443,
            "signal_rate": 0.18,
        },
    )

    factory = _http_factory(
        [
            {"status_code": 200, "json": {"loaded": True}},
            {"status_code": 200, "json": {
                "composite_reload_passed": True,
                "rollback_ready": True,
            }},
        ]
    )
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    patch = await collector.collect_and_patch(session_id, 1)

    assert patch.get("signal_health", {}).get("operational", {}).get("signal_rate") == 0.18
    assert patch.get("inference_parity", {}).get("adapter_loading_passed") is True
    assert patch.get("inference_parity", {}).get("composite_reload_passed") is True

    row = await store.get_iteration(session_id, 1)
    persisted = json.loads(row["metrics_json"])
    assert persisted["signal_health"]["operational"]["signal_rate"] == 0.18
    assert persisted["inference_parity"]["adapter_loading_passed"] is True


@pytest.mark.asyncio
async def test_collector_records_error_on_inference_http_failure(
    tmp_path: Path,
) -> None:
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    session_id = await _seed(
        store, metrics={"signal_rate": 0.2},
    )

    factory = _http_factory(
        [
            {"status_code": 500, "json": {}},
            {"status_code": 500, "json": {}},
        ]
    )
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    patch = await collector.collect_and_patch(session_id, 1)

    errors = patch.get("promotion_evidence_collection_errors", {})
    assert "inference_preflight" in errors
    assert "inference_reload" in errors


@pytest.mark.asyncio
async def test_collector_idempotent_when_evidence_already_present(
    tmp_path: Path,
) -> None:
    """When the iteration already has the full evidence, no HTTP calls are
    made (sub-collectors short-circuit on presence checks)."""
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    session_id = await _seed(
        store,
        metrics={
            "signal_rate": 0.2,
            "signal_health": {
                "operational": {"signal_rate": 0.2},
                "probability": {"mean": 0.55},
            },
            "inference_parity": {
                "adapter_loading_passed": True,
                "composite_reload_passed": True,
            },
            "smoke_validation": {"passed": True},
        },
    )

    factory = _http_factory([])
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    patch = await collector.collect_and_patch(session_id, 1)
    assert patch == {}


@pytest.mark.asyncio
async def test_collector_no_op_when_iteration_missing(
    tmp_path: Path,
) -> None:
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    await store.create_session(
        session_id="res_missing",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="t",
        workspace_path="/ws",
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )

    factory = _http_factory([])
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    patch = await collector.collect_and_patch("res_missing", 999)
    assert patch == {}


@pytest.mark.asyncio
async def test_collector_passes_through_existing_smoke_validation(
    tmp_path: Path,
) -> None:
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    session_id = await _seed(
        store,
        metrics={
            "signal_rate": 0.2,
            "paper_validation": {"passed": True},
        },
    )

    factory = _http_factory(
        [
            {"status_code": 200, "json": {"loaded": True}},
            {"status_code": 200, "json": {"composite_reload_passed": True}},
        ]
    )
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    patch = await collector.collect_and_patch(session_id, 1)
    # Smoke not in patch because existing paper_validation already passed.
    assert "smoke_validation" not in patch


# ---------------------------------------------------------------------------
# Option B — /admin/paper/replay smoke-validation collection
# ---------------------------------------------------------------------------


def _capture_http_factory(responses):
    """Factory recording each POST's url/json so tests can assert which
    endpoints were (not) called. Replays ``responses`` in order."""
    captures = []
    state = {"i": 0}

    def factory(timeout_s: float):
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        async def post(url, **kw):
            captures.append({"url": url, "json": kw.get("json")})
            i = state["i"]
            state["i"] += 1
            spec = responses[i] if i < len(responses) else {"status_code": 200, "json": {}}
            resp = MagicMock()
            resp.status_code = spec.get("status_code", 200)
            resp.json = MagicMock(return_value=spec.get("json", {}))
            return resp

        client.post = post
        return client

    return factory, captures


@pytest.mark.asyncio
async def test_collector_emits_smoke_validation_when_paper_replay_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No pre-staged artifact → collector calls /admin/paper/replay; a
    passing replay yields smoke_validation evidence the gate accepts."""
    from pydantic import SecretStr
    from src.config import settings as _settings
    monkeypatch.setattr(
        _settings, "inference_service_auth_token", SecretStr("test-token"),
    )

    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    session_id = await _seed(store, metrics={"signal_rate": 0.2})

    factory = _http_factory([
        {"status_code": 200, "json": {"loaded": True}},                  # preflight
        {"status_code": 200, "json": {"composite_reload_passed": True}}, # reload
        {"status_code": 200, "json": {                                   # paper/replay
            "passed": True,
            "composite_reload_passed": True,
            "prior_version_left_intact_on_failure": True,
            "source": "paper_replay_with_candidate_artifact_validated",
        }},
    ])
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    patch = await collector.collect_and_patch(session_id, 1)

    assert patch["smoke_validation"]["passed"] is True
    assert patch["smoke_validation"]["source"].endswith("_artifact_validated")
    assert "smoke_validation" not in patch.get(
        "promotion_evidence_collection_errors", {}
    )


@pytest.mark.asyncio
async def test_collector_merges_signal_health_from_paper_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fix B2: the paper-replay ran the candidate through the real serving
    path, so its signal_health (probability summary + hold_rate) is patched in
    as dev-scope signal-health evidence the gate needs."""
    from pydantic import SecretStr
    from src.config import settings as _settings
    monkeypatch.setattr(
        _settings, "inference_service_auth_token", SecretStr("test-token"),
    )

    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    session_id = await _seed(store, metrics={"signal_rate": 0.2})

    factory = _http_factory([
        {"status_code": 200, "json": {"loaded": True}},                  # preflight
        {"status_code": 200, "json": {"composite_reload_passed": True}}, # reload
        {"status_code": 200, "json": {                                   # paper/replay
            "passed": True,
            "composite_reload_passed": True,
            "prior_version_left_intact_on_failure": True,
            "source": "paper_replay_with_candidate_artifact_validated",
            "signal_health": {
                "probability_mean": 0.61,
                "probability_std": 0.08,
                "entropy_mean": 0.74,
                "signal_rate": 0.58,
                "hold_rate": 0.42,
            },
        }},
    ])
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    patch = await collector.collect_and_patch(session_id, 1)

    sh = patch["signal_health"]
    assert sh["probability_mean"] == 0.61
    assert sh["entropy_mean"] == 0.74
    assert sh["hold_rate"] == 0.42
    # Persisted to the iteration so the promotion preview reads it.
    persisted = await store.get_iteration(session_id, 1)
    import json as _json
    assert _json.loads(persisted["metrics_json"])["signal_health"]["entropy_mean"] == 0.74


@pytest.mark.asyncio
async def test_collector_records_error_when_paper_replay_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-passing paper-replay (e.g. sample not staged) keeps the gate
    hard and surfaces a precise error in collection_errors."""
    from pydantic import SecretStr
    from src.config import settings as _settings
    monkeypatch.setattr(
        _settings, "inference_service_auth_token", SecretStr("test-token"),
    )

    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    session_id = await _seed(store, metrics={"signal_rate": 0.2})

    factory = _http_factory([
        {"status_code": 200, "json": {"loaded": True}},
        {"status_code": 200, "json": {"composite_reload_passed": True}},
        {"status_code": 200, "json": {
            "passed": False,
            "error": "sample_not_staged: /data/samples/DOGE_USDT_15m.parquet",
        }},
    ])
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    patch = await collector.collect_and_patch(session_id, 1)

    assert "smoke_validation" not in patch  # gate stays hard
    errors = patch.get("promotion_evidence_collection_errors", {})
    assert errors.get("smoke_validation", "").startswith(
        "paper_replay_not_passed: sample_not_staged"
    )


@pytest.mark.asyncio
async def test_collector_passthrough_skips_paper_replay_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When metrics already carry a passing paper_validation, the collector
    must NOT POST to /admin/paper/replay (the passthrough branch wins)."""
    from pydantic import SecretStr
    from src.config import settings as _settings
    monkeypatch.setattr(
        _settings, "inference_service_auth_token", SecretStr("test-token"),
    )

    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    session_id = await _seed(
        store,
        metrics={"signal_rate": 0.2, "paper_validation": {"passed": True}},
    )

    factory, captures = _capture_http_factory([
        {"status_code": 200, "json": {"loaded": True}},
        {"status_code": 200, "json": {"composite_reload_passed": True}},
    ])
    collector = PromotionEvidenceCollector(store, http_client_factory=factory)
    await collector.collect_and_patch(session_id, 1)

    # preflight + reload may be called, but paper/replay must NOT be.
    urls = {c["url"] for c in captures}
    assert not any("/admin/paper/replay" in u for u in urls), (
        f"paper/replay must be skipped when paper_validation is pre-staged; "
        f"captured URLs: {urls}"
    )
