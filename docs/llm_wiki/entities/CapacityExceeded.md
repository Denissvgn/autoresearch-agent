# CapacityExceeded

**Location:** `src/core/state_store.py:988`
**Kind:** Class
**Bases:** `RuntimeError`
**Module:** [state_store](../modules/state_store.md)

## Description

Raised when admitting work would exceed the configured global limit.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["CapacityExceeded (src/core/state_store.py)"]
    n1["RuntimeError"]
    n2["PostgresStateStore.reserve_work (src/core/postgres_state_store.py)"]
    n3["src/core/session_manager.py"]
    n4["SQLiteStateStore.reserve_work (src/core/state_store.py)"]
    n5["tests/test_store_transaction_serialization.py"]
    n6["tests/test_work_reservations.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    click n0 "../modules/state_store.md"
    click n2 "../modules/postgres_state_store.md"
    click n3 "../modules/session_manager.md"
    click n4 "../modules/state_store.md"
    click n5 "../modules/test_store_transaction_serialization.md"
    click n6 "../modules/test_work_reservations.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [state_store](../modules/state_store.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `RuntimeError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `PostgresStateStore.reserve_work` | call | [postgres_state_store](../modules/postgres_state_store.md) | 1 |
| `session_manager` | import | [session_manager](../modules/session_manager.md) | — |
| `SQLiteStateStore.reserve_work` | call | [state_store](../modules/state_store.md) | 1 |
| `test_store_transaction_serialization` | import | [test_store_transaction_serialization](../modules/test_store_transaction_serialization.md) | — |
| `test_work_reservations` | import | [test_work_reservations](../modules/test_work_reservations.md) | — |
