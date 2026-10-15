# FakeStore

**Location:** `tests/test_auto_promotion_readiness.py:44`
**Kind:** Class
**Bases:** —
**Module:** [test_auto_promotion_readiness](../modules/test_auto_promotion_readiness.md)

## Description

_Auto-generated from `FakeStore` in `tests/test_auto_promotion_readiness.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(*, phase_state: Dict[str, Any], terminal_reason: Optional[str] = None) -> None` | — | — |
| `get_session` | *(async)* `(research_id: str) -> Dict[str, Any]` | — | — |
| `get_iterations` | *(async)* `(research_id: str) -> List[Dict[str, Any]]` | — | — |
| `get_hpo_studies` | *(async)* `(research_id: str) -> List[Dict[str, Any]]` | — | — |
| `list_promotions` | *(async)* `() -> List[Dict[str, Any]]` | — | — |
| `record_audit_event` | *(async)* `(**kwargs: Any) -> Dict[str, Any]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["FakeStore (tests/test_auto_promotion_readiness.py)"]
    n1["test_auto_promote_confirms_only_when_preview_allowed (tests/test_auto_promotion_readiness.py)"]
    n2["test_auto_promote_reports_quality_baseline_blocker (tests/test_auto_promotion_readiness.py)"]
    n3["test_auto_promote_skips_when_pre_promotion_phases_incomplete (tests/test_auto_promotion_readiness.py)"]
    n4["test_auto_promote_treats_preview_value_error_as_skip (tests/test_auto_promotion_readiness.py)"]
    n5["test_auto_promote_uses_preview_before_confirm (tests/test_auto_promotion_readiness.py)"]
    n6["test_auto_promote_uses_training_gate_alias_before_preview (tests/test_auto_promotion_readiness.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    click n0 "../modules/test_auto_promotion_readiness.md"
    click n1 "../modules/test_auto_promotion_readiness.md"
    click n2 "../modules/test_auto_promotion_readiness.md"
    click n3 "../modules/test_auto_promotion_readiness.md"
    click n4 "../modules/test_auto_promotion_readiness.md"
    click n5 "../modules/test_auto_promotion_readiness.md"
    click n6 "../modules/test_auto_promotion_readiness.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_auto_promotion_readiness](../modules/test_auto_promotion_readiness.md) | 6 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `test_auto_promote_confirms_only_when_preview_allowed` | call | [test_auto_promotion_readiness](../modules/test_auto_promotion_readiness.md) | 1 |
| `test_auto_promote_reports_quality_baseline_blocker` | call | [test_auto_promotion_readiness](../modules/test_auto_promotion_readiness.md) | 1 |
| `test_auto_promote_skips_when_pre_promotion_phases_incomplete` | call | [test_auto_promotion_readiness](../modules/test_auto_promotion_readiness.md) | 1 |
| `test_auto_promote_treats_preview_value_error_as_skip` | call | [test_auto_promotion_readiness](../modules/test_auto_promotion_readiness.md) | 1 |
| `test_auto_promote_uses_preview_before_confirm` | call | [test_auto_promotion_readiness](../modules/test_auto_promotion_readiness.md) | 1 |
| `test_auto_promote_uses_training_gate_alias_before_preview` | call | [test_auto_promotion_readiness](../modules/test_auto_promotion_readiness.md) | 1 |
