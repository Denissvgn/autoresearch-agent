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
| `src.core.legacy_alias` | `model_type_to_skill_id` |
| `typing` | `Any`, `Dict`, `Set` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src"]
    n1["src/ws/events.py"]
    n2["tests"]
    n0 --> n1
    n1 --> n0
    n2 --> n1
    click n1 "../modules/events.md"
```

> Module-level dependencies exceed the generated-diagram limits, so the diagram and table below group them by top-level package. Counts report the number of module neighbors in each package.

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | `src` (6) |
| Inbound | `tests` (9) |
| Outbound | `src` (1) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

> All 16 module neighbor(s) are summarized by package because the module-level view exceeds the 12-node limit.

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [EventBroadcaster](../entities/EventBroadcaster.md) | 68 | — | Manages WebSocket client connections and broadcasts events. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_enrich_event` | `(event: Any) -> Any` | — | P3-018: enrich a WebSocket event payload with canonical skill fields. |
| `redact_event_payload` | `(payload: Dict[str, Any]) -> tuple[Dict[str, Any], bool]` | — | Strip secret-looking values from an event payload. |
| `plan_catchup` | `(*, cursor: int, min_sequence: int) -> Dict[str, Any]` | — | Decide replay versus resync for a reconnecting client. |
| `dedupe_events` | `(events: list[Dict[str, Any]], applied_ids: Set[str]) -> tuple[list[Dict[str, Any]], Set[str]]` | — | Duplicate/out-of-order ingestion rule: apply each event at most once. |
| `poll_events` | *(async)* `(store: Any, *, cursor: int = 0, stream_key: str \| None = None, limit: int = 200) -> list[Dict[str, Any]]` | — | Bounded outbox read — the slow-consumer/backpressure primitive. |
| `snapshot_with_cursor` | *(async)* `(store: Any, research_id: str) -> Dict[str, Any]` | — | Atomic snapshot-plus-cursor resynchronization payload. |
| `relay_new_events` | *(async)* `(store: Any, *, cursor: int, stream_key: str \| None = None, limit: int = 200, on_event: Any = None) -> tuple[int, int]` | — | One bounded relay tick: deliver new events and advance the cursor. |
