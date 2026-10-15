# FakePromotionStore

**Location:** `tests/test_config_promoter_gate_bundle.py:22`
**Kind:** Class
**Bases:** —
**Module:** [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md)

## Description

_Auto-generated from `FakePromotionStore` in `tests/test_config_promoter_gate_bundle.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(best: dict, model_type: str = 'direction', promotions: list[dict] \| None = None, iterations: list[dict] \| None = None) -> None` | — | — |
| `get_session` | *(async)* `(research_id: str)` | — | — |
| `get_best_iteration` | *(async)* `(research_id: str)` | — | — |
| `get_iterations` | *(async)* `(research_id: str)` | — | — |
| `get_iteration` | *(async)* `(research_id: str, iteration: int)` | — | — |
| `record_promotion` | *(async)* `(**kwargs)` | — | — |
| `list_promotions` | *(async)* `()` | — | — |
| `get_latest_promotion` | *(async)* `(*, model_type: str, instrument: str, timeframe: str, scope: str)` | — | — |
| `get_latest_development_promotion` | *(async)* `(*, model_type: str, instrument: str, timeframe: str)` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["FakePromotionStore (tests/test_config_promoter_gate_bundle.py)"]
    n1["test_confirm_blocks_reload_failure_before_replacing_prior_config (tests/test_config_promoter_gate_bundle.py)"]
    n2["test_confirm_records_promotion_when_bundle_passes (tests/test_config_promoter_gate_bundle.py)"]
    n3["test_confirm_requires_cross_service_consistency (tests/test_config_promoter_gate_bundle.py)"]
    n4["test_confirm_requires_development_gate_bundle_pass (tests/test_config_promoter_gate_bundle.py)"]
    n5["test_confirm_requires_quality_baseline_pass (tests/test_config_promoter_gate_bundle.py)"]
    n6["test_paper_scope_remains_local_only (tests/test_config_promoter_gate_bundle.py)"]
    n7["test_preview_accepts_finalist_with_honest_rl_oos (tests/test_config_promoter_gate_bundle.py)"]
    n8["test_preview_accepts_rl_candidate_with_honest_oos_provenance (tests/test_config_promoter_gate_bundle.py)"]
    n9["test_preview_accepts_structured_tsfm_fallback_validation (tests/test_config_promoter_gate_bundle.py)"]
    n10["test_preview_allows_feature_candidate_without_economic_replay (tests/test_config_promoter_gate_bundle.py)"]
    n11["test_preview_allows_metric_within_or_above_development_baseline (tests/test_config_promoter_gate_bundle.py)"]
    n12["test_preview_blocks_adaptive_finalist_missing_schema_flags (tests/test_config_promoter_gate_bundle.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    n10 --> n0
    n11 --> n0
    n12 --> n0
    click n0 "../modules/test_config_promoter_gate_bundle.md"
    click n1 "../modules/test_config_promoter_gate_bundle.md"
    click n2 "../modules/test_config_promoter_gate_bundle.md"
    click n3 "../modules/test_config_promoter_gate_bundle.md"
    click n4 "../modules/test_config_promoter_gate_bundle.md"
    click n5 "../modules/test_config_promoter_gate_bundle.md"
    click n6 "../modules/test_config_promoter_gate_bundle.md"
    click n7 "../modules/test_config_promoter_gate_bundle.md"
    click n8 "../modules/test_config_promoter_gate_bundle.md"
    click n9 "../modules/test_config_promoter_gate_bundle.md"
    click n10 "../modules/test_config_promoter_gate_bundle.md"
    click n11 "../modules/test_config_promoter_gate_bundle.md"
    click n12 "../modules/test_config_promoter_gate_bundle.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 9 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `test_confirm_blocks_reload_failure_before_replacing_prior_config` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `test_confirm_records_promotion_when_bundle_passes` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `test_confirm_requires_cross_service_consistency` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `test_confirm_requires_development_gate_bundle_pass` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `test_confirm_requires_quality_baseline_pass` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `test_paper_scope_remains_local_only` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `test_preview_accepts_finalist_with_honest_rl_oos` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `test_preview_accepts_rl_candidate_with_honest_oos_provenance` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `test_preview_accepts_structured_tsfm_fallback_validation` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `test_preview_allows_feature_candidate_without_economic_replay` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `test_preview_allows_metric_within_or_above_development_baseline` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `test_preview_blocks_adaptive_finalist_missing_schema_flags` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |

> References: showing 12 of 40 logical references; 28 omitted by the 12-row generated summary limit.
