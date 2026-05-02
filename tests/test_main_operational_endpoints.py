from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from libs.observability import bind_platform_headers

from src import main as main_module
from src.core.observability import empty_observability_snapshot


class FakeSessionManager:
    active_count = 3


class FakeStore:
    async def ping(self) -> bool:
        return True

    async def collect_observability_metrics(self, *, active_sessions: int) -> dict[str, Any]:
        return empty_observability_snapshot(active_sessions=active_sessions)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(main_module, "_session_manager", FakeSessionManager())
    monkeypatch.setattr(main_module, "_store", FakeStore())
    monkeypatch.setattr(main_module.settings, "autoresearch_prometheus_token", None)
    monkeypatch.setattr(main_module.settings, "preflight_enabled", False)
    return TestClient(main_module.app)


def test_metrics_returns_404_when_scrape_token_unset(
    client: TestClient,
) -> None:
    response = client.get("/metrics")

    assert response.status_code == 404


def test_metrics_exports_prometheus_client_runtime_and_custom_metrics(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module.settings, "autoresearch_prometheus_token", "scrape-token")

    response = client.get(
        "/metrics",
        headers={"Authorization": "Bearer scrape-token"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "python_info" in response.text
    assert "process_cpu_seconds_total" in response.text
    assert "autoresearch_active_sessions 3" in response.text


def test_metrics_scrape_token_gate(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module.settings, "autoresearch_prometheus_token", "scrape-token")

    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401

    response = client.get(
        "/metrics",
        headers={"Authorization": "Bearer scrape-token"},
    )
    assert response.status_code == 200
    assert "autoresearch_active_sessions 3" in response.text


def test_monitoring_health_reports_preflight_details(client: TestClient) -> None:
    response = client.get("/monitoring/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["service"] == main_module.settings.service_name
    assert payload["active_sessions"] == 3
    assert payload["dependencies"]["status"] == "not_run"


def test_app_has_platform_header_dependency() -> None:
    dependencies = main_module.app.router.dependencies
    assert any(
        getattr(dependency, "dependency", None) is bind_platform_headers
        for dependency in dependencies
    )


def test_runtime_config_requires_metrics_token_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module.settings, "environment", "production")
    monkeypatch.setattr(main_module.settings, "autoresearch_prometheus_token", None)

    with pytest.raises(RuntimeError, match="PROMETHEUS_TOKEN"):
        main_module._validate_runtime_configuration()


def test_runtime_config_rejects_multiple_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module.settings, "environment", "development")
    monkeypatch.setenv("WEB_CONCURRENCY", "2")

    with pytest.raises(RuntimeError, match="single-instance"):
        main_module._validate_runtime_configuration()


def test_readiness_reports_internal_state(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["status"] == "ready"
    assert payload["service"] == main_module.settings.service_name
    assert payload["active_sessions"] == 3
    assert payload["checks"]["store_initialized"] is True
    assert payload["checks"]["session_manager_initialized"] is True
    assert payload["checks"]["db_ready"] is True
    assert payload["dependencies"]["status"] == "not_run"
