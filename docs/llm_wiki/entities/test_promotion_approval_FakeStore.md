# FakeStore

**Location:** `tests/test_promotion_approval.py:110`
**Kind:** Class
**Bases:** —
**Module:** [test_promotion_approval](../modules/test_promotion_approval.md)

## Description

Captures audit events so AC #4 can inspect the recorded approver.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `() -> None` | — | — |
| `list_promotions` | *(async)* `(**kwargs)` | — | — |
| `record_audit_event` | *(async)* `(**kwargs)` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["FakeStore (tests/test_promotion_approval.py)"]
    n1["_confirm_audit_event (tests/test_promotion_approval.py)"]
    n2["client (tests/test_promotion_approval.py)"]
    n3["configure_module (tests/test_promotion_approval.py)"]
    n4["promoter (tests/test_promotion_approval.py)"]
    n5["test_audit_records_approver_on_signature_failure (tests/test_promotion_approval.py)"]
    n6["test_audit_records_approver_on_success (tests/test_promotion_approval.py)"]
    n7["test_audit_records_scope_only_for_non_production (tests/test_promotion_approval.py)"]
    n8["test_http_confirm_fail_closed_when_verifier_unset (tests/test_promotion_approval.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    click n0 "../modules/test_promotion_approval.md"
    click n1 "../modules/test_promotion_approval.md"
    click n2 "../modules/test_promotion_approval.md"
    click n3 "../modules/test_promotion_approval.md"
    click n4 "../modules/test_promotion_approval.md"
    click n5 "../modules/test_promotion_approval.md"
    click n6 "../modules/test_promotion_approval.md"
    click n7 "../modules/test_promotion_approval.md"
    click n8 "../modules/test_promotion_approval.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_promotion_approval](../modules/test_promotion_approval.md) | 3 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_confirm_audit_event` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
| `client` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
| `configure_module` | call | [test_promotion_approval](../modules/test_promotion_approval.md) | 1 |
| `promoter` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
| `test_audit_records_approver_on_signature_failure` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
| `test_audit_records_approver_on_success` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
| `test_audit_records_scope_only_for_non_production` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
| `test_http_confirm_fail_closed_when_verifier_unset` | type_reference | [test_promotion_approval](../modules/test_promotion_approval.md) | — |
