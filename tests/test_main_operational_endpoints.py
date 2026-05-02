from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src import main as main_module
from src.core.observability import empty_observability_snapshot


class FakeSessionManager:
    active_count = 3


class FakeStore:
    async def collect_observability_metrics(self, *, active_sessions: int) -> dict[str, Any]:
        return empty_observability_snapshot(active_sessions=active_sessions)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(main_module, "_session_manager", FakeSessionManager())
    monkeypatch.setattr(main_module, "_store", FakeStore())
    monkeypatch.setattr(main_module.settings, "autoresearch_prometheus_token", None)
    monkeypatch.setattr(main_module.settings, "preflight_enabled", False)
    return TestClient(main_module.app)


def test_metrics_exports_prometheus_client_runtime_and_custom_metrics(
    client: TestClient,
) -> None:
    response = client.get("/metrics")

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
