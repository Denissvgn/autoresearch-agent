"""Autoresearch Agent — FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from server.api.auth import require_api_auth, require_websocket_auth
from server.config import settings
from server.core.config_promoter import ConfigPromoter
from server.core.observability import (
    PROMETHEUS_CONTENT_TYPE,
    empty_observability_snapshot,
    format_prometheus,
)
from server.core.results_store import ResultsStore
from server.core.session_manager import SessionManager
from server.ws.events import broadcaster

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Global instances (initialized in lifespan)
_store: ResultsStore | None = None
_session_manager: SessionManager | None = None
_promoter: ConfigPromoter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    global _store, _session_manager, _promoter

    logger.info("Starting autoresearch-agent service")
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
    from server.api import promotion, research, results

    research.init(_session_manager, _store)
    results.init(_store, mlflow_external_url=settings.mlflow_external_url)
    promotion.init(_promoter, _store)

    logger.info("Autoresearch-agent ready")

    yield

    # Shutdown
    logger.info("Shutting down autoresearch-agent...")
    if _session_manager:
        await _session_manager.shutdown()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Autoresearch Agent",
    description="Autonomous ML model tuning via Claude agent sessions",
    version="0.1.0",
    lifespan=lifespan,
)

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
from server.api.promotion import router as promotion_router
from server.api.research import router as research_router
from server.api.results import router as results_router

app.include_router(research_router)
app.include_router(results_router)
app.include_router(promotion_router)


# ------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "active_sessions": _session_manager.active_count if _session_manager else 0,
    }


async def _collect_observability_snapshot():
    active_sessions = _session_manager.active_count if _session_manager else 0
    if _store is None:
        return empty_observability_snapshot(active_sessions=active_sessions)
    return await _store.collect_observability_metrics(
        active_sessions=active_sessions,
    )


@app.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    # Phase 5.2: optional bearer-token gate for Prometheus scrapers. When
    # ``autoresearch_prometheus_token`` is unset we keep the previous
    # unauthenticated behavior (typical in-cluster scrape via NetworkPolicy);
    # when set we require it explicitly so the endpoint is safe to expose
    # outside the cluster boundary.
    expected = settings.autoresearch_prometheus_token
    if expected:
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


@app.get("/api/observability/alerts", dependencies=[Depends(require_api_auth)])
async def observability_alerts():
    snapshot = await _collect_observability_snapshot()
    return {
        "schema_version": snapshot["schema_version"],
        "collected_at": snapshot["collected_at"],
        "alert_suggestions": snapshot["alert_suggestions"],
    }


# ------------------------------------------------------------------
# WebSocket
# ------------------------------------------------------------------


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    actor = await require_websocket_auth(websocket)
    if actor is None:
        return

    await broadcaster.connect(websocket, subprotocol=actor.websocket_subprotocol)
    try:
        # Server-side ping loop keeps the TCP connection alive during long
        # training runs when no application-level events are being sent.
        async def _heartbeat():
            try:
                while True:
                    await asyncio.sleep(15)
                    await websocket.send_json({"type": "ping"})
            except Exception:
                pass  # connection closed — let the outer handler clean up

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
                try:
                    await asyncio.wait_for(
                        websocket.receive_text(), timeout=idle_window_s,
                    )
                    idle_count = 0
                except asyncio.TimeoutError:
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
    async def spa_fallback(full_path: str):
        # Serve actual files if they exist (favicon.ico, etc.)
        file_path = os.path.join(_ui_dist, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(_index_html)
