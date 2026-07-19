"""WebSocket broadcast manager for real-time experiment events."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Set

from fastapi import WebSocket

from src.core.legacy_alias import model_type_to_skill_id

logger = logging.getLogger(__name__)

#: P0-013: per-send timeout (seconds). A stuck/half-open WebSocket is pruned
#: after this interval so a single slow client cannot stall the fan-out.
#: Monkeypatched to a small value in tests.
_BROADCAST_SEND_TIMEOUT_S: float = 5.0


def _enrich_event(event: Any) -> Any:
    """P3-018: enrich a WebSocket event payload with canonical skill fields.

    Additive only (§10 #5: event names unchanged; payloads only gain fields).
    Adds:

    * ``skill_id``     ← ``model_type`` via the alias registry.
    * ``skill_phase``  ← ``search_phase`` (legacy column name).
    * ``evidence_keys``← keys of ``phase_evidence`` (when it is a dict).
    * ``metrics``      ← a compact summary of the primary metric fields.

    Non-dict events pass through unchanged. Existing fields are never
    overwritten — enrichment is strictly additive.
    """
    if not isinstance(event, dict):
        return event
    enriched = dict(event)

    # skill_id — derived from model_type via the alias registry.
    model_type = enriched.get("model_type")
    if model_type and not enriched.get("skill_id"):
        enriched["skill_id"] = model_type_to_skill_id(model_type)

    # skill_phase — derived from the legacy search_phase field.
    if not enriched.get("skill_phase"):
        search_phase = enriched.get("search_phase")
        if search_phase:
            enriched["skill_phase"] = search_phase

    # evidence_keys — derived from the phase_evidence dict's keys.
    if "evidence_keys" not in enriched:
        phase_evidence = enriched.get("phase_evidence")
        if isinstance(phase_evidence, dict):
            enriched["evidence_keys"] = list(phase_evidence.keys())

    # metrics — a compact summary so WS clients don't need a follow-up fetch.
    if "metrics" not in enriched:
        metric_fields = ("primary_metric", "metric_name", "all_gates_passed",
                         "training_gates_passed")
        summary = {k: enriched[k] for k in metric_fields if k in enriched}
        if summary:
            enriched["metrics"] = summary

    return enriched


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

    async def connect(
        self,
        websocket: WebSocket,
        *,
        subprotocol: str | None = None,
        max_clients: int | None = None,
    ) -> bool:
        async with self._lock:
            if max_clients is not None and len(self._clients) >= max_clients:
                logger.warning(
                    "Rejecting WebSocket client: max clients reached (%d)",
                    max_clients,
                )
                await websocket.close(code=1013)
                return False
            await websocket.accept(subprotocol=subprotocol)
            self._clients.add(websocket)
            count = len(self._clients)
        logger.info("WebSocket client connected (total: %d)", count)
        return True

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)
            count = len(self._clients)
        logger.info("WebSocket client disconnected (total: %d)", count)

    async def broadcast(self, event: Dict[str, Any]) -> None:
        """Send an event to all connected WebSocket clients.

        P3-018: events are enriched with canonical ``skill_id`` (derived from
        ``model_type``), ``skill_phase``, ``evidence_keys``, and a ``metrics``
        summary — strictly additive (§10 #5)."""
        event = _enrich_event(event)
        async with self._lock:
            if not self._clients:
                return
            snapshot = list(self._clients)
        payload = json.dumps(event)
        dead: list[WebSocket] = []
        for ws in snapshot:
            try:
                await asyncio.wait_for(
                    ws.send_text(payload), timeout=_BROADCAST_SEND_TIMEOUT_S
                )
            except Exception as exc:
                logger.debug("WebSocket send failed: %s", exc)
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
