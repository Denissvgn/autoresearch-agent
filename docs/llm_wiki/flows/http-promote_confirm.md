# promote_confirm

**Entry point:** `promote_confirm` (`http`)
**Source:** [promotion](../modules/promotion.md)
**Modules touched:** [audit](../modules/audit.md), [compat_legacy_alias](../modules/compat_legacy_alias.md), [config](../modules/config.md), [config_promoter](../modules/config_promoter.md), and 3 more

**Complete modules touched:**

- [audit](../modules/audit.md)
- [compat_legacy_alias](../modules/compat_legacy_alias.md)
- [config](../modules/config.md)
- [config_promoter](../modules/config_promoter.md)
- [promotion](../modules/promotion.md)
- [promotion_approval](../modules/promotion_approval.md)
- [promotion_target](../modules/promotion_target.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as promote_confirm
    participant p1 as _verify_production_approval_signature
    participant p2 as _promoter_for_session
    participant p3 as _audit
    participant p4 as _inject_target_kind
    participant p5 as PromotionScopeRequest
    participant p6 as _approval_payload
    participant p7 as _confirm_audit_metadata
    participant p8 as record_api_audit_event
    participant p9 as canonical_approval_message
    participant p10 as promotion_target_from_manifest
    participant p11 as request_metadata
    participant p12 as secret_value
    participant p13 as model_type_to_skill_id
    participant p14 as ConfigPromoter
    participant p15 as _request_actor
    participant p16 as FilePathPromotionTarget
    participant p17 as WebhookPromotionTarget
    participant p18 as canonical_json
    participant p19 as candidate_fields
    participant p20 as str
    participant p21 as (…).lower
    participant p22 as promoter.confirm
    participant p23 as HTTPException
    p0->>p1: _verify_production_approval_signature
    p0->>p2: _promoter_for_session
    p0->>p3: _audit
    p0->>p4: _inject_target_kind
    p0->>p5: PromotionScopeRequest
    p0->>p6: _approval_payload
    p0->>p7: _confirm_audit_metadata
    p3->>p8: record_api_audit_event
    p1->>p9: canonical_approval_message
    p2->>p10: promotion_target_from_manifest
    p8->>p11: request_metadata
    p1->>p12: secret_value
    p2->>p13: model_type_to_skill_id
    p2->>p14: ConfigPromoter
    p8->>p15: _request_actor
    p10->>p16: FilePathPromotionTarget
    p10->>p17: WebhookPromotionTarget
    p9->>p18: canonical_json
    p9->>p19: candidate_fields
    p0-->>p20: str(e)
    p0-->>p21: (…).lower
    p0-->>p22: promoter.confirm(research_id, scope=payload.scope, approval=approval)
    p0-->>p23: HTTPException(status_code=400, detail=str(...))
    p0-->>p20: str(e)
    p0-->>p20: str(e)
    p0-->>p23: HTTPException(status_code=404, detail=str(...))
    p0-->>p20: str(e)
    p0-->>p20: str(e)
    p0-->>p23: HTTPException(status_code=500, detail=str(...))
    p0-->>p20: str(e)
```

> Call sequence diagram shows 30 of 107 interactions; 77 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 9 of 50 (41 omitted); unresolved 2 of 32 (30 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/api/promotion.py:_approval_payload` | 3 | - | external | 1 |
| `src/api/promotion.py:_approval_payload` | 3 | - | unresolved | 2 |
| `src/api/promotion.py:_confirm_audit_metadata` | 7 | - | external | 1 |
| `src/config.py:secret_value` | 11 | - | external | 1 |
| `src/config.py:secret_value` | 11 | - | unresolved | 1 |
| `src/api/promotion.py:_verify_production_approval_signature` | 10 | - | external | 5 |
| `src/core/promotion_approval.py:canonical_approval_message` | 16 | - | external | 7 |
| `src/core/promotion_approval.py:canonical_approval_message` | 16 | - | unresolved | 5 |
> Omission summary shows 8 of 26 groups; 18 further groups are not expanded here. Counts above include all omitted interactions.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. promote_confirm"]
    s2["2. PromotionScopeRequest"]
    s3["3. _approval_payload"]
    s4["4. hasattr"]
    s5["5. approval.model_dump (src/api/promotion.py:_approval_payload)"]
    s6["6. approval.dict"]
    s7["7. _confirm_audit_metadata"]
    s8["8. getattr (src/api/promotion.py:_confirm_audit_metadata)"]
    s9["9. (…).lower"]
    s10["10. _verify_production_approval_signature"]
    s11["11. secret_value"]
    s12["12. isinstance (src/config.py:secret_value)"]
    s1 -->|"PromotionScopeRequest(data not statically known)"| s2
    s1 -->|"_approval_payload(payload.approval)"| s3
    s3 -. "hasattr(approval, 'model_dump')" .-> s4
    s3 -. "approval.model_dump (src/api/promotion.py:_approval_payload)(exclude_none=True)" .-> s5
    s3 -. "approval.dict(exclude_none=True)" .-> s6
    s1 -->|"_confirm_audit_metadata(payload)"| s7
    s7 -. "getattr (src/api/promotion.py:_confirm_audit_metadata)(payload.approval, field)" .-> s8
    s1 -. "(…).lower(data not statically known)" .-> s9
    s1 -->|"_verify_production_approval_signature(research_id, payload)"| s10
    s10 -->|"secret_value(settings.production_approval_verifier)"| s11
    s11 -. "isinstance (src/config.py:secret_value)(value, SecretStr)" .-> s12
    click s1 "../modules/promotion.md"
    click s2 "../modules/promotion.md"
    click s3 "../modules/promotion.md"
    click s7 "../modules/promotion.md"
    click s10 "../modules/promotion.md"
    click s11 "../modules/config.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `promote_confirm` | `request: Request`, `research_id: str`, `payload: PromotionScopeRequest \| None` | - | - | `_inject_target_kind(...)` |
| `PromotionScopeRequest` | - | - | - | - |
| `_approval_payload` | `approval: PromotionApproval \| None` | - | - | `None`, `approval.model_dump(...)`, `approval.dict(...)` |
| `hasattr` | - | - | - | - |
| `approval.model_dump (src/api/promotion.py:_approval_payload)` | - | - | - | - |
| `approval.dict` | - | - | - | - |
| `_confirm_audit_metadata` | `payload: PromotionScopeRequest` | `CANDIDATE_FIELDS` | `metadata[...]`, `metadata[...]`, `metadata[...]` | `metadata` |
| `getattr (src/api/promotion.py:_confirm_audit_metadata)` | - | - | - | - |
| `(…).lower` | - | - | - | - |
| `_verify_production_approval_signature` | `research_id: str`, `payload: PromotionScopeRequest` | `settings` | - | - |
| `secret_value` | `value: SecretStr \| str \| None` | `SecretStr` | - | `value.get_secret_value(...)`, `value` |
| `isinstance (src/config.py:secret_value)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| promote_confirm | PromotionScopeRequest | 377 | `PromotionScopeRequest(data not statically known)` |
| promote_confirm | _approval_payload | 378 | `_approval_payload(payload.approval)` |
| _approval_payload | hasattr | 198 | `hasattr(approval, 'model_dump')` |
| _approval_payload | approval.model_dump (src/api/promotion.py:_approval_payload) | 199 | `approval.model_dump(exclude_none=True)` |
| _approval_payload | approval.dict | 200 | `approval.dict(exclude_none=True)` |
| promote_confirm | _confirm_audit_metadata | 379 | `_confirm_audit_metadata(payload)` |
| _confirm_audit_metadata | getattr (src/api/promotion.py:_confirm_audit_metadata) | 252 | `getattr(payload.approval, field)` |
| promote_confirm | (…).lower | 384 | `(payload.scope or '').lower(data not statically known)` |
| promote_confirm | _verify_production_approval_signature | 385 | `_verify_production_approval_signature(research_id, payload)` |
| _verify_production_approval_signature | secret_value | 215 | `secret_value(settings.production_approval_verifier)` |
| secret_value | isinstance (src/config.py:secret_value) | 25 | `isinstance(value, SecretStr)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `_approval_payload` | `hasattr` | 198 |
| unresolved_call | `_approval_payload` | `approval.model_dump` | 199 |
| external_call | `_confirm_audit_metadata` | `getattr` | 252 |
| unresolved_call | `promote_confirm` | `(payload.scope or '').lower` | 384 |
| external_call | `secret_value` | `isinstance` | 25 |
| step_limit | `promote_confirm` | `first 12 steps` | 0 |

## Behavior

This flow starts at `promote_confirm` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
