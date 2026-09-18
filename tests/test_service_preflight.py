from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path

import httpx
import pytest

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    class _FakeAsyncAnthropic:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class _FakeAPIStatusError(Exception):
        status_code = 500

    sys.modules["anthropic"] = types.SimpleNamespace(
        AsyncAnthropic=_FakeAsyncAnthropic,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=_FakeAPIStatusError,
    )

from src.config import settings
from src.core.results_store import ResultsStore
from src.core.service_preflight import (
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
    monkeypatch.setattr(settings, "mlflow_tracking_uri", "http://mlflow:5000")


def _sample_targets():
    from src.core.service_preflight import ServicePreflightTarget

    return [
        ServicePreflightTarget(
            "data_ingest", "http://data-ingest:8000",
            health_paths=("/readiness", "/health"),
        ),
        ServicePreflightTarget(
            "ensemble_trainer", "http://ensemble-trainer:8000",
            health_paths=("/health/ready", "/health"),
        ),
        ServicePreflightTarget("mlflow_service", "http://mlflow-service:8000"),
        ServicePreflightTarget(
            "artifact_store", "http://minio:9000",
            health_paths=("/minio/health/ready", "/health"),
        ),
    ]


def _healthy_transport() -> httpx.MockTransport:
    ready_paths = {
        ("mlflow", "/health"),
        ("mlflow-service", "/health"),
        ("data-ingest", "/readiness"),
        ("ensemble-trainer", "/health/ready"),
        ("rl-trainer", "/health/ready"),
        ("feature-service", "/health"),
        ("inference-service", "/api/v1/health"),
        ("admin-service", "/api/v1/health"),
        ("vdmc-indicator", "/api/v1/health/ready"),
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
        result = await run_service_preflight(
            targets=_sample_targets(), client=client,
        )

    assert result["schema_version"] == "autoresearch_service_preflight.v1"
    assert result["status"] == "ready"
    assert result["required_failures"] == []
    assert result["services"]["data_ingest"]["checked_url"].endswith("/readiness")
    assert result["services"]["ensemble_trainer"]["health_paths"] == [
        "/health/ready",
        "/health",
    ]
    assert result["services"]["ensemble_trainer"]["checked_url"].endswith("/health/ready")
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
        result = await run_service_preflight(
            targets=_sample_targets(), client=client,
        )

    assert result["status"] == "failed"
    assert result["required_failures"] == ["mlflow_service"]
    with pytest.raises(ServicePreflightError, match="mlflow_service"):
        require_preflight_ready(result)


@pytest.mark.asyncio
async def test_session_start_persists_preflight_in_manifest(monkeypatch, tmp_path):
    _configure_preflight(monkeypatch, tmp_path)

    import src.core.session_manager as session_manager_module

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

    async def healthy_preflight(*, targets=None):
        return {
            "schema_version": "autoresearch_service_preflight.v1",
            "status": "ready",
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
        lambda store, state_machine=None: fake_orchestrator,
    )
    monkeypatch.setattr(
        session_manager_module,
        "run_service_preflight",
        healthy_preflight,
    )

    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    manager = session_manager_module.SessionManager(store)

    # P7-011: the skill bootstrap runs at start — supply a real eval_set
    # (prompt-engineering fail-closes without one outside demo mode).
    eval_set = tmp_path / "eval_set.jsonl"
    eval_set.write_text(
        '{"input": "What is 2+2?", "expected": "4"}\n', encoding="utf-8",
    )
    session = await manager.start_session(
        # ARC-012 P7-010: starts must name an installed skill — the legacy
        # ``model_type``-only shape is refused before preflight now.
        instrument="default",
        timeframe="production",
        model_type="",
        skill_id="prompt-engineering",
        skill_params={"eval_set": str(eval_set)},
        subject_id="default",
        variant="production",
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

    import src.core.session_manager as session_manager_module

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

    async def unhealthy_preflight(*, targets=None):
        return failed_preflight

    monkeypatch.setattr(
        session_manager_module,
        "AgentOrchestrator",
        lambda store, state_machine=None: fake_orchestrator,
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
            # ARC-012 P7-010: installed skill — preflight is what fails here.
            instrument="default",
            timeframe="production",
            model_type="",
            skill_id="prompt-engineering",
            subject_id="default",
            variant="production",
        )

    assert fake_orchestrator.run_called is False
    assert await store.list_sessions() == []


def test_sanitize_service_url_removes_manifest_credentials():
    assert (
        sanitize_service_url("http://user:pass@mlflow-service:8000/health?token=raw")
        == "http://mlflow-service:8000/health"
    )
