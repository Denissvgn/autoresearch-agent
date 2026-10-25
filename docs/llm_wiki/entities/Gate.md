# Gate

**Location:** `scripts/ci_qualification_gates.py:95`
**Kind:** Class
**Bases:** —
**Module:** [ci_qualification_gates](../modules/ci_qualification_gates.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

_Auto-generated from `Gate` in `scripts/ci_qualification_gates.py`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | *required* | — |
| `kind` | `str` | *required* | — |
| `suites` | `tuple[str, ...]` | *required* | — |
| `required_coverage` | `tuple[str, ...]` | *required* | — |
| `requires_env` | `tuple[str, ...]` | `()` | — |
| `budget_s` | `int` | `900` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["Gate (scripts/ci_qualification_gates.py)"]
    n1["evaluate_gate (scripts/ci_qualification_gates.py)"]
    n1 --> n0
    click n0 "../modules/ci_qualification_gates.md"
    click n1 "../modules/ci_qualification_gates.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [ci_qualification_gates](../modules/ci_qualification_gates.md) | 0 | `budget_s`, `kind`, `name`, `required_coverage`, `requires_env`, `suites` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `evaluate_gate` | type_reference | [ci_qualification_gates](../modules/ci_qualification_gates.md) | — |
