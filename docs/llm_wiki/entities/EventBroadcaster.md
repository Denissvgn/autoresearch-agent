# EventBroadcaster

**Location:** `src/ws/events.py:68`
**Kind:** Class
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
| `connect` | *(async)* `(websocket: WebSocket, *, subprotocol: str \| None = None, max_clients: int \| None = None) -> bool` | — | — |
| `disconnect` | *(async)* `(websocket: WebSocket) -> None` | — | — |
| `broadcast` | *(async)* `(event: Dict[str, Any]) -> None` | — | Send an event to all connected WebSocket clients. |
| `client_count` | `() -> int` | `@property` | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["EventBroadcaster (src/ws/events.py)"]
    n1["_CapturingBroadcaster (tests/test_state_machine.py)"]
    n2["SessionStateMachine.__init__ (src/core/state_machine.py)"]
    n3["tests/test_distributed_state_store.py"]
    n4["test_broadcast_storm_with_churn (tests/test_event_broadcaster_concurrency.py)"]
    n5["test_concurrent_broadcast_and_disconnect_never_raises (tests/test_event_broadcaster_concurrency.py)"]
    n6["test_connect_during_broadcast_is_safe (tests/test_event_broadcaster_concurrency.py)"]
    n7["test_dead_client_pruned_exactly (tests/test_event_broadcaster_concurrency.py)"]
    n8["test_slow_client_does_not_block_broadcast (tests/test_event_broadcaster_concurrency.py)"]
    n9["test_cross_worker_stop_observed_by_owner (tests/test_fencing_tokens.py)"]
    n10["test_integrated_fence_stale_worker_discards_result (tests/test_fencing_tokens.py)"]
    n11["test_transition_bumps_epoch (tests/test_fencing_tokens.py)"]
    n12["test_broadcaster_drops_dead_clients_under_concurrent_churn (tests/test_hardening_phase1_to_5.py)"]
    n13["test_broadcaster_rejects_clients_over_cap (tests/test_hardening_phase1_to_5.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    n10 --> n0
    n11 --> n0
    n12 --> n0
    n13 --> n0
    click n0 "../modules/events.md"
    click n1 "../modules/test_state_machine.md"
    click n2 "../modules/state_machine.md"
    click n3 "../modules/test_distributed_state_store.md"
    click n4 "../modules/test_event_broadcaster_concurrency.md"
    click n5 "../modules/test_event_broadcaster_concurrency.md"
    click n6 "../modules/test_event_broadcaster_concurrency.md"
    click n7 "../modules/test_event_broadcaster_concurrency.md"
    click n8 "../modules/test_event_broadcaster_concurrency.md"
    click n9 "../modules/test_fencing_tokens.md"
    click n10 "../modules/test_fencing_tokens.md"
    click n11 "../modules/test_fencing_tokens.md"
    click n12 "../modules/test_hardening_phase1_to_5.md"
    click n13 "../modules/test_hardening_phase1_to_5.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [events](../modules/events.md) | 5 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Subclass | `_CapturingBroadcaster` | [test_state_machine](../modules/test_state_machine.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `SessionStateMachine.__init__` | type_reference | [state_machine](../modules/state_machine.md) | — |
| `test_distributed_state_store` | import | [test_distributed_state_store](../modules/test_distributed_state_store.md) | — |
| `test_broadcast_storm_with_churn` | call | [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md) | 1 |
| `test_concurrent_broadcast_and_disconnect_never_raises` | call | [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md) | 1 |
| `test_connect_during_broadcast_is_safe` | call | [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md) | 1 |
| `test_dead_client_pruned_exactly` | call | [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md) | 1 |
| `test_slow_client_does_not_block_broadcast` | call | [test_event_broadcaster_concurrency](../modules/test_event_broadcaster_concurrency.md) | 1 |
| `test_cross_worker_stop_observed_by_owner` | call | [test_fencing_tokens](../modules/test_fencing_tokens.md) | 1 |
| `test_integrated_fence_stale_worker_discards_result` | call | [test_fencing_tokens](../modules/test_fencing_tokens.md) | 1 |
| `test_transition_bumps_epoch` | call | [test_fencing_tokens](../modules/test_fencing_tokens.md) | 1 |
| `test_broadcaster_drops_dead_clients_under_concurrent_churn` | call | [test_hardening_phase1_to_5](../modules/test_hardening_phase1_to_5.md) | 1 |
| `test_broadcaster_rejects_clients_over_cap` | call | [test_hardening_phase1_to_5](../modules/test_hardening_phase1_to_5.md) | 1 |

> References: showing 12 of 13 logical references; 1 omitted by the 12-row generated summary limit.
