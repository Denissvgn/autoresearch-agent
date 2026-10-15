# promote_preview

**Entry point:** `promote_preview` (`http`)
**Source:** [promotion](../modules/promotion.md)
**Modules touched:** [audit](../modules/audit.md), [compat_legacy_alias](../modules/compat_legacy_alias.md), [config_promoter](../modules/config_promoter.md), [promotion](../modules/promotion.md), and 1 more

**Complete modules touched:**

- [audit](../modules/audit.md)
- [compat_legacy_alias](../modules/compat_legacy_alias.md)
- [config_promoter](../modules/config_promoter.md)
- [promotion](../modules/promotion.md)
- [promotion_target](../modules/promotion_target.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as promote_preview
    participant p1 as _promoter_for_session
    participant p2 as _audit
    participant p3 as _inject_target_kind
    participant p4 as PromotionPreviewRequest
    participant p5 as _approval_payload
    participant p6 as record_api_audit_event
    participant p7 as promotion_target_from_manifest
    participant p8 as request_metadata
    participant p9 as model_type_to_skill_id
    participant p10 as ConfigPromoter
    participant p11 as _request_actor
    participant p12 as FilePathPromotionTarget
    participant p13 as WebhookPromotionTarget
    participant p14 as str
    participant p15 as promoter.preview
    participant p16 as HTTPException
    participant p17 as hasattr
    participant p18 as _store.get_session
    participant p19 as isinstance (src/api/promotion.py:_inject_target_kind)
    participant p20 as approval.model_dump
    participant p21 as session.get
    participant p22 as result.get
    participant p23 as approval.dict
    p0->>p1: _promoter_for_session
    p0->>p2: _audit
    p0->>p3: _inject_target_kind
    p0->>p4: PromotionPreviewRequest
    p0->>p5: _approval_payload
    p2->>p6: record_api_audit_event
    p1->>p7: promotion_target_from_manifest
    p6->>p8: request_metadata
    p1->>p9: model_type_to_skill_id
    p1->>p10: ConfigPromoter
    p6->>p11: _request_actor
    p7->>p12: FilePathPromotionTarget
    p7->>p13: WebhookPromotionTarget
    p0-->>p14: str(e)
    p0-->>p15: promoter.preview(research_id, scope=payload.scope, approval=approval)
    p0-->>p16: HTTPException(status_code=404, detail=str(...))
    p0-->>p14: str(e)
    p0-->>p14: str(e)
    p0-->>p16: HTTPException(status_code=404, detail=str(...))
    p0-->>p14: str(e)
    p5-->>p17: hasattr(approval, 'model_dump')
    p1-->>p18: _store.get_session(research_id)
    p3-->>p19: isinstance (src/api/promotion.py:_inject_target_kind)(result, dict)
    p5-->>p20: approval.model_dump(exclude_none=True)
    p1-->>p21: session.get('skill_id')
    p3-->>p22: result.get('target_kind')
    p5-->>p23: approval.dict(exclude_none=True)
    p1-->>p21: session.get('model_type')
    p3-->>p22: result.get('skill_id')
    p3-->>p22: result.get('model_type')
```

> Call sequence diagram shows 30 of 60 interactions; 30 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 8 of 25 (17 omitted); unresolved 9 of 17 (8 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/compat/legacy_alias.py:model_type_to_skill_id` | 11 | - | unresolved | 1 |
| `src/api/promotion.py:_promoter_for_session` | 7 | - | unresolved | 1 |
| `src/core/promotion_target.py:promotion_target_from_manifest` | 14 | - | external | 14 |
| `src/core/promotion_target.py:promotion_target_from_manifest` | 14 | [src/core/promotion_target.py](../modules/promotion_target.md) | internal | 1 |
| `src/api/promotion.py:_promoter_for_session` | 7 | - | external | 1 |
| `src/api/audit.py:_request_actor` | 37 | - | external | 2 |
| `src/api/audit.py:record_api_audit_event` | 36 | - | unresolved | 1 |
| `src/api/audit.py:request_metadata` | 41 | [src/api/audit.py](../modules/audit.md) | internal | 1 |
> Omission summary shows 8 of 12 groups; 4 further groups are not expanded here. Counts above include all omitted interactions.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. promote_preview"]
    s2["2. PromotionPreviewRequest"]
    s3["3. _approval_payload"]
    s4["4. hasattr"]
    s5["5. approval.model_dump"]
    s6["6. approval.dict"]
    s7["7. _promoter_for_session"]
    s8["8. _store.get_session"]
    s9["9. session.get"]
    s10["10. session.get"]
    s11["11. model_type_to_skill_id"]
    s12["12. _MODEL_TYPE_TO_SKILL_ID.get"]
    s1 -->|"PromotionPreviewRequest(data not statically known)"| s2
    s1 -->|"_approval_payload(payload.approval)"| s3
    s3 -. "hasattr(approval, 'model_dump')" .-> s4
    s3 -. "approval.model_dump(exclude_none=True)" .-> s5
    s3 -. "approval.dict(exclude_none=True)" .-> s6
    s1 -->|"_promoter_for_session(research_id)"| s7
    s7 -. "_store.get_session(research_id)" .-> s8
    s7 -. "session.get('skill_id')" .-> s9
    s7 -. "session.get('model_type')" .-> s10
    s7 -->|"model_type_to_skill_id(model_type)"| s11
    s11 -. "_MODEL_TYPE_TO_SKILL_ID.get(model_type, model_type)" .-> s12
    click s1 "../modules/promotion.md"
    click s2 "../modules/promotion.md"
    click s3 "../modules/promotion.md"
    click s7 "../modules/promotion.md"
    click s11 "../modules/compat_legacy_alias.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `promote_preview` | `request: Request`, `research_id: str`, `payload: PromotionPreviewRequest \| None` | - | - | `_inject_target_kind(...)` |
| `PromotionPreviewRequest` | - | - | - | - |
| `_approval_payload` | `approval: PromotionApproval \| None` | - | - | `None`, `approval.model_dump(...)`, `approval.dict(...)` |
| `hasattr` | - | - | - | - |
| `approval.model_dump` | - | - | - | - |
| `approval.dict` | - | - | - | - |
| `_promoter_for_session` | `research_id: str` | `_registry`, `_store`, `_promoter`, `_promoter`, `_promoter`, `_promoter`, `_promoter`, `_promoter` | - | `(...)`, `(...)`, `(...)`, `(...)`, `(...)`, `(...)`, `(...)`, `(...)` |
| `_store.get_session` | - | - | - | - |
| `session.get` | - | - | - | - |
| `session.get` | - | - | - | - |
| `model_type_to_skill_id` | `model_type: str` | - | - | `''`, `_MODEL_TYPE_TO_SKILL_ID.get(...)` |
| `_MODEL_TYPE_TO_SKILL_ID.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| promote_preview | PromotionPreviewRequest | 314 | `PromotionPreviewRequest(data not statically known)` |
| promote_preview | _approval_payload | 315 | `_approval_payload(payload.approval)` |
| _approval_payload | hasattr | 187 | `hasattr(approval, 'model_dump')` |
| _approval_payload | approval.model_dump | 188 | `approval.model_dump(exclude_none=True)` |
| _approval_payload | approval.dict | 189 | `approval.dict(exclude_none=True)` |
| promote_preview | _promoter_for_session | 317 | `_promoter_for_session(research_id)` |
| _promoter_for_session | _store.get_session | 267 | `_store.get_session(research_id)` |
| _promoter_for_session | session.get | 272 | `session.get('skill_id')` |
| _promoter_for_session | session.get | 274 | `session.get('model_type')` |
| _promoter_for_session | model_type_to_skill_id | 278 | `model_type_to_skill_id(model_type)` |
| model_type_to_skill_id | _MODEL_TYPE_TO_SKILL_ID.get | 45 | `_MODEL_TYPE_TO_SKILL_ID.get(model_type, model_type)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `_approval_payload` | `hasattr` | 187 |
| unresolved_call | `_approval_payload` | `approval.model_dump` | 188 |
| unresolved_call | `_promoter_for_session` | `_store.get_session` | 267 |
| unresolved_call | `_promoter_for_session` | `session.get` | 272 |
| unresolved_call | `_promoter_for_session` | `session.get` | 274 |
| unresolved_call | `model_type_to_skill_id` | `_MODEL_TYPE_TO_SKILL_ID.get` | 45 |
| step_limit | `promote_preview` | `first 12 steps` | 0 |

## Behavior

This flow starts at `promote_preview` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
