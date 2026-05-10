# events Module

**Path:** `src/ws/events.py`

## Description

WebSocket broadcast manager for real-time experiment events.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `asyncio` | `asyncio` |
| `fastapi` | `WebSocket` |
| `json` | `json` |
| `logging` | `logging` |
| `typing` | `Any`, `Dict`, `Set` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [EventBroadcaster](../entities/EventBroadcaster.md) | 15 | — | Manages WebSocket client connections and broadcasts events. |
