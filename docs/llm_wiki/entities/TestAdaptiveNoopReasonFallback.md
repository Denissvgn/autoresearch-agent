# TestAdaptiveNoopReasonFallback

**Location:** `tests/test_adaptive_noop_reason_fallback.py:33`
**Kind:** Class
**Bases:** —
**Module:** [test_adaptive_noop_reason_fallback](../modules/test_adaptive_noop_reason_fallback.md)

## Description

_Auto-generated from `TestAdaptiveNoopReasonFallback` in `tests/test_adaptive_noop_reason_fallback.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `test_explicit_noop_reason_wins` | `()` | — | — |
| `test_results_fallback_when_no_noop_reason_key` | `()` | — | — |
| `test_unavailable_fallback_when_requested_false` | `()` | — | requested=False with no explicit noop_reason → unavailable (accepted). |
| `test_unavailable_fallback_when_empty_adaptive_features` | `()` | — | Empty adaptive_features dict → unavailable (accepted). |
| `test_empty_string_when_requested_true_no_reason` | `()` | — | requested=True but no noop_reason → empty string (not a noop). |
| `test_empty_string_when_requested_none_no_reason` | `()` | — | requested key absent → empty string (ambiguous, don't assume unavailable). |
| `test_unavailable_is_in_accepted_set` | `()` | — | Ensure the fallback value is in ACCEPTED_ADAPTIVE_NOOP_REASONS. |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_adaptive_noop_reason_fallback](../modules/test_adaptive_noop_reason_fallback.md) | 7 | — |
