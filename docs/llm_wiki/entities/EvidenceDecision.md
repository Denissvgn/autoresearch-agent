# EvidenceDecision

**Location:** `src/core/research_kernel.py:58`
**Kind:** Class
**Bases:** —
**Module:** [research_kernel](../modules/research_kernel.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

The verification state of one evaluator result.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `status` | `str` | *required* | — |
| `reasons` | `tuple[str, ...]` | `()` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["EvidenceDecision (src/core/research_kernel.py)"]
    n1["verify_evidence (src/core/research_kernel.py)"]
    n1 --> n0
    click n0 "../modules/research_kernel.md"
    click n1 "../modules/research_kernel.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [research_kernel](../modules/research_kernel.md) | 0 | `reasons`, `status` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `verify_evidence` | call | [research_kernel](../modules/research_kernel.md) | 1 |
| `verify_evidence` | type_reference | [research_kernel](../modules/research_kernel.md) | — |
