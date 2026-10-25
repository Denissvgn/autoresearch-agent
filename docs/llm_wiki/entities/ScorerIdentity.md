# ScorerIdentity

**Location:** `src/core/prompt_scorer.py:39`
**Kind:** Class
**Bases:** —
**Module:** [prompt_scorer](../modules/prompt_scorer.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

Who scores the outputs, and at which pinned endpoint.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | *required* | — |
| `version` | `str` | *required* | — |
| `endpoint` | `str` | *required* | — |
| `contract_version` | `str` | `SCORER_CONTRACT_VERSION` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `as_dict` | `() -> dict[str, Any]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ScorerIdentity (src/core/prompt_scorer.py)"]
    n1["ControlledLocalScorer.__init__ (src/core/prompt_scorer.py)"]
    n2["ControlledLocalScorer.identity (src/core/prompt_scorer.py)"]
    n3["OfflineDemoScorer.__init__ (src/core/prompt_scorer.py)"]
    n4["scorer_pin (src/core/prompt_scorer.py)"]
    n5["test_continuation_preserves_the_pinned_configuration (tests/test_prompt_evaluation_domain.py)"]
    n6["test_pinned_datasets_and_scorer_identity (tests/test_prompt_evaluation_domain.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    click n0 "../modules/prompt_scorer.md"
    click n1 "../modules/prompt_scorer.md"
    click n2 "../modules/prompt_scorer.md"
    click n3 "../modules/prompt_scorer.md"
    click n4 "../modules/prompt_scorer.md"
    click n5 "../modules/test_prompt_evaluation_domain.md"
    click n6 "../modules/test_prompt_evaluation_domain.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [prompt_scorer](../modules/prompt_scorer.md) | 1 | `contract_version`, `endpoint`, `name`, `version` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `ControlledLocalScorer.__init__` | call | [prompt_scorer](../modules/prompt_scorer.md) | 1 |
| `ControlledLocalScorer.identity` | type_reference | [prompt_scorer](../modules/prompt_scorer.md) | — |
| `OfflineDemoScorer.__init__` | call | [prompt_scorer](../modules/prompt_scorer.md) | 1 |
| `scorer_pin` | type_reference | [prompt_scorer](../modules/prompt_scorer.md) | — |
| `test_continuation_preserves_the_pinned_configuration` | call | [test_prompt_evaluation_domain](../modules/test_prompt_evaluation_domain.md) | 1 |
| `test_pinned_datasets_and_scorer_identity` | call | [test_prompt_evaluation_domain](../modules/test_prompt_evaluation_domain.md) | 1 |
