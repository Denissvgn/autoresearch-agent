# IsolationError

**Location:** `src/core/isolation.py:53`
**Kind:** Class
**Bases:** `RuntimeError`
**Module:** [isolation](../modules/isolation.md)

## Description

Base class for isolation boundary failures (always fail-closed).

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["IsolationError (src/core/isolation.py)"]
    n1["RuntimeError"]
    n2["IsolationUnavailableError (src/core/isolation.py)"]
    n3["UnsupportedCapabilityError (src/core/isolation.py)"]
    n4["src/core/command_runner.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/isolation.md"
    click n2 "../modules/isolation.md"
    click n3 "../modules/isolation.md"
    click n4 "../modules/command_runner.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [isolation](../modules/isolation.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `RuntimeError` | — |
| Subclass | `IsolationUnavailableError` | [isolation](../modules/isolation.md) |
| Subclass | `UnsupportedCapabilityError` | [isolation](../modules/isolation.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `command_runner` | import | [command_runner](../modules/command_runner.md) | — |
