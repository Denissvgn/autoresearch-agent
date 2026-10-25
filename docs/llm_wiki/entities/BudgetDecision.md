# BudgetDecision

**Location:** `src/core/research_kernel.py:49`
**Kind:** Class
**Bases:** —
**Module:** [research_kernel](../modules/research_kernel.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

Which declared budgets bound the run, and whether one is exhausted.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `within_budget` | `bool` | *required* | — |
| `exhausted` | `tuple[str, ...]` | `()` | — |
| `labels` | `tuple[str, ...]` | `()` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["BudgetDecision (src/core/research_kernel.py)"]
    n1["decide_budget (src/core/research_kernel.py)"]
    n1 --> n0
    click n0 "../modules/research_kernel.md"
    click n1 "../modules/research_kernel.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [research_kernel](../modules/research_kernel.md) | 0 | `exhausted`, `labels`, `within_budget` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `decide_budget` | call | [research_kernel](../modules/research_kernel.md) | 1 |
| `decide_budget` | type_reference | [research_kernel](../modules/research_kernel.md) | — |
