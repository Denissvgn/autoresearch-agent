"""Autoresearch Agent — FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from libs.observability import (
    ensure_app_platform_headers,
    initialize_telemetry_from_env,
    shutdown_telemetry,
)

from src.api.auth import require_api_auth, require_websocket_auth
from src.config import get_vault_status, secret_value, settings
from src.core.config_promoter import ConfigPromoter
from src.core.observability import (
    PROMETHEUS_CONTENT_TYPE,
    empty_observability_snapshot,
    format_prometheus,
)
from src.core.results_store import ResultsStore
from src.core.service_preflight import build_not_run_preflight, run_service_preflight
from src.core.session_manager import SessionManager
from src.ws.events import broadcaster

try:
    from libs.config.ml_service_logging import setup_ml_service_logging

    _ml_logger = setup_ml_service_logging(
        service_name=settings.service_name,
        level=settings.log_level,
        json_logs=settings.environment == "production",
        mask_secrets=True,
    )
    logger = _ml_logger.logger
except Exception:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
    )
    logger = logging.getLogger(settings.service_name)
    _ml_logger = None

# Global instances (initialized in lifespan)
_store: ResultsStore | None = None
_session_manager: SessionManager | None = None
_promoter: ConfigPromoter | None = None


def _validate_runtime_configuration() -> None:
    """Fail fast for settings that would break this service's invariants."""

    env = settings.environment.lower()
    if env in {"prod", "production"} and not secret_value(settings.autoresearch_prometheus_token):
        raise RuntimeError("AUTORESEARCH_PROMETHEUS_TOKEN is required in production")
    for name in ("WEB_CONCURRENCY", "UVICORN_WORKERS", "AUTORESEARCH_REPLICAS"):
        raw = os.getenv(name)
        if not raw:
            continue
        try:
            value = int(raw)
        except ValueError:
            logger.warning(
                "Cannot parse %s=%r as an integer — single-instance guard "
                "skipped. Ensure only one worker is running.",
                name, raw,
            )
            continue
        if value > 1:
            raise RuntimeError(
                "autoresearch-agent is a single-instance SQLite control-plane "
                f"service; {name}={value} is not supported"
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown logic."""
    global _store, _session_manager, _promoter

    logger.info("Starting autoresearch-agent service")
    _validate_runtime_configuration()
    initialize_telemetry_from_env(settings.service_name)
    if _ml_logger:
        vault_status = get_vault_status()
        _ml_logger.log_service_startup(settings, vault_status)
        _ml_logger.log_config_loaded(settings, vault_status.get("vault_config_keys", 0))
    logger.info("Model: %s", settings.anthropic_model)
    logger.info("Default quick mode: %s", settings.default_quick_mode)
    logger.info("Max iterations: %d", settings.max_iterations)
    logger.info("Max budget: $%.2f", settings.max_budget_usd)
    logger.info("Workspace: %s", settings.workspace_root)

    # Initialize SQLite store
    _store = ResultsStore(settings.db_path)
    await _store.initialize()
    app.state.audit_store = _store

    # Initialize session manager and promoter
    _session_manager = SessionManager(_store)
    orphan_summary = await _session_manager.recover_orphaned_sessions()
    if orphan_summary.get("resumable") or orphan_summary.get("interrupted"):
        logger.warning("Runtime recovery summary: %s", orphan_summary)
    _promoter = ConfigPromoter(_store)

    # Wire API modules
    from src.api import promotion, research, results

    research.init(_session_manager, _store)  # type: ignore[no-untyped-call]
    results.init(_store, mlflow_external_url=settings.mlflow_external_url)
    promotion.init(_promoter, _store)  # type: ignore[no-untyped-call]

    logger.info("Autoresearch-agent ready")

    yield

    # Shutdown
    logger.info("Shutting down autoresearch-agent...")
    if _session_manager:
        await _session_manager.shutdown()
    if _store:
        await _store.close()
    shutdown_telemetry()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Autoresearch Agent",
    description="Autonomous ML model tuning via Claude agent sessions",
    version="0.1.0",
    lifespan=lifespan,
)
ensure_app_platform_headers(app)

# CORS — Phase 1.4 hardening: when origins is the wildcard, force
# allow_credentials=False because Starlette will silently produce a
# response that browsers reject anyway, and combining `*` with
# credentials=True is unsafe with our shared bearer token.
_cors_origins = settings.cors_origins
_cors_allow_credentials = True
if _cors_origins == ["*"]:
    logger.warning(
        "CORS origins is '*'; disabling allow_credentials to comply with "
        "browser policy. Set AUTORESEARCH_CORS_ORIGINS to an explicit list "
        "to keep credentialed requests working.",
    )
    _cors_allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
from src.api.promotion import router as promotion_router
from src.api.research import router as research_router
from src.api.results import router as results_router


def _normalise_api_prefix(prefix: str) -> str:
    cleaned = (prefix or "").strip().strip("/")
    return f"/{cleaned}" if cleaned else "/api/v1"


_API_V1_PREFIX = _normalise_api_prefix(settings.api_v1_prefix)


def _include_api_routers(prefix: str, *, include_in_schema: bool = True) -> None:
    app.include_router(research_router, prefix=prefix, include_in_schema=include_in_schema)
    app.include_router(results_router, prefix=prefix, include_in_schema=include_in_schema)
    app.include_router(promotion_router, prefix=prefix, include_in_schema=include_in_schema)


_include_api_routers(_API_V1_PREFIX)
_include_api_routers("/api", include_in_schema=False)


# ------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "active_sessions": _session_manager.active_count if _session_manager else 0,
    }


@app.get("/info")
async def info(request: Request) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    return {
        "service": settings.service_name,
        "version": app.version,
        "docs_url": "/docs",
        "health_url": "/health",
        "websocket_path": "/ws/events",
        "api_prefix": _API_V1_PREFIX,
        "legacy_api_prefix": "/api",
        "api_base_url": f"{base_url}{_API_V1_PREFIX}",
    }


@app.get("/health/ready")
async def readiness() -> dict[str, Any]:
    active_sessions = _session_manager.active_count if _session_manager else 0
    internal_checks = {
        "store_initialized": _store is not None,
        "session_manager_initialized": _session_manager is not None,
        "db_ready": False,
    }
    if _store is not None:
        internal_checks["db_ready"] = await _store.ping()
    dependencies_ready = True
    if settings.preflight_enabled:
        try:
            preflight = await run_service_preflight(model_type="all")
        except Exception as exc:
            preflight = {
                "schema_version": "autoresearch_service_preflight.v1",
                "status": "failed",
                "required_ready": False,
                "required_failures": ["preflight"],
                "error": str(exc),
            }
        dependencies_ready = bool(
            preflight.get("required_ready") or settings.allow_unready_services,
        )
    else:
        preflight = build_not_run_preflight()

    ready = all(internal_checks.values()) and dependencies_ready
    status_text = "ready" if ready else "not_ready"
    if _ml_logger:
        _ml_logger.log_health_check(
            status_text,
            {**internal_checks, "active_sessions": active_sessions},
        )

    return {
        "ready": ready,
        "status": status_text,
        "service": settings.service_name,
        "active_sessions": active_sessions,
        "checks": internal_checks,
        "dependencies": preflight,
    }


@app.get("/monitoring/health")
async def monitoring_health() -> dict[str, Any]:
    active_sessions = _session_manager.active_count if _session_manager else 0
    if settings.preflight_enabled:
        try:
            preflight = await run_service_preflight(model_type="all")
        except Exception as exc:
            preflight = {
                "schema_version": "autoresearch_service_preflight.v1",
                "status": "failed",
                "required_ready": False,
                "required_failures": ["preflight"],
                "error": str(exc),
            }
    else:
        preflight = build_not_run_preflight()

    preflight_status = preflight.get("status")
    if preflight_status == "ready":
        status_text = "healthy"
    elif preflight_status in {"degraded", "skipped", "not_run"}:
        status_text = "degraded"
    else:
        status_text = "unhealthy"

    return {
        "status": status_text,
        "service": settings.service_name,
        "active_sessions": active_sessions,
        "dependencies": preflight,
    }


async def _collect_observability_snapshot() -> dict[str, Any]:
    active_sessions = _session_manager.active_count if _session_manager else 0
    if _store is None:
        return empty_observability_snapshot(active_sessions=active_sessions)
    return await _store.collect_observability_metrics(
        active_sessions=active_sessions,
    )


@app.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    # Phase 5.2: bearer-token gate for Prometheus scrapers. When
    # ``autoresearch_prometheus_token`` is unset the endpoint is intentionally
    # unavailable; when set we require it explicitly so the endpoint is safe to
    # expose outside the cluster boundary.
    expected = secret_value(settings.autoresearch_prometheus_token)
    if not expected:
        raise HTTPException(status_code=404, detail="metrics endpoint disabled")
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    provided = auth.split(" ", 1)[1].strip()
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid scrape token")
    snapshot = await _collect_observability_snapshot()
    return Response(
        content=format_prometheus(snapshot),
        media_type=PROMETHEUS_CONTENT_TYPE,
    )


@app.get(f"{_API_V1_PREFIX}/observability/alerts", dependencies=[Depends(require_api_auth)])
@app.get(
    "/api/observability/alerts",
    include_in_schema=False,
    dependencies=[Depends(require_api_auth)],
)
async def observability_alerts() -> dict[str, Any]:
    snapshot = await _collect_observability_snapshot()
    return {
        "schema_version": snapshot["schema_version"],
        "collected_at": snapshot["collected_at"],
        "alert_suggestions": snapshot["alert_suggestions"],
    }


@app.api_route(
    f"{_API_V1_PREFIX}/{{full_path:path}}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def api_v1_not_found(full_path: str) -> None:
    raise HTTPException(status_code=404, detail="API endpoint not found")


# ------------------------------------------------------------------
# WebSocket
# ------------------------------------------------------------------


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    actor = await require_websocket_auth(websocket)
    if actor is None:
        return

    connected = await broadcaster.connect(
        websocket,
        subprotocol=actor.websocket_subprotocol,
        max_clients=settings.ws_max_clients,
    )
    if not connected:
        return
    try:
        # Server-side ping loop keeps the TCP connection alive during long
        # training runs when no application-level events are being sent.
        heartbeat_failed = asyncio.Event()

        async def _heartbeat() -> None:
            try:
                while True:
                    await asyncio.sleep(15)
                    await websocket.send_json({"type": "ping"})
            except Exception as exc:
                logger.debug("WebSocket heartbeat failed: %s", exc)
                heartbeat_failed.set()

        heartbeat_task = asyncio.create_task(_heartbeat())
        # Phase 4.2: bound receive_text with a wall-clock timeout and drop
        # the connection if the peer goes silent for more than N consecutive
        # idle windows; this catches half-open TCP sockets the OS hasn't
        # detected yet (heartbeat send failures cover the other direction).
        idle_window_s = 60
        max_idle_windows = 5
        idle_count = 0
        try:
            while True:
                receive_task = asyncio.create_task(websocket.receive_text())
                heartbeat_task_wait = asyncio.create_task(heartbeat_failed.wait())
                done, pending = await asyncio.wait(
                    {receive_task, heartbeat_task_wait},
                    timeout=idle_window_s,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for pending_task in pending:
                    pending_task.cancel()
                if heartbeat_task_wait in done and heartbeat_failed.is_set():
                    logger.info("Closing WebSocket after heartbeat failure")
                    break
                if receive_task in done:
                    await receive_task
                    idle_count = 0
                    continue
                receive_task.cancel()
                heartbeat_task_wait.cancel()
                idle_count += 1
                if idle_count >= max_idle_windows:
                    logger.info(
                        "Closing idle WebSocket after %ds of silence",
                        idle_window_s * max_idle_windows,
                    )
                    break
        finally:
            heartbeat_task.cancel()
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
    except Exception:
        await broadcaster.disconnect(websocket)
    else:
        await broadcaster.disconnect(websocket)


# ------------------------------------------------------------------
# Static UI files (served at root, after API routes)
# ------------------------------------------------------------------

_ui_dist = os.path.join(os.path.dirname(__file__), "..", "ui", "dist")
if os.path.isdir(_ui_dist):
    # Serve static assets (JS, CSS, images) from the build output
    app.mount("/assets", StaticFiles(directory=os.path.join(_ui_dist, "assets")), name="ui-assets")

    # SPA catch-all: any non-API path returns index.html for client-side routing
    _index_html = os.path.join(_ui_dist, "index.html")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        # Serve actual files if they exist (favicon.ico, etc.)
        file_path = os.path.join(_ui_dist, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(_index_html)
