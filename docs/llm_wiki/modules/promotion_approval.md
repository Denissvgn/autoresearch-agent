# promotion_approval Module

**Path:** `src/core/promotion_approval.py`

## Description

Pure production-approval v2 encoding and candidate binding (no I/O).

The HMAC covers the caller's candidate, never a substituted current winner.
Core confirmation must compare that candidate to its actual preview before writes.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `collections.abc` | `Mapping` |
| `hashlib` | `hashlib` |
| `json` | `json` |
| `re` | `re` |
| `typing` | `Any` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/api/promotion.py"]
    n1["src/core/config_promoter.py"]
    n2["src/core/promotion_approval.py"]
    n3["tests/test_promotion_approval.py"]
    n4["tests/test_promotion_policy.py"]
    n5["tests/test_release_promotion_safety.py"]
    n0 --> n1
    n0 --> n2
    n1 --> n2
    n3 --> n0
    n3 --> n2
    n4 --> n1
    n4 --> n2
    n5 --> n0
    n5 --> n1
    n5 --> n2
    click n0 "../modules/promotion.md"
    click n1 "../modules/config_promoter.md"
    click n2 "../modules/promotion_approval.md"
    click n3 "../modules/test_promotion_approval.md"
    click n4 "../modules/test_promotion_policy.md"
    click n5 "../modules/test_release_promotion_safety.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [promotion](../modules/promotion.md) |
| Inbound | [config_promoter](../modules/config_promoter.md) |
| Inbound | [test_promotion_approval](../modules/test_promotion_approval.md) |
| Inbound | [test_promotion_policy](../modules/test_promotion_policy.md) |
| Inbound | [test_release_promotion_safety](../modules/test_release_promotion_safety.md) |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `canonical_json` | `(value: Mapping[str, Any]) -> bytes` | — | Stable UTF-8 JSON: sorted keys, compact separators, ASCII escapes, no NaN. |
| `target_identity` | `(descriptor: Mapping[str, Any]) -> str` | — | Hash identity()'s kind/path/endpoint descriptor, excluding credentials. |
| `candidate_fields` | `(candidate: Mapping[str, Any] \| None) -> dict[str, Any]` | — | Require exact candidate types: integer iteration and lowercase SHA256s. |
| `validate_candidate_binding` | `(approval: Mapping[str, Any] \| None, preview: Mapping[str, Any]) -> None` | — | Fail closed if the approved candidate differs from the actual preview. |
| `canonical_approval_message` | `(research_id: str, scope: str, approval: Mapping[str, Any]) -> bytes` | — | Encode v2 signed provenance and candidate. Scope must already be canonical. |
