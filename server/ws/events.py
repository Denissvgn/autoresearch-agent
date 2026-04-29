"""WebSocket broadcast manager for real-time experiment events."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """Manages WebSocket client connections and broadcasts events."""

    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, *, subprotocol: str | None = None) -> None:
        await websocket.accept(subprotocol=subprotocol)
        self._clients.add(websocket)
        logger.info(
            "WebSocket client connected (total: %d)", len(self._clients),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)
        logger.info(
            "WebSocket client disconnected (total: %d)", len(self._clients),
        )

    async def broadcast(self, event: Dict[str, Any]) -> None:
        """Send an event to all connected WebSocket clients."""
        if not self._clients:
            return
        payload = json.dumps(event)
        dead: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)


# Global singleton
broadcaster = EventBroadcaster()
