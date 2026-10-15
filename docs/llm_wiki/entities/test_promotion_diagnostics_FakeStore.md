# FakeStore

**Location:** `tests/test_promotion_diagnostics.py:56`
**Kind:** Class
**Bases:** —
**Module:** [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md)

## Description

_Auto-generated from `FakeStore` in `tests/test_promotion_diagnostics.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `() -> None` | — | — |
| `record_audit_event` | *(async)* `(**kwargs: Any) -> Dict[str, Any]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["FakeStore (tests/test_promotion_diagnostics.py)"]
    n1["_orchestrator (tests/test_promotion_diagnostics.py)"]
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
| `_orchestrator` | type_reference | [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md) | — |
| `test_skip_with_empty_errors_dict_treated_as_no_errors` | call | [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md) | 1 |
| `test_skip_with_errors_surfaces_them_to_all_sinks` | call | [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md) | 1 |
| `test_skip_without_errors_omits_collection_errors_key` | call | [test_promotion_diagnostics](../modules/test_promotion_diagnostics.md) | 1 |
