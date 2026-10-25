# MultiObjectiveError

**Location:** `src/core/multiobjective.py:21`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [multiobjective](../modules/multiobjective.md)

## Description

Base error for multiobjective semantics (explicit, never silent).

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["MultiObjectiveError (src/core/multiobjective.py)"]
    n1["ValueError"]
    n2["ScalarProxyRejected (src/core/multiobjective.py)"]
    n3["objective_metrics_from_spec (src/core/multiobjective.py)"]
    n4["ObjectiveMetric.__post_init__ (src/core/multiobjective.py)"]
    n5["promotion_frontier (src/core/multiobjective.py)"]
    n6["tests/test_domain_semantics_extension.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    click n0 "../modules/multiobjective.md"
    click n2 "../modules/multiobjective.md"
    click n3 "../modules/multiobjective.md"
    click n4 "../modules/multiobjective.md"
    click n5 "../modules/multiobjective.md"
    click n6 "../modules/test_domain_semantics_extension.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [multiobjective](../modules/multiobjective.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |
| Subclass | `ScalarProxyRejected` | [multiobjective](../modules/multiobjective.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `objective_metrics_from_spec` | call | [multiobjective](../modules/multiobjective.md) | 1 |
| `ObjectiveMetric.__post_init__` | call | [multiobjective](../modules/multiobjective.md) | 1 |
| `promotion_frontier` | call | [multiobjective](../modules/multiobjective.md) | 1 |
| `test_domain_semantics_extension` | import | [test_domain_semantics_extension](../modules/test_domain_semantics_extension.md) | — |
