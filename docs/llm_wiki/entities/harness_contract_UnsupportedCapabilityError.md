# UnsupportedCapabilityError

**Location:** `src/core/harness_contract.py:82`
**Kind:** Class
**Bases:** `HarnessContractError`
**Module:** [harness_contract](../modules/harness_contract.md)

## Description

An optional capability was requested but is not advertised.

Refusal is explicit: the SDK never substitutes a different operation
(a kill is not a pause) and never silently no-ops.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(capability: str, adapter_name: str) -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["UnsupportedCapabilityError (src/core/harness_contract.py)"]
    n1["HarnessContractError (src/core/harness_contract.py)"]
    n2["request_pause (src/core/harness_adapter.py)"]
    n3["request_resume (src/core/harness_adapter.py)"]
    n4["request_steer (src/core/harness_adapter.py)"]
    n5["src/core/harness_conformance.py"]
    n6["src/core/harness_qualification.py"]
    n7["tests/test_claude_code_harness.py"]
    n8["tests/test_codex_harness.py"]
    n9["tests/test_harness_sdk.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    click n0 "../modules/harness_contract.md"
    click n1 "../modules/harness_contract.md"
    click n2 "../modules/harness_adapter.md"
    click n3 "../modules/harness_adapter.md"
    click n4 "../modules/harness_adapter.md"
    click n5 "../modules/harness_conformance.md"
    click n6 "../modules/harness_qualification.md"
    click n7 "../modules/test_claude_code_harness.md"
    click n8 "../modules/test_codex_harness.md"
    click n9 "../modules/test_harness_sdk.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [harness_contract](../modules/harness_contract.md) | 1 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `HarnessContractError` | [harness_contract](../modules/harness_contract.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `request_pause` | call | [harness_adapter](../modules/harness_adapter.md) | 1 |
| `request_resume` | call | [harness_adapter](../modules/harness_adapter.md) | 1 |
| `request_steer` | call | [harness_adapter](../modules/harness_adapter.md) | 1 |
| `harness_conformance` | import | [harness_conformance](../modules/harness_conformance.md) | — |
| `harness_qualification` | import | [harness_qualification](../modules/harness_qualification.md) | — |
| `test_claude_code_harness` | import | [test_claude_code_harness](../modules/test_claude_code_harness.md) | — |
| `test_codex_harness` | import | [test_codex_harness](../modules/test_codex_harness.md) | — |
| `test_harness_sdk` | import | [test_harness_sdk](../modules/test_harness_sdk.md) | — |
