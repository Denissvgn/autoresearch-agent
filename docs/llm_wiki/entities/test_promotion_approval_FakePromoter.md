# FakePromoter

**Location:** `tests/test_promotion_approval.py:129`
**Kind:** Class
**Bases:** —
**Module:** [test_promotion_approval](../modules/test_promotion_approval.md)

## Description

Records confirm() invocations so tests can assert it was/wasn't reached.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `() -> None` | — | — |
| `confirm` | *(async)* `(research_id: str, **kwargs)` | — | — |
| `preview` | *(async)* `(research_id: str, **kwargs)` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["FakePromoter (tests/test_promotion_approval.py)"]
    n1["configure_module (tests/test_promotion_approval.py)"]
    n2["promoter (tests/test_promotion_approval.py)"]
    n3["test_canary_scope_unaffected_without_verifier (tests/test_promotion_approval.py)"]
    n4["test_development_scope_unaffected_without_verifier (tests/test_promotion_approval.py)"]
    n5["test_http_confirm_accepts_valid_signature (tests/test_promotion_approval.py)"]
    n6["test_http_confirm_fail_closed_when_verifier_unset (tests/test_promotion_approval.py)"]
    n7["test_http_confirm_rejects_wrong_signature (tests/test_promotion_approval.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    click n0 "../modules/test_promotion_approval.md"
    click n1 "../modules/test_promotion_approval.md"
    click n2 "../modules/test_promotion_approval.md"
    click n3 "../modules/test_promotion_approval.md"
    click n4 "../modules/test_promotion_approval.md"
    click n5 "../modules/test_promotion_approval.md"
    click n6 "../modules/test_promotion_approval.md"
    click n7 "../modules/test_promotion_approval.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_promotion_approval](../modules/test_promotion_approval.md) | 3 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `configure_module` | call | [test_promotion_approval](../modules/test_promotion_approval.md) | 1 |
| `promoter` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
| `test_canary_scope_unaffected_without_verifier` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
| `test_development_scope_unaffected_without_verifier` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
| `test_http_confirm_accepts_valid_signature` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
| `test_http_confirm_fail_closed_when_verifier_unset` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
| `test_http_confirm_rejects_wrong_signature` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
