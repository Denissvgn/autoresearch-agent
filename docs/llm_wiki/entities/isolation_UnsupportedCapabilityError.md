# UnsupportedCapabilityError

**Location:** `src/core/isolation.py:61`
**Kind:** Class
**Bases:** `IsolationError`
**Module:** [isolation](../modules/isolation.md)

## Description

A capability request the selected backend cannot enforce.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["UnsupportedCapabilityError (src/core/isolation.py)"]
    n1["IsolationError (src/core/isolation.py)"]
    n2["BwrapBackend.wrap (src/core/isolation.py)"]
    n3["src/core/plugin_runner.py"]
    n4["tests/test_execution_isolation.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/isolation.md"
    click n1 "../modules/isolation.md"
    click n2 "../modules/isolation.md"
    click n3 "../modules/plugin_runner.md"
    click n4 "../modules/test_execution_isolation.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [isolation](../modules/isolation.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `IsolationError` | [isolation](../modules/isolation.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `BwrapBackend.wrap` | call | [isolation](../modules/isolation.md) | 1 |
| `plugin_runner` | import | [plugin_runner](../modules/plugin_runner.md) | — |
| `test_execution_isolation` | import | [test_execution_isolation](../modules/test_execution_isolation.md) | — |
