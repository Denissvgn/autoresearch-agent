# HarnessVersionError

**Location:** `src/core/harness_contract.py:78`
**Kind:** Class
**Bases:** `HarnessContractError`
**Module:** [harness_contract](../modules/harness_contract.md)

## Description

The adapter's contract version is incompatible with this SDK.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["HarnessVersionError (src/core/harness_contract.py)"]
    n1["HarnessContractError (src/core/harness_contract.py)"]
    n2["HarnessRegistry.register (src/core/harness_adapter.py)"]
    n3["src/core/harness_conformance.py"]
    n4["src/core/harness_qualification.py"]
    n5["tests/test_harness_sdk.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/harness_contract.md"
    click n1 "../modules/harness_contract.md"
    click n2 "../modules/harness_adapter.md"
    click n3 "../modules/harness_conformance.md"
    click n4 "../modules/harness_qualification.md"
    click n5 "../modules/test_harness_sdk.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [harness_contract](../modules/harness_contract.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `HarnessContractError` | [harness_contract](../modules/harness_contract.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `HarnessRegistry.register` | call | [harness_adapter](../modules/harness_adapter.md) | 1 |
| `harness_conformance` | import | [harness_conformance](../modules/harness_conformance.md) | — |
| `harness_qualification` | import | [harness_qualification](../modules/harness_qualification.md) | — |
| `test_harness_sdk` | import | [test_harness_sdk](../modules/test_harness_sdk.md) | — |
