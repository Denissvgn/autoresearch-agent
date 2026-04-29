from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from server.config import settings
from server.core.results_store import ResultsStore
from server.core.service_preflight import (
    ServicePreflightError,
    require_preflight_ready,
    run_service_preflight,
    sanitize_service_url,
)


def _configure_preflight(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "workspace"))
    monkeypatch.setattr(settings, "preflight_enabled", True)
    monkeypatch.setattr(settings, "allow_unready_services", False)
    monkeypatch.setattr(settings, "preflight_timeout_s", 0.5)
    monkeypatch.setattr(settings, "artifact_logging_required", True)
    monkeypatch.setattr(settings, "mlflow_tracking_uri", "http://mlflow:5000")
    monkeypatch.setattr(settings, "mlflow_service_url", "http://mlflow-service:8000")
    monkeypatch.setattr(settings, "data_ingest_url", "http://data-ingest:8000")
    monkeypatch.setattr(settings, "ensemble_trainer_url", "http://ensemble-trainer:8000")
    monkeypatch.setattr(settings, "rl_trainer_url", "http://rl-trainer:8000")
    monkeypatch.setattr(settings, "feature_service_url", "http://feature-service:8000")
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://minio:9000")
    monkeypatch.setattr(settings, "mlflow_s3_endpoint_url", None)


def _healthy_transport() -> httpx.MockTransport:
    ready_paths = {
        ("mlflow", "/health"),
        ("mlflow-service", "/health"),
        ("data-ingest", "/readiness"),
        ("ensemble-trainer", "/health"),
        ("rl-trainer", "/health/ready"),
        ("feature-service", "/health"),
        ("minio", "/minio/health/ready"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.url.host, request.url.path)
        if key in ready_paths:
            return httpx.Response(200, json={"status": "ready"})
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_service_preflight_records_healthy_services(monkeypatch, tmp_path):
    _configure_preflight(monkeypatch, tmp_path)
    async with httpx.AsyncClient(transport=_healthy_transport()) as client:
        result = await run_service_preflight(model_type="direction", client=client)

    assert result["schema_version"] == "autoresearch_service_preflight.v1"
    assert result["status"] == "ready"
    assert result["required_failures"] == []
    assert result["services"]["data_ingest"]["checked_url"].endswith("/readiness")
    assert result["services"]["artifact_store"]["url"] == "http://minio:9000"
    assert all(check["status"] == "ready" for check in result["services"].values())


@pytest.mark.asyncio
async def test_service_preflight_blocks_unhealthy_required_service(
    monkeypatch,
    tmp_path,
):
    _configure_preflight(monkeypatch, tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "mlflow-service":
            return httpx.Response(503, json={"status": "down"})
        return httpx.Response(200, json={"status": "ready"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await run_service_preflight(model_type="rl", client=client)

    assert result["status"] == "failed"
    assert result["required_failures"] == ["mlflow_service"]
    with pytest.raises(ServicePreflightError, match="mlflow_service"):
        require_preflight_ready(result)


@pytest.mark.asyncio
async def test_session_start_persists_preflight_in_manifest(monkeypatch, tmp_path):
    _configure_preflight(monkeypatch, tmp_path)

    import server.core.session_manager as session_manager_module

    class FakeOrchestrator:
        def __init__(self, store) -> None:
            self.run_called = False

        async def run(self, config) -> None:
            self.run_called = True

        def request_stop(self, research_id: str) -> None:
            pass

        def request_pause(self, research_id: str) -> None:
            pass

        def request_resume(self, research_id: str) -> None:
            pass

    fake_orchestrator = FakeOrchestrator(None)

    async def healthy_preflight(*, model_type: str):
        return {
            "schema_version": "autoresearch_service_preflight.v1",
            "status": "ready",
            "model_type": model_type,
            "required_ready": True,
            "override_allowed_unready": False,
            "services": {
                "mlflow_service": {
                    "url": "http://mlflow-service:8000",
                    "required": True,
                    "status": "ready",
                }
            },
            "required_failures": [],
        }

    monkeypatch.setattr(
        session_manager_module,
        "AgentOrchestrator",
        lambda store: fake_orchestrator,
    )
    monkeypatch.setattr(
        session_manager_module,
        "run_service_preflight",
        healthy_preflight,
    )

    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    manager = session_manager_module.SessionManager(store)

    session = await manager.start_session(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        max_iterations=1,
    )
    await asyncio.sleep(0)

    manifest = json.loads(session["manifest_json"])
    assert manifest["preflight"]["status"] == "ready"
    assert manifest["preflight"]["services"]["mlflow_service"]["status"] == "ready"
    assert fake_orchestrator.run_called is True
    await manager.shutdown()


@pytest.mark.asyncio
async def test_session_start_preflight_failure_skips_llm_call(monkeypatch, tmp_path):
    _configure_preflight(monkeypatch, tmp_path)

    import server.core.session_manager as session_manager_module

    class FakeOrchestrator:
        def __init__(self, store) -> None:
            self.run_called = False

        async def run(self, config) -> None:
            self.run_called = True

        def request_stop(self, research_id: str) -> None:
            pass

        def request_pause(self, research_id: str) -> None:
            pass

        def request_resume(self, research_id: str) -> None:
            pass

    failed_preflight = {
        "schema_version": "autoresearch_service_preflight.v1",
        "status": "failed",
        "required_ready": True,
        "services": {
            "mlflow_service": {
                "url": "http://mlflow-service:8000",
                "required": True,
                "status": "failed",
                "status_code": 503,
                "error": "HTTP 503",
            }
        },
        "required_failures": ["mlflow_service"],
    }
    fake_orchestrator = FakeOrchestrator(None)

    async def unhealthy_preflight(*, model_type: str):
        return failed_preflight

    monkeypatch.setattr(
        session_manager_module,
        "AgentOrchestrator",
        lambda store: fake_orchestrator,
    )
    monkeypatch.setattr(
        session_manager_module,
        "run_service_preflight",
        unhealthy_preflight,
    )

    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    manager = session_manager_module.SessionManager(store)

    with pytest.raises(RuntimeError, match="Service preflight failed"):
        await manager.start_session(
            instrument="DOGE_USDT",
            timeframe="15m",
            model_type="direction",
        )

    assert fake_orchestrator.run_called is False
    assert await store.list_sessions() == []


def test_sanitize_service_url_removes_manifest_credentials():
    assert (
        sanitize_service_url("http://user:pass@mlflow-service:8000/health?token=raw")
        == "http://mlflow-service:8000/health"
    )
