# _EventReader

**Location:** `src/core/driver_host.py:88`
**Kind:** Class
**Bases:** `threading.Thread`
**Module:** [driver_host](../modules/driver_host.md)

## Description

Bounded stdout reader: normalizes JSONL, enforces size and queue
bounds, and records protocol violations instead of trusting them.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(stream: Any, config: DriverHostConfig, on_event: Any) -> None` | — | — |
| `run` | `() -> None` | — | — |
| `_handle_line` | `(line: bytes) -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["_EventReader (src/core/driver_host.py)"]
    n1["threading.Thread"]
    n2["DriverHost.start (src/core/driver_host.py)"]
    n0 --> n1
    n2 --> n0
    click n0 "../modules/driver_host.md"
    click n2 "../modules/driver_host.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [driver_host](../modules/driver_host.md) | 3 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `threading.Thread` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `DriverHost.start` | call | [driver_host](../modules/driver_host.md) | 1 |
