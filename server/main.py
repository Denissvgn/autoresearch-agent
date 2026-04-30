"""Autoresearch Agent — FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
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
async def metrics():
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
        try:
            while True:
                await websocket.receive_text()
        finally:
            heartbeat_task.cancel()
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
    except Exception:
        broadcaster.disconnect(websocket)


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
