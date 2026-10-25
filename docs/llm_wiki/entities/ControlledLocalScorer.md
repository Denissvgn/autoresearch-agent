# ControlledLocalScorer

**Location:** `src/core/prompt_scorer.py:178`
**Kind:** Class
**Bases:** —
**Module:** [prompt_scorer](../modules/prompt_scorer.md)

## Description

The declared real scorer: outputs scored against pinned examples.

This is the controlled scoring endpoint's logic. It evaluates real
model outputs; it never invents scores and never falls back to a
simulator — an unreachable endpoint is ``ScorerUnavailable``.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(*, name: str = 'controlled-local-scorer', version: str = '1.0.0', endpoint: str = 'local://controlled-scorer') -> None` | — | — |
| `identity` | `() -> ScorerIdentity` | — | — |
| `register_dataset` | `(dataset: PinnedDataset) -> None` | — | — |
| `score` | `(request: Mapping[str, Any]) -> dict[str, Any]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ControlledLocalScorer (src/core/prompt_scorer.py)"]
    n1["test_candidate_bound_promotion_fixture (tests/test_prompt_evaluation_domain.py)"]
    n2["test_controlled_scorer_evaluates_real_outputs (tests/test_prompt_evaluation_domain.py)"]
    n3["test_data_tampering_is_refused (tests/test_prompt_evaluation_domain.py)"]
    n4["test_live_local_endpoint_run (tests/test_prompt_evaluation_domain.py)"]
    n5["test_optimization_and_qualification_evidence_are_distinguishable (tests/test_prompt_evaluation_domain.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/prompt_scorer.md"
    click n1 "../modules/test_prompt_evaluation_domain.md"
    click n2 "../modules/test_prompt_evaluation_domain.md"
    click n3 "../modules/test_prompt_evaluation_domain.md"
    click n4 "../modules/test_prompt_evaluation_domain.md"
    click n5 "../modules/test_prompt_evaluation_domain.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [prompt_scorer](../modules/prompt_scorer.md) | 4 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `test_candidate_bound_promotion_fixture` | call | [test_prompt_evaluation_domain](../modules/test_prompt_evaluation_domain.md) | 1 |
| `test_controlled_scorer_evaluates_real_outputs` | call | [test_prompt_evaluation_domain](../modules/test_prompt_evaluation_domain.md) | 1 |
| `test_data_tampering_is_refused` | call | [test_prompt_evaluation_domain](../modules/test_prompt_evaluation_domain.md) | 1 |
| `test_live_local_endpoint_run` | call | [test_prompt_evaluation_domain](../modules/test_prompt_evaluation_domain.md) | 1 |
| `test_optimization_and_qualification_evidence_are_distinguishable` | call | [test_prompt_evaluation_domain](../modules/test_prompt_evaluation_domain.md) | 1 |
