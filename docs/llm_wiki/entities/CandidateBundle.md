# CandidateBundle

**Location:** `src/core/code_evaluator.py:32`
**Kind:** Class
**Bases:** —
**Module:** [code_evaluator](../modules/code_evaluator.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

A multi-file candidate: named target files with full contents.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `candidate_id` | `str` | *required* | — |
| `files` | `Mapping[str, str]` | *required* | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `digest` | `() -> str` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["CandidateBundle (src/core/code_evaluator.py)"]
    n1["apply_bundle (src/core/code_evaluator.py)"]
    n2["evaluate_bundle (src/core/code_evaluator.py)"]
    n3["promotion_preview (src/core/code_evaluator.py)"]
    n4["_bundle (tests/test_code_refactor_domain.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/code_evaluator.md"
    click n1 "../modules/code_evaluator.md"
    click n2 "../modules/code_evaluator.md"
    click n3 "../modules/code_evaluator.md"
    click n4 "../modules/test_code_refactor_domain.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [code_evaluator](../modules/code_evaluator.md) | 1 | `candidate_id`, `files` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `apply_bundle` | type_reference | [code_evaluator](../modules/code_evaluator.md) | — |
| `evaluate_bundle` | type_reference | [code_evaluator](../modules/code_evaluator.md) | — |
| `promotion_preview` | type_reference | [code_evaluator](../modules/code_evaluator.md) | — |
| `_bundle` | call | [test_code_refactor_domain](../modules/test_code_refactor_domain.md) | 1 |
