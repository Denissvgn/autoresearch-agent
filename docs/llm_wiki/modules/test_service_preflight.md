# test_service_preflight Module

**Path:** `tests/test_service_preflight.py`

## Description

_Auto-generated from `tests/test_service_preflight.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `anthropic` | `anthropic` |
| `asyncio` | `asyncio` |
| `httpx` | `httpx` |
| `json` | `json` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.config` | `settings` |
| `src.core.results_store` | `ResultsStore` |
| `src.core.service_preflight` | `ServicePreflightError`, `require_preflight_ready`, `run_service_preflight`, `sanitize_service_url`, `preflight_module` |
| `src.core.session_manager` | `session_manager_module`, `session_manager_module` |
| `sys` | `sys` |
| `types` | `types` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [_FakeAsyncAnthropic](../entities/test_service_preflight__FakeAsyncAnthropic.md) | 15 | — | — |
| [_FakeAPIStatusError](../entities/test_service_preflight__FakeAPIStatusError.md) | 19 | `Exception` | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_configure_preflight` | `(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` | — | — |
| `_healthy_transport` | `() -> httpx.MockTransport` | — | — |
| `test_service_preflight_records_healthy_services` | `*(async)* (monkeypatch, tmp_path)` | `@pytest.mark.asyncio` | — |
| `test_service_preflight_blocks_unhealthy_required_service` | `*(async)* (monkeypatch, tmp_path)` | `@pytest.mark.asyncio` | — |
| `test_vdmc_preflight_required_for_rl_pipeline_and_all_only` | `*(async)* (monkeypatch, tmp_path)` | `@pytest.mark.asyncio` | — |
| `test_full_stack_preflight_requires_inference_admin_and_nats` | `*(async)* (monkeypatch, tmp_path)` | `@pytest.mark.asyncio` | — |
| `test_session_start_persists_preflight_in_manifest` | `*(async)* (monkeypatch, tmp_path)` | `@pytest.mark.asyncio` | — |
| `test_session_start_preflight_failure_skips_llm_call` | `*(async)* (monkeypatch, tmp_path)` | `@pytest.mark.asyncio` | — |
| `test_sanitize_service_url_removes_manifest_credentials` | `()` | — | — |
