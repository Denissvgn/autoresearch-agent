# _YieldingFakeWS

**Location:** `tests/test_event_broadcaster_concurrency.py:27`
**Kind:** Class
**Bases:** —
**Module:** [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md)

## Description

A fake WebSocket that yields to the event loop inside ``send_text``.

The ``await asyncio.sleep(0)`` forces a genuine suspension point so
``asyncio.gather`` interleaves broadcast with connect/disconnect — the
real concurrency window the P0-013 snapshot-before-iterate hardening
protects against.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(*, fail: bool = False, name: str = 'ws') -> None` | — | — |
| `accept` | *(async)* `(*, subprotocol: str \| None = None) -> None` | — | — |
| `close` | *(async)* `(*, code: int = 1000) -> None` | — | — |
| `send_text` | *(async)* `(payload: str) -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["_YieldingFakeWS (tests/test_event_broadcaster_concurrency.py)"]
    n1["test_broadcast_storm_with_churn (tests/test_event_broadcaster_concurrency.py)"]
    n2["test_concurrent_broadcast_and_disconnect_never_raises (tests/test_event_broadcaster_concurrency.py)"]
    n3["test_connect_during_broadcast_is_safe (tests/test_event_broadcaster_concurrency.py)"]
    n4["test_dead_client_pruned_exactly (tests/test_event_broadcaster_concurrency.py)"]
    n5["test_slow_client_does_not_block_broadcast (tests/test_event_broadcaster_concurrency.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/test_event_broadcaster_concurrency.md"
    click n1 "../modules/test_event_broadcaster_concurrency.md"
    click n2 "../modules/test_event_broadcaster_concurrency.md"
    click n3 "../modules/test_event_broadcaster_concurrency.md"
    click n4 "../modules/test_event_broadcaster_concurrency.md"
    click n5 "../modules/test_event_broadcaster_concurrency.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md) | 4 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `test_broadcast_storm_with_churn` | call | [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md) | 1 |
| `test_concurrent_broadcast_and_disconnect_never_raises` | call | [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md) | 2 |
| `test_connect_during_broadcast_is_safe` | call | [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md) | 3 |
| `test_dead_client_pruned_exactly` | call | [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md) | 2 |
| `test_slow_client_does_not_block_broadcast` | call | [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md) | 1 |
