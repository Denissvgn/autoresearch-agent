# main Module

**Path:** `src/main.py`

## Description

Autoresearch Agent — FastAPI application entry point.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `asyncio` | `asyncio` |
| `contextlib` | `asynccontextmanager` |
| `fastapi` | `Depends`, `FastAPI`, `HTTPException`, `Request`, `WebSocket`, `WebSocketDisconnect` |
| `fastapi.middleware.cors` | `CORSMiddleware` |
| `fastapi.responses` | `FileResponse`, `Response` |
| `fastapi.staticfiles` | `StaticFiles` |
| `libs.config.ml_service_logging` | `setup_ml_service_logging` |
| `libs.observability` | `ensure_app_platform_headers`, `initialize_telemetry_from_env`, `shutdown_telemetry` |
| `logging` | `logging` |
| `os` | `os` |
| `secrets` | `secrets` |
| `src.api` | `promotion`, `research`, `results` |
| `src.api.auth` | `require_api_auth`, `require_websocket_auth` |
| `src.api.promotion` | `router` |
| `src.api.research` | `router` |
| `src.api.results` | `router` |
| `src.config` | `get_vault_status`, `secret_value`, `settings` |
| `src.core.config_promoter` | `ConfigPromoter` |
| `src.core.observability` | `PROMETHEUS_CONTENT_TYPE`, `empty_observability_snapshot`, `format_prometheus` |
| `src.core.results_store` | `ResultsStore` |
| `src.core.service_preflight` | `build_not_run_preflight`, `run_service_preflight` |
| `src.core.session_manager` | `SessionManager` |
| `src.ws.events` | `broadcaster` |
| `typing` | `Any`, `AsyncIterator` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_validate_runtime_configuration` | `() -> None` | — | Fail fast for settings that would break this service's invariants. |
| `lifespan` | `*(async)* (app: FastAPI) -> AsyncIterator[None]` | `@asynccontextmanager` | Startup and shutdown logic. |
| `_normalise_api_prefix` | `(prefix: str) -> str` | — | — |
| `_include_api_routers` | `(prefix: str) -> None` | — | — |
| `health` | `*(async)* () -> dict[str, Any]` | `@app.get('/health')` | — |
| `info` | `*(async)* (request: Request) -> dict[str, Any]` | `@app.get('/info')` | — |
| `readiness` | `*(async)* () -> dict[str, Any]` | `@app.get('/health/ready')` | — |
| `monitoring_health` | `*(async)* () -> dict[str, Any]` | `@app.get('/monitoring/health')` | — |
| `_collect_observability_snapshot` | `*(async)* () -> dict[str, Any]` | — | — |
| `metrics` | `*(async)* (request: Request) -> Response` | `@app.get('/metrics', include_in_schema=False)` | — |
| `observability_alerts` | `*(async)* () -> dict[str, Any]` | `@app.get(JoinedStr(values=[FormattedValue(value=Name(id='_API_V1_PREFIX', ctx=Load()), conversion=-1), Constant(value='/observability/alerts')]), dependencies=[Call(func=Name(id='Depends', ctx=Load()), args=[Name(id='require_api_auth', ctx=Load())], keywords=[])])`, `@app.get('/api/observability/alerts', include_in_schema=False, dependencies=[Call(func=Name(id='Depends', ctx=Load()), args=[Name(id='require_api_auth', ctx=Load())], keywords=[])])` | — |
| `api_v1_not_found` | `*(async)* (full_path: str) -> None` | `@app.api_route(JoinedStr(values=[FormattedValue(value=Name(id='_API_V1_PREFIX', ctx=Load()), conversion=-1), Constant(value='/{full_path:path}')]), methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'], include_in_schema=False)` | — |
| `websocket_events` | `*(async)* (websocket: WebSocket) -> None` | `@app.websocket('/ws/events')` | — |
| `spa_fallback` | `*(async)* (full_path: str) -> FileResponse` | `@app.get('/{full_path:path}')` | — |
