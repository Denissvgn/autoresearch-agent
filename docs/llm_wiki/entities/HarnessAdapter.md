# HarnessAdapter

**Location:** `src/core/harness_adapter.py:31`
**Kind:** Class
**Bases:** `Protocol`
**Module:** [harness_adapter](../modules/harness_adapter.md)

**Decorators:** `@runtime_checkable`

## Description

The minimal, versioned harness surface.

Required operations: identity, capabilities, start/attach, the event
stream, cancel, and close. Optional operations (pause, resume, steer)
exist only for adapters that advertise the matching capability.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `identity` | `() -> HarnessIdentity` | — | — |
| `capabilities` | `() -> frozenset[str]` | — | — |
| `start` | `(request: Mapping[str, Any]) -> Mapping[str, Any]` | — | Begin a run; returns ``{"handle": <id>, ...}``. |
| `attach` | `(request: Mapping[str, Any]) -> Mapping[str, Any]` | — | Rejoin a run under an explicit attach mode. |
| `events` | `(handle: str) -> Iterator[Mapping[str, Any]]` | — | — |
| `cancel` | `(handle: str) -> None` | — | — |
| `close` | `(handle: str) -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["HarnessAdapter (src/core/harness_adapter.py)"]
    n1["Protocol"]
    n2["HarnessRegistry.register (src/core/harness_adapter.py)"]
    n3["HarnessRegistry.resolve (src/core/harness_adapter.py)"]
    n4["request_pause (src/core/harness_adapter.py)"]
    n5["request_resume (src/core/harness_adapter.py)"]
    n6["request_steer (src/core/harness_adapter.py)"]
    n7["resolve_harness_spec (src/core/harness_adapter.py)"]
    n8["validate_requirements (src/core/harness_adapter.py)"]
    n9["run_conformance (src/core/harness_conformance.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    click n0 "../modules/harness_adapter.md"
    click n2 "../modules/harness_adapter.md"
    click n3 "../modules/harness_adapter.md"
    click n4 "../modules/harness_adapter.md"
    click n5 "../modules/harness_adapter.md"
    click n6 "../modules/harness_adapter.md"
    click n7 "../modules/harness_adapter.md"
    click n8 "../modules/harness_adapter.md"
    click n9 "../modules/harness_conformance.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [harness_adapter](../modules/harness_adapter.md) | 7 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Protocol` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `HarnessRegistry.register` | type_reference | [harness_adapter](../modules/harness_adapter.md) | — |
| `HarnessRegistry.resolve` | type_reference | [harness_adapter](../modules/harness_adapter.md) | — |
| `request_pause` | type_reference | [harness_adapter](../modules/harness_adapter.md) | — |
| `request_resume` | type_reference | [harness_adapter](../modules/harness_adapter.md) | — |
| `request_steer` | type_reference | [harness_adapter](../modules/harness_adapter.md) | — |
| `resolve_harness_spec` | type_reference | [harness_adapter](../modules/harness_adapter.md) | — |
| `validate_requirements` | type_reference | [harness_adapter](../modules/harness_adapter.md) | — |
| `run_conformance` | type_reference | [harness_conformance](../modules/harness_conformance.md) | — |
