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
) -> None:
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
