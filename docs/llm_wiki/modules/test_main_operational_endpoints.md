# test_main_operational_endpoints Module

**Path:** `tests/test_main_operational_endpoints.py`

## Description

_Auto-generated from `tests/test_main_operational_endpoints.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `fastapi.testclient` | `TestClient` |
| `libs.observability` | `bind_platform_headers` |
| `pytest` | `pytest` |
| `src` | `main` |
| `src.core.observability` | `empty_observability_snapshot` |
| `typing` | `Any` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [FakeSessionManager](../entities/test_main_operational_endpoints_FakeSessionManager.md) | 13 | — | — |
| [FakeStore](../entities/test_main_operational_endpoints_FakeStore.md) | 17 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `client` | `(monkeypatch: pytest.MonkeyPatch) -> TestClient` | `@pytest.fixture` | — |
| `test_metrics_returns_404_when_scrape_token_unset` | `(client: TestClient) -> None` | — | — |
| `test_metrics_exports_prometheus_client_runtime_and_custom_metrics` | `(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None` | — | — |
| `test_metrics_scrape_token_gate` | `(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None` | — | — |
| `test_monitoring_health_reports_preflight_details` | `(client: TestClient) -> None` | — | — |
| `test_info_reports_service_metadata` | `(client: TestClient) -> None` | — | — |
| `test_unknown_api_v1_path_returns_404` | `(client: TestClient) -> None` | — | — |
| `test_app_has_platform_header_dependency` | `() -> None` | — | — |
| `test_runtime_config_requires_metrics_token_in_production` | `(monkeypatch: pytest.MonkeyPatch) -> None` | — | — |
| `test_runtime_config_rejects_multiple_workers` | `(monkeypatch: pytest.MonkeyPatch) -> None` | — | — |
| `test_readiness_reports_internal_state` | `(client: TestClient) -> None` | — | — |
