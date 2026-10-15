# ContractMigrationError

**Location:** `src/core/execution_contracts.py:113`
**Kind:** Class
**Bases:** `ContractError`
**Module:** [execution_contracts](../modules/execution_contracts.md)

## Description

Raised when a legacy payload requests a rejected incomplete feature.

Carries one entry per offending legacy field so a migration failure names
every problem at once instead of the first one only.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(message: str, *, issues: Optional[list[Mapping[str, str]]] = None) -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ContractMigrationError (src/core/execution_contracts.py)"]
    n1["ContractError (src/core/execution_contracts.py)"]
    n2["_check_rejected_fields (src/core/execution_contracts.py)"]
    n3["_require_identity (src/core/execution_contracts.py)"]
    n4["read_legacy_session_manifest (src/core/execution_contracts.py)"]
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
| [execution_contracts](../modules/execution_contracts.md) | 1 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ContractError` | [execution_contracts](../modules/execution_contracts.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_check_rejected_fields` | call | [execution_contracts](../modules/execution_contracts.md) | 1 |
| `_require_identity` | call | [execution_contracts](../modules/execution_contracts.md) | 3 |
| `read_legacy_session_manifest` | call | [execution_contracts](../modules/execution_contracts.md) | 3 |
