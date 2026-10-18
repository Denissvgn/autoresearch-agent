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


# ---------------------------------------------------------------------------
# Transactional outbox delivery: cross-worker fan-out, replay, ingestion rules
# ---------------------------------------------------------------------------

SECRET_KEY_MARKERS = (
    "token",
    "secret",
    "password",
    "api_key",
    "authorization",
    "credential",
)

REDACTED_PLACEHOLDER = "[redacted]"


def redact_event_payload(payload: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    """Strip secret-looking values from an event payload.

    Redaction happens before publication, not at display time: an event
    that never carries a secret cannot leak one through a replayed stream.
    Returns the clean payload and whether anything was redacted.
    """
    redacted = False

    def _clean(value: Any, key: str = "") -> Any:
        nonlocal redacted
        lowered = key.lower()
        if any(marker in lowered for marker in SECRET_KEY_MARKERS):
            if value not in (None, "", REDACTED_PLACEHOLDER):
                redacted = True
            return REDACTED_PLACEHOLDER if value not in (None, "") else value
        if isinstance(value, dict):
            return {k: _clean(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [_clean(item, key) for item in value]
        return value

    cleaned = {k: _clean(v, k) for k, v in dict(payload).items()}
    return cleaned, redacted


def plan_catchup(*, cursor: int, min_sequence: int) -> Dict[str, Any]:
    """Decide replay versus resync for a reconnecting client.

    A cursor inside the retained stream replays from there. A cursor whose
    successor is no longer retained (``cursor + 1 < min_sequence``) has
    expired: the missed events cannot be reconstructed from the outbox and
    the client must resynchronize from an atomic snapshot-plus-cursor.
    """
    if cursor > 0 and cursor + 1 < int(min_sequence):
        return {
            "mode": "resync",
            "reason": "cursor_expired",
            "cursor": int(cursor),
            "min_sequence": int(min_sequence),
        }
    return {"mode": "replay", "after_sequence": int(cursor)}


def dedupe_events(
    events: list[Dict[str, Any]], applied_ids: Set[str]
) -> tuple[list[Dict[str, Any]], Set[str]]:
    """Duplicate/out-of-order ingestion rule: apply each event at most once.

    Events are ordered by their sequence before delivery; an event whose id
    was already applied is dropped, so a replayed or duplicated delivery
    cannot apply a side effect twice. The caller persists ``applied_ids``
    (or derives it from applied state) to keep the guarantee across restarts.
    """
    fresh: list[Dict[str, Any]] = []
    updated = set(applied_ids)
    for event in sorted(events, key=lambda item: int(item.get("sequence") or 0)):
        event_id = str(event.get("event_id") or "")
        if not event_id or event_id in updated:
            continue
        updated.add(event_id)
        fresh.append(event)
    return fresh, updated


async def poll_events(
    store: Any,
    *,
    cursor: int = 0,
    stream_key: str | None = None,
    limit: int = 200,
) -> list[Dict[str, Any]]:
    """Bounded outbox read — the slow-consumer/backpressure primitive."""
    return await store.list_events(
        stream_key=stream_key, after_sequence=int(cursor), limit=int(limit),
    )


async def snapshot_with_cursor(
    store: Any, research_id: str
) -> Dict[str, Any]:
    """Atomic snapshot-plus-cursor resynchronization payload.

    The cursor is read before the snapshot: any event up to it may already
    be reflected in the snapshot, and the duplicate/out-of-order ingestion
    rule makes that over-supply harmless. Under no ordering does the pair
    miss an event.
    """
    cursor = await store.event_cursor(stream_key=research_id)
    snapshot = await store.get_session(research_id)
    return {
        "snapshot": snapshot,
        "cursor": cursor,
        "mode": "snapshot_plus_cursor",
    }


async def relay_new_events(
    store: Any,
    *,
    cursor: int,
    stream_key: str | None = None,
    limit: int = 200,
    on_event: Any = None,
) -> tuple[int, int]:
    """One bounded relay tick: deliver new events and advance the cursor.

    Cross-worker fan-out is this relay against the shared outbox: a client
    connected to any worker observes events produced on any other worker,
    because the durable record — not the local broadcaster — is the source
    of truth. Returns ``(delivered, new_cursor)``.
    """
    events = await poll_events(
        store, cursor=cursor, stream_key=stream_key, limit=limit,
    )
    delivered = 0
    for event in events:
        if on_event is not None:
            result = on_event(event)
            if asyncio.iscoroutine(result):
                await result
        else:
            delivery, _redacted = redact_event_payload(
                dict(event.get("payload") or {})
            )
            await broadcaster.broadcast(
                {
                    "event": event.get("event_type"),
                    "research_id": event.get("stream_key"),
                    "sequence": event.get("sequence"),
                    "event_id": event.get("event_id"),
                    **delivery,
                }
            )
        delivered += 1
    new_cursor = (
        int(events[-1].get("sequence") or 0) if events else int(cursor)
    )
    return delivered, new_cursor


