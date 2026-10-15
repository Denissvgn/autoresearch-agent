# UnsupportedCapabilityError

**Location:** `src/core/execution_contracts.py:105`
**Kind:** Class
**Bases:** `ContractError`
**Module:** [execution_contracts](../modules/execution_contracts.md)

## Description

Raised before work starts when a capability is unknown or unsupported.

Unknown or unsupported capabilities fail explicitly; nothing silently
falls back to weaker semantics.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["UnsupportedCapabilityError (src/core/execution_contracts.py)"]
    n1["ContractError (src/core/execution_contracts.py)"]
    n2["ensure_capabilities_allowed (src/core/execution_contracts.py)"]
    n3["ensure_isolation_boundary (src/core/execution_contracts.py)"]
    n4["ensure_minimum_capabilities (src/core/execution_contracts.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/execution_contracts.md"
    click n1 "../modules/execution_contracts.md"
    click n2 "../modules/execution_contracts.md"
    click n3 "../modules/execution_contracts.md"
    click n4 "../modules/execution_contracts.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [execution_contracts](../modules/execution_contracts.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ContractError` | [execution_contracts](../modules/execution_contracts.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `ensure_capabilities_allowed` | call | [execution_contracts](../modules/execution_contracts.md) | 1 |
| `ensure_isolation_boundary` | call | [execution_contracts](../modules/execution_contracts.md) | 1 |
| `ensure_minimum_capabilities` | call | [execution_contracts](../modules/execution_contracts.md) | 1 |
