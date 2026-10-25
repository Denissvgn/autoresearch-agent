# ContractError

**Location:** `src/core/execution_contracts.py:103`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [execution_contracts](../modules/execution_contracts.md)

## Description

Base error for contract validation and resolution failures.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ContractError (src/core/execution_contracts.py)"]
    n1["ValueError"]
    n2["ContractMigrationError (src/core/execution_contracts.py)"]
    n3["UnsupportedCapabilityError (src/core/execution_contracts.py)"]
    n4["_chain_pick (src/core/execution_contracts.py)"]
    n5["ensure_capabilities_allowed (src/core/execution_contracts.py)"]
    n6["ensure_request_matches_run_spec (src/core/execution_contracts.py)"]
    n7["reject_raw_secret_parameters (src/core/execution_contracts.py)"]
    n8["resolve_run_inputs (src/core/execution_contracts.py)"]
    n9["SecretReference.parse (src/core/execution_contracts.py)"]
    n10["validate_secret_list (src/core/execution_contracts.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    n10 --> n0
    click n0 "../modules/execution_contracts.md"
    click n2 "../modules/execution_contracts.md"
    click n3 "../modules/execution_contracts.md"
    click n4 "../modules/execution_contracts.md"
    click n5 "../modules/execution_contracts.md"
    click n6 "../modules/execution_contracts.md"
    click n7 "../modules/execution_contracts.md"
    click n8 "../modules/execution_contracts.md"
    click n9 "../modules/execution_contracts.md"
    click n10 "../modules/execution_contracts.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [execution_contracts](../modules/execution_contracts.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |
| Subclass | `ContractMigrationError` | [execution_contracts](../modules/execution_contracts.md) |
| Subclass | `UnsupportedCapabilityError` | [execution_contracts](../modules/execution_contracts.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_chain_pick` | call | [execution_contracts](../modules/execution_contracts.md) | 1 |
| `ensure_capabilities_allowed` | call | [execution_contracts](../modules/execution_contracts.md) | 1 |
| `ensure_request_matches_run_spec` | call | [execution_contracts](../modules/execution_contracts.md) | 1 |
| `reject_raw_secret_parameters` | call | [execution_contracts](../modules/execution_contracts.md) | 1 |
| `resolve_run_inputs` | call | [execution_contracts](../modules/execution_contracts.md) | 1 |
| `SecretReference.parse` | call | [execution_contracts](../modules/execution_contracts.md) | 1 |
| `validate_secret_list` | call | [execution_contracts](../modules/execution_contracts.md) | 2 |
