# StaleFenceError

**Location:** `src/core/state_store.py:996`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [state_store](../modules/state_store.md)

## Description

Raised when a write carries a fence epoch older than the current one.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["StaleFenceError (src/core/state_store.py)"]
    n1["ValueError"]
    n2["PostgresStateStore.require_session_fence (src/core/postgres_state_store.py)"]
    n3["SQLiteStateStore.require_session_fence (src/core/state_store.py)"]
    n4["tests/test_durable_operation_qualification.py"]
    n5["tests/test_work_reservations.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/state_store.md"
    click n2 "../modules/postgres_state_store.md"
    click n3 "../modules/state_store.md"
    click n4 "../modules/test_durable_operation_qualification.md"
    click n5 "../modules/test_work_reservations.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [state_store](../modules/state_store.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `PostgresStateStore.require_session_fence` | call | [postgres_state_store](../modules/postgres_state_store.md) | 1 |
| `SQLiteStateStore.require_session_fence` | call | [state_store](../modules/state_store.md) | 1 |
| `test_durable_operation_qualification` | import | [test_durable_operation_qualification](../modules/test_durable_operation_qualification.md) | — |
| `test_work_reservations` | import | [test_work_reservations](../modules/test_work_reservations.md) | — |
