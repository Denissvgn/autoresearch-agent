# _AutoPromoteStore

**Location:** `tests/test_manifest_runtime_production_path.py:415`
**Kind:** Class
**Bases:** —
**Module:** [test_manifest_runtime_production_path](../modules/test_manifest_runtime_production_path.md)

## Description

_Auto-generated from `_AutoPromoteStore` in `tests/test_manifest_runtime_production_path.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `() -> None` | — | — |
| `get_session` | *(async)* `(research_id: str)` | — | — |
| `get_iterations` | *(async)* `(research_id: str)` | — | — |
| `get_hpo_studies` | *(async)* `(research_id: str)` | — | — |
| `list_promotions` | *(async)* `()` | — | — |
| `record_audit_event` | *(async)* `(**kwargs: Any)` | — | — |
| `update_session` | *(async)* `(research_id, **fields)` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["_AutoPromoteStore (tests/test_manifest_runtime_production_path.py)"]
    n1["test_auto_promote_skips_loudly_on_unsupported_target (tests/test_manifest_runtime_production_path.py)"]
    n2["test_auto_promote_transitional_sessions_keep_default_constructor (tests/test_manifest_runtime_production_path.py)"]
    n1 --> n0
    n2 --> n0
    click n0 "../modules/test_manifest_runtime_production_path.md"
    click n1 "../modules/test_manifest_runtime_production_path.md"
    click n2 "../modules/test_manifest_runtime_production_path.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_manifest_runtime_production_path](../modules/test_manifest_runtime_production_path.md) | 7 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `test_auto_promote_skips_loudly_on_unsupported_target` | call | [test_manifest_runtime_production_path](../modules/test_manifest_runtime_production_path.md) | 1 |
| `test_auto_promote_transitional_sessions_keep_default_constructor` | call | [test_manifest_runtime_production_path](../modules/test_manifest_runtime_production_path.md) | 1 |
