"""Autoresearch Agent — FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.config import settings
from server.core.config_promoter import ConfigPromoter
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

    # Initialize session manager and promoter
    _session_manager = SessionManager(_store)
    _promoter = ConfigPromoter(_store)

    # Wire API modules
    from server.api import promotion, research, results

    research.init(_session_manager, _store)
    results.init(_store)
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


# ------------------------------------------------------------------
# WebSocket
# ------------------------------------------------------------------


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await broadcaster.connect(websocket)
    try:
        while True:
            # Keep connection alive; client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
    except Exception:
        broadcaster.disconnect(websocket)


# ------------------------------------------------------------------
# Static UI files (served at root, after API routes)
# ------------------------------------------------------------------

_ui_dist = os.path.join(os.path.dirname(__file__), "..", "ui", "dist")
if os.path.isdir(_ui_dist):
    app.mount("/", StaticFiles(directory=_ui_dist, html=True), name="ui")
