# SessionEvent

**Location:** `src/core/state_machine.py:68`
**Kind:** Enum
**Bases:** `str`, `Enum`
**Module:** [state_machine](../modules/state_machine.md)

## Description

Events that drive session state transitions (ARC-011 §4.1).

## Attributes

| Name | Declared value | Description |
|------|-------|-------------|
| `START` | `'start'` | — |
| `PAUSE` | `'pause'` | — |
| `RESUME` | `'resume'` | — |
| `STOP_REQUESTED` | `'stop_requested'` | — |
| `FINALIZE_STOP` | `'finalize_stop'` | — |
| `COMPLETE` | `'complete'` | — |
| `TIMEOUT` | `'timeout'` | — |
| `HARD_TIMEOUT` | `'hard_timeout'` | — |
| `FAIL` | `'fail'` | — |
| `RESTART_RECOVER` | `'restart_recover'` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SessionEvent (src/core/state_machine.py)"]
    n1["Enum"]
    n2["str"]
    n3["src/core/orchestrator.py"]
    n4["src/core/session_manager.py"]
    n5["_resolve_severity (src/core/state_machine.py)"]
    n6["IllegalTransitionError.__init__ (src/core/state_machine.py)"]
    n7["SessionStateMachine._apply (src/core/state_machine.py)"]
    n8["SessionStateMachine._transition_locked (src/core/state_machine.py)"]
    n9["SessionStateMachine.transition (src/core/state_machine.py)"]
    n10["tests/test_cross_worker_control.py"]
    n11["tests/test_event_outbox.py"]
    n12["tests/test_session_failure_modes.py"]
    n13["tests/test_session_status_routing.py"]
    n0 --> n1
    n0 --> n2
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
    click n0 "../modules/state_machine.md"
    click n3 "../modules/orchestrator.md"
    click n4 "../modules/session_manager.md"
    click n5 "../modules/state_machine.md"
    click n6 "../modules/state_machine.md"
    click n7 "../modules/state_machine.md"
    click n8 "../modules/state_machine.md"
    click n9 "../modules/state_machine.md"
    click n10 "../modules/test_cross_worker_control.md"
    click n11 "../modules/test_event_outbox.md"
    click n12 "../modules/test_session_failure_modes.md"
    click n13 "../modules/test_session_status_routing.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [state_machine](../modules/state_machine.md) | 0 | `COMPLETE`, `FAIL`, `FINALIZE_STOP`, `HARD_TIMEOUT`, `PAUSE`, `RESTART_RECOVER`, `RESUME`, `START`, `STOP_REQUESTED`, `TIMEOUT` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Enum` | — |
| Base | `str` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `orchestrator` | import | [orchestrator](../modules/orchestrator.md) | — |
| `session_manager` | import | [session_manager](../modules/session_manager.md) | — |
| `_resolve_severity` | type_reference | [state_machine](../modules/state_machine.md) | — |
| `IllegalTransitionError.__init__` | type_reference | [state_machine](../modules/state_machine.md) | — |
| `SessionStateMachine._apply` | type_reference | [state_machine](../modules/state_machine.md) | — |
| `SessionStateMachine._transition_locked` | type_reference | [state_machine](../modules/state_machine.md) | — |
| `SessionStateMachine.transition` | call | [state_machine](../modules/state_machine.md) | 1 |
| `SessionStateMachine.transition` | type_reference | [state_machine](../modules/state_machine.md) | — |
| `test_cross_worker_control` | import | [test_cross_worker_control](../modules/test_cross_worker_control.md) | — |
| `test_event_outbox` | import | [test_event_outbox](../modules/test_event_outbox.md) | — |
| `test_session_failure_modes` | import | [test_session_failure_modes](../modules/test_session_failure_modes.md) | — |
| `test_session_status_routing` | import | [test_session_status_routing](../modules/test_session_status_routing.md) | — |

> References: showing 12 of 17 logical references; 5 omitted by the 12-row generated summary limit.
