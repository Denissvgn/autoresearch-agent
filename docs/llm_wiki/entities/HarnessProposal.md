# HarnessProposal

**Location:** `src/core/harness_contract.py:56`
**Kind:** Class
**Bases:** `TypedDict`
**Module:** [harness_contract](../modules/harness_contract.md)

## Description

A proposal carried across the boundary (e.g. a steering proposal).

## Attributes

| Name | Type | Presence | Description |
|------|------|----------|-------------|
| `proposal_id` | `str` | *required* | — |
| `kind` | `str` | *required* | — |
| `target` | `str` | *required* | — |
| `payload` | `Mapping[str, Any]` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["HarnessProposal (src/core/harness_contract.py)"]
    n1["TypedDict"]
    n2["BuiltinHarnessAdapter.route_proposal (src/core/builtin_harness.py)"]
    n3["src/core/harness_adapter.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    click n0 "../modules/harness_contract.md"
    click n2 "../modules/builtin_harness.md"
    click n3 "../modules/harness_adapter.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [harness_contract](../modules/harness_contract.md) | 0 | `kind`, `payload`, `proposal_id`, `target` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `TypedDict` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `BuiltinHarnessAdapter.route_proposal` | type_reference | [builtin_harness](../modules/builtin_harness.md) | — |
| `harness_adapter` | import | [harness_adapter](../modules/harness_adapter.md) | — |
