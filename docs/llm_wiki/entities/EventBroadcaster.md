# EventBroadcaster

**Location:** `src/ws/events.py:15`
**Bases:** —
**Module:** [events](../modules/events.md)

## Description

Manages WebSocket client connections and broadcasts events.

Phase 4.1: a single ``asyncio.Lock`` serializes mutations to the
client set so concurrent connect/disconnect/broadcast cannot leave
the set in an inconsistent state, and ``broadcast`` iterates a
snapshot so client churn during a fan-out cannot raise
``RuntimeError: Set changed size during iteration``.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `() -> None` | — | — |
| `connect` | `*(async)* (websocket: WebSocket) -> bool` | — | — |
| `disconnect` | `*(async)* (websocket: WebSocket) -> None` | — | — |
| `broadcast` | `*(async)* (event: Dict[str, Any]) -> None` | — | Send an event to all connected WebSocket clients. |
| `client_count` | `() -> int` | `@property` | — |

## Relationships

- **imported_by**: [test_hardening_phase1_to_5](../modules/test_hardening_phase1_to_5.md)
