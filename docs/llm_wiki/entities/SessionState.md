# SessionState

**Location:** `src/core/state_machine.py:44`
**Kind:** Enum
**Bases:** `str`, `Enum`
**Module:** [state_machine](../modules/state_machine.md)

## Description

The 13 session lifecycle states (ARC-011 §3).

## Attributes

| Name | Declared value | Description |
|------|-------|-------------|
| `PENDING` | `'pending'` | — |
| `RUNNING` | `'running'` | — |
| `PAUSED` | `'paused'` | — |
| `STOPPING` | `'stopping'` | — |
| `COMPLETING` | `'completing'` | — |
| `TIMING_OUT` | `'timing_out'` | — |
| `FAILING` | `'failing'` | — |
| `STOPPED` | `'stopped'` | — |
| `COMPLETED` | `'completed'` | — |
| `TIMED_OUT` | `'timed_out'` | — |
| `FAILED` | `'failed'` | — |
| `RESUMABLE` | `'resumable'` | — |
| `INTERRUPTED` | `'interrupted'` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SessionState (src/core/state_machine.py)"]
    n1["Enum"]
    n2["str"]
    n3["AgentOrchestrator.__init__ (src/core/orchestrator.py)"]
    n4["SessionManager.__init__ (src/core/session_manager.py)"]
    n5["_resolve_severity (src/core/state_machine.py)"]
    n6["IllegalTransitionError.__init__ (src/core/state_machine.py)"]
    n7["SessionStateMachine._apply (src/core/state_machine.py)"]
    n8["SessionStateMachine._transition_locked (src/core/state_machine.py)"]
    n9["SessionStateMachine.transition (src/core/state_machine.py)"]
    n10["_status_of (tests/test_state_machine.py)"]
    n11["test_completing_outranked_by_more_severe (tests/test_state_machine.py)"]
    n12["test_illegal_transition_raises_and_writes_nothing (tests/test_state_machine.py)"]
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
    click n0 "../modules/state_machine.md"
    click n3 "../modules/orchestrator.md"
    click n4 "../modules/session_manager.md"
    click n5 "../modules/state_machine.md"
    click n6 "../modules/state_machine.md"
    click n7 "../modules/state_machine.md"
    click n8 "../modules/state_machine.md"
    click n9 "../modules/state_machine.md"
    click n10 "../modules/test_state_machine.md"
    click n11 "../modules/test_state_machine.md"
    click n12 "../modules/test_state_machine.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [state_machine](../modules/state_machine.md) | 0 | `COMPLETED`, `COMPLETING`, `FAILED`, `FAILING`, `INTERRUPTED`, `PAUSED`, `PENDING`, `RESUMABLE`, `RUNNING`, `STOPPED`, `STOPPING`, `TIMED_OUT` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Enum` | — |
| Base | `str` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `AgentOrchestrator.__init__` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `SessionManager.__init__` | type_reference | [session_manager](../modules/session_manager.md) | — |
| `_resolve_severity` | type_reference | [state_machine](../modules/state_machine.md) | — |
| `IllegalTransitionError.__init__` | type_reference | [state_machine](../modules/state_machine.md) | — |
| `SessionStateMachine._apply` | type_reference | [state_machine](../modules/state_machine.md) | — |
| `SessionStateMachine._transition_locked` | call | [state_machine](../modules/state_machine.md) | 1 |
| `SessionStateMachine._transition_locked` | type_reference | [state_machine](../modules/state_machine.md) | — |
| `SessionStateMachine.transition` | type_reference | [state_machine](../modules/state_machine.md) | — |
| `_status_of` | call | [test_state_machine](../modules/test_state_machine.md) | 1 |
| `_status_of` | type_reference | [test_state_machine](../modules/test_state_machine.md) | — |
| `test_completing_outranked_by_more_severe` | type_reference | [test_state_machine](../modules/test_state_machine.md) | — |
| `test_illegal_transition_raises_and_writes_nothing` | call | [test_state_machine](../modules/test_state_machine.md) | 2 |

> References: showing 12 of 16 logical references; 4 omitted by the 12-row generated summary limit.
