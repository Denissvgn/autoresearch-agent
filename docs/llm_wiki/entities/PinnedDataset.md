# PinnedDataset

**Location:** `src/core/prompt_scorer.py:52`
**Kind:** Class
**Bases:** —
**Module:** [prompt_scorer](../modules/prompt_scorer.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

A digest-pinned evaluation split (train or holdout).

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `role` | `str` | *required* | — |
| `dataset_id` | `str` | *required* | — |
| `digest` | `str` | *required* | — |
| `examples` | `tuple[Mapping[str, str], ...]` | *required* | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `as_dict` | `() -> dict[str, Any]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["PinnedDataset (src/core/prompt_scorer.py)"]
    n1["_score_outputs (src/core/prompt_scorer.py)"]
    n2["build_score_request (src/core/prompt_scorer.py)"]
    n3["ControlledLocalScorer.register_dataset (src/core/prompt_scorer.py)"]
    n4["pin_dataset (src/core/prompt_scorer.py)"]
    n5["scorer_pin (src/core/prompt_scorer.py)"]
    n6["verify_dataset (src/core/prompt_scorer.py)"]
    n7["test_data_tampering_is_refused (tests/test_prompt_evaluation_domain.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    click n0 "../modules/prompt_scorer.md"
    click n1 "../modules/prompt_scorer.md"
    click n2 "../modules/prompt_scorer.md"
    click n3 "../modules/prompt_scorer.md"
    click n4 "../modules/prompt_scorer.md"
    click n5 "../modules/prompt_scorer.md"
    click n6 "../modules/prompt_scorer.md"
    click n7 "../modules/test_prompt_evaluation_domain.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [prompt_scorer](../modules/prompt_scorer.md) | 1 | `dataset_id`, `digest`, `examples`, `role` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_score_outputs` | type_reference | [prompt_scorer](../modules/prompt_scorer.md) | — |
| `build_score_request` | type_reference | [prompt_scorer](../modules/prompt_scorer.md) | — |
| `ControlledLocalScorer.register_dataset` | type_reference | [prompt_scorer](../modules/prompt_scorer.md) | — |
| `pin_dataset` | call | [prompt_scorer](../modules/prompt_scorer.md) | 1 |
| `pin_dataset` | type_reference | [prompt_scorer](../modules/prompt_scorer.md) | — |
| `scorer_pin` | type_reference | [prompt_scorer](../modules/prompt_scorer.md) | — |
| `verify_dataset` | type_reference | [prompt_scorer](../modules/prompt_scorer.md) | — |
| `test_data_tampering_is_refused` | call | [test_prompt_evaluation_domain](../modules/test_prompt_evaluation_domain.md) | 1 |
