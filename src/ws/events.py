"""WebSocket broadcast manager for real-time experiment events."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """Manages WebSocket client connections and broadcasts events.

    Phase 4.1: a single ``asyncio.Lock`` serializes mutations to the
    client set so concurrent connect/disconnect/broadcast cannot leave
    the set in an inconsistent state, and ``broadcast`` iterates a
    snapshot so client churn during a fan-out cannot raise
    ``RuntimeError: Set changed size during iteration``.
    """

    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, *, subprotocol: str | None = None) -> None:
        await websocket.accept(subprotocol=subprotocol)
        async with self._lock:
            self._clients.add(websocket)
            count = len(self._clients)
        logger.info("WebSocket client connected (total: %d)", count)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)
            count = len(self._clients)
        logger.info("WebSocket client disconnected (total: %d)", count)

    async def broadcast(self, event: Dict[str, Any]) -> None:
        """Send an event to all connected WebSocket clients."""
        async with self._lock:
            if not self._clients:
                return
            snapshot = list(self._clients)
        payload = json.dumps(event)
        dead: list[WebSocket] = []
        for ws in snapshot:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)


# Global singleton
broadcaster = EventBroadcaster()
