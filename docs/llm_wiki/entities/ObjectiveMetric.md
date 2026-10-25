# ObjectiveMetric

**Location:** `src/core/multiobjective.py:30`
**Kind:** Class
**Bases:** —
**Module:** [multiobjective](../modules/multiobjective.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

One declared objective metric: field name + direction.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `field` | `str` | *required* | — |
| `direction` | `str` | *required* | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__post_init__` | `() -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ObjectiveMetric (src/core/multiobjective.py)"]
    n1["_better (src/core/multiobjective.py)"]
    n2["_no_worse (src/core/multiobjective.py)"]
    n3["dominates (src/core/multiobjective.py)"]
    n4["non_dominated (src/core/multiobjective.py)"]
    n5["objective_metrics_from_spec (src/core/multiobjective.py)"]
    n6["promotion_frontier (src/core/multiobjective.py)"]
    n7["scalar_winner_rejected (src/core/multiobjective.py)"]
    n8["test_case2_pareto_semantics_without_a_scalar_winner (tests/test_domain_semantics_extension.py)"]
    n9["test_case2_scalar_proxy_is_rejected_as_evidence (tests/test_domain_semantics_extension.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    click n0 "../modules/multiobjective.md"
    click n1 "../modules/multiobjective.md"
    click n2 "../modules/multiobjective.md"
    click n3 "../modules/multiobjective.md"
    click n4 "../modules/multiobjective.md"
    click n5 "../modules/multiobjective.md"
    click n6 "../modules/multiobjective.md"
    click n7 "../modules/multiobjective.md"
    click n8 "../modules/test_domain_semantics_extension.md"
    click n9 "../modules/test_domain_semantics_extension.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [multiobjective](../modules/multiobjective.md) | 1 | `direction`, `field` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_better` | type_reference | [multiobjective](../modules/multiobjective.md) | — |
| `_no_worse` | type_reference | [multiobjective](../modules/multiobjective.md) | — |
| `dominates` | type_reference | [multiobjective](../modules/multiobjective.md) | — |
| `non_dominated` | type_reference | [multiobjective](../modules/multiobjective.md) | — |
| `objective_metrics_from_spec` | call | [multiobjective](../modules/multiobjective.md) | 1 |
| `objective_metrics_from_spec` | type_reference | [multiobjective](../modules/multiobjective.md) | — |
| `promotion_frontier` | type_reference | [multiobjective](../modules/multiobjective.md) | — |
| `scalar_winner_rejected` | type_reference | [multiobjective](../modules/multiobjective.md) | — |
| `test_case2_pareto_semantics_without_a_scalar_winner` | call | [test_domain_semantics_extension](../modules/test_domain_semantics_extension.md) | 2 |
| `test_case2_scalar_proxy_is_rejected_as_evidence` | call | [test_domain_semantics_extension](../modules/test_domain_semantics_extension.md) | 2 |
