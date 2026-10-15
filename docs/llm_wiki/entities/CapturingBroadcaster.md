# _CapturingBroadcaster

**Location:** `tests/test_state_machine.py:39`
**Kind:** Class
**Bases:** `EventBroadcaster`
**Module:** [test_state_machine](../modules/test_state_machine.md)

## Description

An ``EventBroadcaster`` that records broadcasts instead of sending them.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `() -> None` | — | — |
| `broadcast` | *(async)* `(event: Dict[str, Any]) -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["_CapturingBroadcaster (tests/test_state_machine.py)"]
    n1["EventBroadcaster (src/ws/events.py)"]
    n2["test_complete_broadcast_merges_domain_fields (tests/test_state_machine.py)"]
    n3["test_complete_writes_completing_then_completed (tests/test_state_machine.py)"]
    n4["test_completing_outranked_by_more_severe (tests/test_state_machine.py)"]
    n5["test_completing_plus_stop_redirects_to_stopping_no_autopromote (tests/test_state_machine.py)"]
    n6["test_concurrent_complete_and_stop_never_corrupts (tests/test_state_machine.py)"]
    n7["test_fail_persists_status_fields_on_terminal_write (tests/test_state_machine.py)"]
    n8["test_illegal_transition_raises_and_writes_nothing (tests/test_state_machine.py)"]
    n9["test_invalid_recovery_target_raises (tests/test_state_machine.py)"]
    n10["test_legal_transition (tests/test_state_machine.py)"]
    n11["test_lock_evicted_on_terminal (tests/test_state_machine.py)"]
    n12["test_missing_session_raises_lookup_error (tests/test_state_machine.py)"]
    n13["test_noop_transition_writes_nothing (tests/test_state_machine.py)"]
    n0 --> n1
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
    click n0 "../modules/test_state_machine.md"
    click n1 "../modules/events.md"
    click n2 "../modules/test_state_machine.md"
    click n3 "../modules/test_state_machine.md"
    click n4 "../modules/test_state_machine.md"
    click n5 "../modules/test_state_machine.md"
    click n6 "../modules/test_state_machine.md"
    click n7 "../modules/test_state_machine.md"
    click n8 "../modules/test_state_machine.md"
    click n9 "../modules/test_state_machine.md"
    click n10 "../modules/test_state_machine.md"
    click n11 "../modules/test_state_machine.md"
    click n12 "../modules/test_state_machine.md"
    click n13 "../modules/test_state_machine.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_state_machine](../modules/test_state_machine.md) | 2 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `EventBroadcaster` | [events](../modules/events.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `test_complete_broadcast_merges_domain_fields` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `test_complete_writes_completing_then_completed` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `test_completing_outranked_by_more_severe` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `test_completing_plus_stop_redirects_to_stopping_no_autopromote` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `test_concurrent_complete_and_stop_never_corrupts` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `test_fail_persists_status_fields_on_terminal_write` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `test_illegal_transition_raises_and_writes_nothing` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `test_invalid_recovery_target_raises` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `test_legal_transition` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `test_lock_evicted_on_terminal` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `test_missing_session_raises_lookup_error` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `test_noop_transition_writes_nothing` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |

> References: showing 12 of 15 logical references; 3 omitted by the 12-row generated summary limit.
