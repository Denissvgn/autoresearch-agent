# DatasetTampered

**Location:** `src/core/prompt_scorer.py:34`
**Kind:** Class
**Bases:** `Exception`
**Module:** [prompt_scorer](../modules/prompt_scorer.md)

## Description

A pinned dataset no longer matches its digest.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["DatasetTampered (src/core/prompt_scorer.py)"]
    n1["Exception"]
    n2["verify_dataset (src/core/prompt_scorer.py)"]
    n3["tests/test_prompt_evaluation_domain.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    click n0 "../modules/prompt_scorer.md"
    click n2 "../modules/prompt_scorer.md"
    click n3 "../modules/test_prompt_evaluation_domain.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [prompt_scorer](../modules/prompt_scorer.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Exception` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `verify_dataset` | call | [prompt_scorer](../modules/prompt_scorer.md) | 1 |
| `test_prompt_evaluation_domain` | import | [test_prompt_evaluation_domain](../modules/test_prompt_evaluation_domain.md) | — |
