# FakeBroadcaster

**Location:** `tests/test_promotion_diagnostics.py:48`
**Kind:** Class
**Bases:** —
**Module:** [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md)

## Description

_Auto-generated from `FakeBroadcaster` in `tests/test_promotion_diagnostics.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `() -> None` | — | — |
| `broadcast` | *(async)* `(payload: Dict[str, Any]) -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["FakeBroadcaster (tests/test_promotion_diagnostics.py)"]
    n1["_patch_broadcaster (tests/test_promotion_diagnostics.py)"]
    n2["test_skip_with_empty_errors_dict_treated_as_no_errors (tests/test_promotion_diagnostics.py)"]
    n3["test_skip_with_errors_surfaces_them_to_all_sinks (tests/test_promotion_diagnostics.py)"]
    n4["test_skip_without_errors_omits_collection_errors_key (tests/test_promotion_diagnostics.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/test_promotion_diagnostics.md"
    click n1 "../modules/test_promotion_diagnostics.md"
    click n2 "../modules/test_promotion_diagnostics.md"
    click n3 "../modules/test_promotion_diagnostics.md"
    click n4 "../modules/test_promotion_diagnostics.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md) | 2 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_patch_broadcaster` | call | [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md) | 1 |
| `_patch_broadcaster` | type_reference | [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md) | — |
| `test_skip_with_empty_errors_dict_treated_as_no_errors` | type_reference | [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md) | — |
| `test_skip_with_errors_surfaces_them_to_all_sinks` | type_reference | [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md) | — |
| `test_skip_without_errors_omits_collection_errors_key` | type_reference | [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md) | — |
