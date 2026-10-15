# IllegalTransitionError

**Location:** `src/core/state_machine.py:124`
**Kind:** Class
**Bases:** `RuntimeError`
**Module:** [state_machine](../modules/state_machine.md)

## Description

Raised when an event is not legal from the session's current state.

Carries the ``(from_state, event)`` pair so callers can react — most
importantly the orchestrator exit path, which catches a ``complete``
refused by a racing stop and skips auto-promotion (ARC-011 §5 / §8).

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(from_state: SessionState, event: SessionEvent) -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["IllegalTransitionError (src/core/state_machine.py)"]
    n1["RuntimeError"]
    n2["src/core/orchestrator.py"]
    n3["src/core/session_manager.py"]
    n4["SessionStateMachine._transition_locked (src/core/state_machine.py)"]
    n5["tests/test_cross_worker_control.py"]
    n6["tests/test_session_status_routing.py"]
    n7["tests/test_state_machine.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    click n0 "../modules/state_machine.md"
    click n2 "../modules/orchestrator.md"
    click n3 "../modules/session_manager.md"
    click n4 "../modules/state_machine.md"
    click n5 "../modules/test_cross_worker_control.md"
    click n6 "../modules/test_session_status_routing.md"
    click n7 "../modules/test_state_machine.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [state_machine](../modules/state_machine.md) | 1 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `RuntimeError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `orchestrator` | import | [orchestrator](../modules/orchestrator.md) | — |
| `session_manager` | import | [session_manager](../modules/session_manager.md) | — |
| `SessionStateMachine._transition_locked` | call | [state_machine](../modules/state_machine.md) | 2 |
| `test_cross_worker_control` | import | [test_cross_worker_control](../modules/test_cross_worker_control.md) | — |
| `test_session_status_routing` | import | [test_session_status_routing](../modules/test_session_status_routing.md) | — |
| `test_state_machine` | import | [test_state_machine](../modules/test_state_machine.md) | — |
