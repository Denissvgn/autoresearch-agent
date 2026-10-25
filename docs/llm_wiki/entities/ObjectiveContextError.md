# ObjectiveContextError

**Location:** `src/core/objective_comparator.py:52`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [objective_comparator](../modules/objective_comparator.md)

## Description

Raised when a comparison needs objective context that is not declared.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ObjectiveContextError (src/core/objective_comparator.py)"]
    n1["ValueError"]
    n2["objective_comparator_for_manifest (src/core/objective_comparator.py)"]
    n3["objective_comparator_for_skill_id (src/core/objective_comparator.py)"]
    n4["ObjectiveComparator.__post_init__ (src/core/objective_comparator.py)"]
    n5["ObjectiveComparator.resolve (src/core/objective_comparator.py)"]
    n6["src/core/orchestrator.py"]
    n7["tests/test_objective_comparator.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    click n0 "../modules/objective_comparator.md"
    click n2 "../modules/objective_comparator.md"
    click n3 "../modules/objective_comparator.md"
    click n4 "../modules/objective_comparator.md"
    click n5 "../modules/objective_comparator.md"
    click n6 "../modules/orchestrator.md"
    click n7 "../modules/test_objective_comparator.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [objective_comparator](../modules/objective_comparator.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `objective_comparator_for_manifest` | call | [objective_comparator](../modules/objective_comparator.md) | 1 |
| `objective_comparator_for_skill_id` | call | [objective_comparator](../modules/objective_comparator.md) | 2 |
| `ObjectiveComparator.__post_init__` | call | [objective_comparator](../modules/objective_comparator.md) | 3 |
| `ObjectiveComparator.resolve` | call | [objective_comparator](../modules/objective_comparator.md) | 1 |
| `orchestrator` | import | [orchestrator](../modules/orchestrator.md) | — |
| `test_objective_comparator` | import | [test_objective_comparator](../modules/test_objective_comparator.md) | — |
