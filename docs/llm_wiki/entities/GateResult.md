# GateResult

**Location:** `scripts/ci_qualification_gates.py:336`
**Kind:** Class
**Bases:** —
**Module:** [ci_qualification_gates](../modules/ci_qualification_gates.md)

**Decorators:** `@dataclass`

## Description

_Auto-generated from `GateResult` in `scripts/ci_qualification_gates.py`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | *required* | — |
| `kind` | `str` | *required* | — |
| `status` | `str` | *required* | — |
| `passed` | `list[str]` | `field(default_factory=list)` | — |
| `failed` | `list[str]` | `field(default_factory=list)` | — |
| `skipped` | `list[str]` | `field(default_factory=list)` | — |
| `errors` | `list[str]` | `field(default_factory=list)` | — |
| `duration_s` | `float` | `0.0` | — |
| `log` | `str` | `''` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["GateResult (scripts/ci_qualification_gates.py)"]
    n1["evaluate_gate (scripts/ci_qualification_gates.py)"]
    n1 --> n0
    click n0 "../modules/ci_qualification_gates.md"
    click n1 "../modules/ci_qualification_gates.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [ci_qualification_gates](../modules/ci_qualification_gates.md) | 0 | `duration_s`, `errors`, `failed`, `kind`, `log`, `name`, `passed`, `skipped`, `status` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `evaluate_gate` | call | [ci_qualification_gates](../modules/ci_qualification_gates.md) | 1 |
| `evaluate_gate` | type_reference | [ci_qualification_gates](../modules/ci_qualification_gates.md) | — |
