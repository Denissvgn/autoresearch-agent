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
| `src.core.preflight` | `preflight_check_from_target` |
| `time` | `time` |
| `typing` | `Any` |
| `urllib.parse` | `urlsplit`, `urlunsplit` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/config.py"]
    n1["src/core/preflight.py"]
    n2["src/core/research_manifest.py"]
    n3["src/core/service_preflight.py"]
    n4["src/core/session_manager.py"]
    n5["src/main.py"]
    n6["tests/test_preflight.py"]
    n7["tests/test_service_preflight.py"]
    n1 --> n3
    n2 --> n0
    n2 --> n3
    n3 --> n0
    n3 --> n1
    n4 --> n0
    n4 --> n2
    n4 --> n3
    n5 --> n0
    n5 --> n3
    n5 --> n4
    n6 --> n1
    n6 --> n3
    n7 --> n0
    n7 --> n3
    n7 --> n4
    click n0 "../modules/config.md"
    click n1 "../modules/preflight.md"
    click n2 "../modules/research_manifest.md"
    click n3 "../modules/service_preflight.md"
    click n4 "../modules/session_manager.md"
    click n5 "../modules/src_main.md"
    click n6 "../modules/test_preflight.md"
    click n7 "../modules/test_service_preflight.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [preflight](../modules/preflight.md) |
| Inbound | [research_manifest](../modules/research_manifest.md) |
| Inbound | [session_manager](../modules/session_manager.md) |
| Inbound | [src_main](../modules/src_main.md) |
| Inbound | [test_preflight](../modules/test_preflight.md) |
| Inbound | [test_service_preflight](../modules/test_service_preflight.md) |
| Outbound | [config](../modules/config.md) |
| Outbound | [preflight](../modules/preflight.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 0 |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ServicePreflightTarget](../entities/ServicePreflightTarget.md) | 20 | — | — |
| [ServicePreflightError](../entities/ServicePreflightError.md) | 28 | `RuntimeError` | Raised when required service dependencies are not ready. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `sanitize_service_url` | `(raw: str \| None) -> str` | — | Return a URL safe for manifests by removing credentials and query data. |
| `build_not_run_preflight` | `(settings_obj = settings, *, targets: 'list[ServicePreflightTarget] \| tuple[()]' = (), model_type: str = '') -> dict[str, Any]` | — | Build a manifest-safe dependency snapshot when checks have not run. |
| `run_service_preflight` | *(async)* `(*, targets: 'list[ServicePreflightTarget]', settings_obj = settings, client: httpx.AsyncClient \| None = None) -> dict[str, Any]` | — | Check the declared service dependencies before launching a session. |
| `require_preflight_ready` | `(result: dict[str, Any]) -> None` | — | Raise when a preflight result should block session creation. |
| `format_preflight_error` | `(result: dict[str, Any]) -> str` | — | — |
| `_check_target` | *(async)* `(client: httpx.AsyncClient, target: ServicePreflightTarget) -> dict[str, Any]` | — | — |
| `_check_tcp_target` | *(async)* `(target: ServicePreflightTarget, timeout_s: float) -> dict[str, Any]` | — | — |
| `_join_health_path` | `(base_url: str, path: str) -> str` | — | — |
