# service_preflight Module

**Path:** `src/core/service_preflight.py`

## Description

Service dependency preflight checks for autoresearch sessions.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `asyncio` | `asyncio` |
| `dataclasses` | `dataclass` |
| `datetime` | `datetime`, `timezone` |
| `httpx` | `httpx` |
| `src.config` | `settings` |
| `time` | `time` |
| `typing` | `Any` |
| `urllib.parse` | `urlsplit`, `urlunsplit` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ServicePreflightTarget](../entities/ServicePreflightTarget.md) | 20 | — | — |
| [ServicePreflightError](../entities/ServicePreflightError.md) | 28 | `RuntimeError` | Raised when required service dependencies are not ready. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_normalise_model_type` | `(model_type: str | None) -> str` | — | — |
| `_vdmc_required_for` | `(model_type: str | None) -> bool` | — | — |
| `_full_stack_required_for` | `(model_type: str | None) -> bool` | — | — |
| `sanitize_service_url` | `(raw: str | None) -> str` | — | Return a URL safe for manifests by removing credentials and query data. |
| `build_service_preflight_targets` | `(settings_obj = settings) -> list[ServicePreflightTarget]` | — | Build the service dependency list from current server settings. |
| `build_not_run_preflight` | `(settings_obj = settings) -> dict[str, Any]` | — | Build a manifest-safe dependency snapshot when checks have not run. |
| `run_service_preflight` | `*(async)* () -> dict[str, Any]` | — | Check required ML dependencies before launching a research session. |
| `require_preflight_ready` | `(result: dict[str, Any]) -> None` | — | Raise when a preflight result should block session creation. |
| `format_preflight_error` | `(result: dict[str, Any]) -> str` | — | — |
| `_check_target` | `*(async)* (client: httpx.AsyncClient, target: ServicePreflightTarget) -> dict[str, Any]` | — | — |
| `_check_tcp_target` | `*(async)* (target: ServicePreflightTarget, timeout_s: float) -> dict[str, Any]` | — | — |
| `_join_health_path` | `(base_url: str, path: str) -> str` | — | — |
