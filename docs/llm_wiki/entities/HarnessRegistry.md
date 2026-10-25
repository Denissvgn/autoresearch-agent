# HarnessRegistry

**Location:** `src/core/harness_adapter.py:63`
**Kind:** Class
**Bases:** —
**Module:** [harness_adapter](../modules/harness_adapter.md)

## Description

Name → adapter. Registering requires no kernel branch for the name.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `() -> None` | — | — |
| `register` | `(adapter: HarnessAdapter) -> None` | — | — |
| `resolve` | `(name: str) -> HarnessAdapter` | — | — |
| `names` | `() -> tuple[str, ...]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["HarnessRegistry (src/core/harness_adapter.py)"]
    n1["build_default_registry (src/api/harnesses.py)"]
    n2["init (src/api/harnesses.py)"]
    n3["run_conformance (src/core/harness_conformance.py)"]
    n4["_negative_version_mismatch (src/core/harness_qualification.py)"]
    n5["test_builtin_adapter_is_selected_explicitly_from_the_registry (tests/test_builtin_harness.py)"]
    n6["test_registering_a_new_adapter_needs_no_kernel_branch (tests/test_harness_sdk.py)"]
    n7["test_version_mismatch_is_refused_at_registration (tests/test_harness_sdk.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    click n0 "../modules/harness_adapter.md"
    click n1 "../modules/harnesses.md"
    click n2 "../modules/harnesses.md"
    click n3 "../modules/harness_conformance.md"
    click n4 "../modules/harness_qualification.md"
    click n5 "../modules/test_builtin_harness.md"
    click n6 "../modules/test_harness_sdk.md"
    click n7 "../modules/test_harness_sdk.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [harness_adapter](../modules/harness_adapter.md) | 4 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `build_default_registry` | call | [harnesses](../modules/harnesses.md) | 1 |
| `build_default_registry` | type_reference | [harnesses](../modules/harnesses.md) | — |
| `init` | type_reference | [harnesses](../modules/harnesses.md) | — |
| `run_conformance` | call | [harness_conformance](../modules/harness_conformance.md) | 1 |
| `_negative_version_mismatch` | call | [harness_qualification](../modules/harness_qualification.md) | 1 |
| `test_builtin_adapter_is_selected_explicitly_from_the_registry` | call | [test_builtin_harness](../modules/test_builtin_harness.md) | 1 |
| `test_registering_a_new_adapter_needs_no_kernel_branch` | call | [test_harness_sdk](../modules/test_harness_sdk.md) | 1 |
| `test_version_mismatch_is_refused_at_registration` | call | [test_harness_sdk](../modules/test_harness_sdk.md) | 1 |
