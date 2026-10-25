# ScopePolicyError

**Location:** `src/core/promotion_policy.py:20`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [promotion_policy](../modules/promotion_policy.md)

## Description

Raised for invalid or unimplementable scope declarations.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ScopePolicyError (src/core/promotion_policy.py)"]
    n1["ValueError"]
    n2["src/core/config_promoter.py"]
    n3["compile_scope_graph (src/core/promotion_policy.py)"]
    n4["tests/test_promotion_policy.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/promotion_policy.md"
    click n2 "../modules/config_promoter.md"
    click n3 "../modules/promotion_policy.md"
    click n4 "../modules/test_promotion_policy.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [promotion_policy](../modules/promotion_policy.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `config_promoter` | import | [config_promoter](../modules/config_promoter.md) | — |
| `compile_scope_graph` | call | [promotion_policy](../modules/promotion_policy.md) | 4 |
| `test_promotion_policy` | import | [test_promotion_policy](../modules/test_promotion_policy.md) | — |
