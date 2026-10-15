# LedgerError

**Location:** `scripts/check_execution_ledger.py:50`
**Kind:** Class
**Bases:** `Exception`
**Module:** [check_execution_ledger](../modules/check_execution_ledger.md)

## Description

Raised for structural problems that make the ledger uninterpretable.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["LedgerError (scripts/check_execution_ledger.py)"]
    n1["Exception"]
    n2["_load_json (scripts/check_execution_ledger.py)"]
    n3["_load_jsonl (scripts/check_execution_ledger.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    click n0 "../modules/check_execution_ledger.md"
    click n2 "../modules/check_execution_ledger.md"
    click n3 "../modules/check_execution_ledger.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [check_execution_ledger](../modules/check_execution_ledger.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Exception` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_load_json` | call | [check_execution_ledger](../modules/check_execution_ledger.md) | 2 |
| `_load_jsonl` | call | [check_execution_ledger](../modules/check_execution_ledger.md) | 2 |
