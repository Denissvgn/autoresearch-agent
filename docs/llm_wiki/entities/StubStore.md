# _StubStore

**Location:** `tests/test_significance.py:199`
**Kind:** Class
**Bases:** —
**Module:** [test_significance](../modules/test_significance.md)

## Description

_Auto-generated from `_StubStore` in `tests/test_significance.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(best_metric: Optional[float], rows: list[dict]) -> None` | — | — |
| `get_session` | *(async)* `(research_id: str) -> Optional[dict]` | — | — |
| `get_iterations` | *(async)* `(research_id: str) -> list[dict]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["_StubStore (tests/test_significance.py)"]
    n1["test_infer_decision_regression_blocks_noise_chase (tests/test_significance.py)"]
    n2["test_infer_decision_significant_beats_epsilon (tests/test_significance.py)"]
    n3["test_infer_decision_undeclared_is_byte_identical_legacy (tests/test_significance.py)"]
    n4["test_significance_sparse_data_falls_back_to_legacy (tests/test_significance.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/test_significance.md"
    click n1 "../modules/test_significance.md"
    click n2 "../modules/test_significance.md"
    click n3 "../modules/test_significance.md"
    click n4 "../modules/test_significance.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_significance](../modules/test_significance.md) | 3 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `test_infer_decision_regression_blocks_noise_chase` | call | [test_significance](../modules/test_significance.md) | 1 |
| `test_infer_decision_significant_beats_epsilon` | call | [test_significance](../modules/test_significance.md) | 2 |
| `test_infer_decision_undeclared_is_byte_identical_legacy` | call | [test_significance](../modules/test_significance.md) | 1 |
| `test_significance_sparse_data_falls_back_to_legacy` | call | [test_significance](../modules/test_significance.md) | 1 |
