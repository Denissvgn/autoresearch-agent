# TestJSONMarkerParserForgery

**Location:** `tests/test_metrics_forgery.py:34`
**Kind:** Class
**Bases:** —
**Module:** [test_metrics_forgery](../modules/test_metrics_forgery.md)

## Description

_Auto-generated from `TestJSONMarkerParserForgery` in `tests/test_metrics_forgery.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `test_valid_nonce_accepted_and_verified` | `()` | — | — |
| `test_wrong_nonce_rejected` | `()` | — | — |
| `test_missing_nonce_rejected` | `()` | — | — |
| `test_legacy_session_graceful_downgrade` | `()` | — | require_signed_metrics=True but no session nonce → unverified. |
| `test_default_no_key_added` | `()` | — | require_signed_metrics=False → no validation, no key (parity). |
| `test_bytes_nonce_accepted` | `()` | — | session_nonce as bytes is hex-encoded for comparison. |
| `test_no_marker_returns_none` | `()` | — | Text without a marker → None regardless of nonce config. |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_metrics_forgery](../modules/test_metrics_forgery.md) | 7 | — |
