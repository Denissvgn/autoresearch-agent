# multiobjective Module

**Path:** `src/core/multiobjective.py`

## Description

Multiobjective (Pareto) result and promotion semantics.

The declarative contract's scalar objective (one primary metric and one
direction) cannot express a genuine tradeoff: combining metrics into a
scalar proxy destroys the requirement. This module implements the
multiobjective extension: dominance over declared metrics with their own
directions, non-dominated frontiers, and promotion semantics that select
a SET — never a forced scalar winner. Dispatch keys on the declared
objective kind only; nothing here branches on a domain or skill id.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `dataclasses` | `dataclass`, `field` |
| `math` | `math` |
| `typing` | `Any`, `Mapping`, `Optional`, `Sequence` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/multiobjective.py"]
    n1["tests/test_domain_semantics_extension.py"]
    n1 --> n0
    click n0 "../modules/multiobjective.md"
    click n1 "../modules/test_domain_semantics_extension.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [test_domain_semantics_extension](../modules/test_domain_semantics_extension.md) |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [MultiObjectiveError](../entities/MultiObjectiveError.md) | 21 | `ValueError` | Base error for multiobjective semantics (explicit, never silent). |
| [ScalarProxyRejected](../entities/ScalarProxyRejected.md) | 25 | `MultiObjectiveError` | A scalar winner cannot stand in for a multiobjective requirement. |
| [ObjectiveMetric](../entities/ObjectiveMetric.md) | 30 | — | One declared objective metric: field name + direction. |
| [Candidate](../entities/Candidate.md) | 44 | — | One measured candidate: identity + per-metric values. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_finite` | `(value: Optional[float]) -> bool` | — | — |
| `_better` | `(metric: ObjectiveMetric, a: float, b: float) -> bool` | — | — |
| `_no_worse` | `(metric: ObjectiveMetric, a: float, b: float) -> bool` | — | — |
| `dominates` | `(a: Candidate, b: Candidate, objectives: Sequence[ObjectiveMetric]) -> bool` | — | True when ``a`` Pareto-dominates ``b`` on every declared metric. |
| `non_dominated` | `(candidates: Sequence[Candidate], objectives: Sequence[ObjectiveMetric]) -> list[Candidate]` | — | The Pareto frontier: candidates dominated by no other candidate. |
| `promotion_frontier` | `(candidates: Sequence[Candidate], objectives: Sequence[ObjectiveMetric]) -> dict[str, Any]` | — | Promotion semantics for a multiobjective requirement. |
| `scalar_winner_rejected` | `(objectives: Sequence[ObjectiveMetric]) -> None` | — | Explicit refusal: no scalar winner is derived from a frontier. |
| `objective_metrics_from_spec` | `(spec: Any) -> list[ObjectiveMetric]` | — | Build metrics from a declared ``ObjectiveSpec`` (generic dispatch). |
