# HarnessIdentity

**Location:** `src/core/harness_contract.py:32`
**Kind:** Class
**Bases:** `TypedDict`
**Module:** [harness_contract](../modules/harness_contract.md)

## Description

Who the adapter is and what it is allowed to do.

## Attributes

| Name | Type | Presence | Description |
|------|------|----------|-------------|
| `name` | `str` | *required* | — |
| `version` | `str` | *required* | — |
| `contract_version` | `str` | *required* | — |
| `permissions` | `Mapping[str, Any]` | *required* | — |
| `interface` | `NotRequired[str]` | *optional* | — |
| `schema_pin` | `NotRequired[str]` | *optional* | — |
| `attach_modes` | `NotRequired[list[str]]` | *optional* | — |
| `resume_mode` | `NotRequired[str]` | *optional* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["HarnessIdentity (src/core/harness_contract.py)"]
    n1["TypedDict"]
    n2["BuiltinHarnessAdapter.identity (src/core/builtin_harness.py)"]
    n3["ClaudeCodeHarnessAdapter.identity (src/core/claude_code_harness.py)"]
    n4["CodexHarnessAdapter.identity (src/core/codex_harness.py)"]
    n5["HarnessAdapter.identity (src/core/harness_adapter.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/harness_contract.md"
    click n2 "../modules/builtin_harness.md"
    click n3 "../modules/claude_code_harness.md"
    click n4 "../modules/codex_harness.md"
    click n5 "../modules/harness_adapter.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [harness_contract](../modules/harness_contract.md) | 0 | `attach_modes`, `contract_version`, `interface`, `name`, `permissions`, `resume_mode`, `schema_pin`, `version` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `TypedDict` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `BuiltinHarnessAdapter.identity` | type_reference | [builtin_harness](../modules/builtin_harness.md) | — |
| `ClaudeCodeHarnessAdapter.identity` | type_reference | [claude_code_harness](../modules/claude_code_harness.md) | — |
| `CodexHarnessAdapter.identity` | type_reference | [codex_harness](../modules/codex_harness.md) | — |
| `HarnessAdapter.identity` | type_reference | [harness_adapter](../modules/harness_adapter.md) | — |
