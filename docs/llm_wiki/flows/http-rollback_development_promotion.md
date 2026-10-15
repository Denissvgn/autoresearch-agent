# rollback_development_promotion

**Entry point:** `rollback_development_promotion` (`http`)
**Source:** [promotion](../modules/promotion.md)
**Modules touched:** [audit](../modules/audit.md), [promotion](../modules/promotion.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as rollback_development_promotion
    participant p1 as PromotionRollbackRequest
    participant p2 as _promoter.rollback
    participant p3 as _audit
    participant p4 as str
    participant p5 as HTTPException
    participant p6 as record_api_audit_event
    participant p7 as _request_actor
    participant p8 as store.record_audit_event
    participant p9 as request_metadata
    participant p10 as getattr
    participant p11 as isinstance
    participant p12 as request.headers.get
    participant p13 as metadata.update
    participant p14 as extra.items
    p0->>p1: PromotionRollbackRequest
    p0-->>p2: _promoter.rollback(model_type=model_type, instrument=instrument, timeframe=timeframe, reason=request.reason)
    p0->>p3: _audit
    p0->>p3: _audit
    p0-->>p4: str(e)
    p0-->>p5: HTTPException(status_code=400, detail=str(...))
    p0-->>p4: str(e)
    p3->>p6: record_api_audit_event
    p6->>p7: _request_actor
    p6-->>p8: store.record_audit_event(…)
    p6->>p9: request_metadata
    p7-->>p10: getattr(request.state, 'auth_actor', None)
    p9->>p7: _request_actor
    p7-->>p11: isinstance(actor, AuthenticatedActor)
    p9-->>p12: request.headers.get('user-agent')
    p9-->>p13: metadata.update(...)
    p9-->>p14: extra.items
```

> Call sequence diagram shows 17 of 17 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 5 of 5 (0 omitted); unresolved 5 of 5 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. rollback_development_promotion"]
    s2["2. PromotionRollbackRequest"]
    s3["3. _promoter.rollback"]
    s4["4. _audit"]
    s5["5. record_api_audit_event"]
    s6["6. _request_actor"]
    s7["7. getattr"]
    s8["8. isinstance"]
    s9["9. store.record_audit_event"]
    s10["10. request_metadata"]
    s11["11. _request_actor"]
    s12["12. request.headers.get"]
    s1 -->|"PromotionRollbackRequest(data not statically known)"| s2
    s1 -. "_promoter.rollback(model_type=model_type, instrument=instrument, timeframe=timeframe, reason=request.reason)" .-> s3
    s1 -->|"_audit(http_request, action='promotion.rollback', outcome='success', metadata=metadata)"| s4
    s4 -->|"record_api_audit_event(request, _store, action=action, outcome=outcome, research_id=research_id, metadata=metadata, error_message=error_message)"| s5
    s5 -->|"_request_actor(request)"| s6
    s6 -. "getattr(request.state, 'auth_actor', None)" .-> s7
    s6 -. "isinstance(actor, AuthenticatedActor)" .-> s8
    s5 -. "store.record_audit_event(…)" .-> s9
    s5 -->|"request_metadata(request, metadata)"| s10
    s10 -->|"_request_actor(request)"| s11
    s10 -. "request.headers.get('user-agent')" .-> s12
    b0["mutation metadata.update"]
    s10 -. "mutation metadata.update" .-> b0
    click s1 "../modules/promotion.md"
    click s2 "../modules/promotion.md"
    click s4 "../modules/promotion.md"
    click s5 "../modules/audit.md"
    click s6 "../modules/audit.md"
    click s10 "../modules/audit.md"
    click s11 "../modules/audit.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `rollback_development_promotion` | `http_request: Request`, `model_type: str`, `instrument: str`, `timeframe: str`, `request: PromotionRollbackRequest` | - | - | `result` |
| `PromotionRollbackRequest` | - | - | - | - |
| `_promoter.rollback` | - | - | - | - |
| `_audit` | `request: Request`, `action: str`, `outcome: str`, `research_id: str \| None`, `metadata: dict \| None`, `error_message: str \| None` | `_store` | - | `...` |
| `record_api_audit_event` | `request: Request`, `store`, `action: str`, `outcome: str`, `research_id: str \| None`, `pipeline_id: str \| None`, `metadata: dict[str, Any] \| None`, `error_message: str \| None` | - | - | `...` |
| `_request_actor` | `request: Request` | `AuthenticatedActor` | - | `...` |
| `getattr` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `store.record_audit_event` | - | - | - | - |
| `request_metadata` | `request: Request`, `extra: dict[str, Any] \| None` | - | `metadata[...]`, `metadata[...]`, `metadata[...]`, `metadata[...]` | `metadata` |
| `_request_actor` | `request: Request` | `AuthenticatedActor` | - | `...` |
| `request.headers.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| rollback_development_promotion | PromotionRollbackRequest | 436 | `PromotionRollbackRequest(data not statically known)` |
| rollback_development_promotion | _promoter.rollback | 444 | `_promoter.rollback(model_type=model_type, instrument=instrument, timeframe=timeframe, reason=request.reason)` |
| rollback_development_promotion | _audit | 450 | `_audit(http_request, action='promotion.rollback', outcome='success', metadata=metadata)` |
| _audit | record_api_audit_event | 64 | `record_api_audit_event(request, _store, action=action, outcome=outcome, research_id=research_id, metadata=metadata, error_message=error_message)` |
| record_api_audit_event | _request_actor | 51 | `_request_actor(request)` |
| _request_actor | getattr | 13 | `getattr(request.state, 'auth_actor', None)` |
| _request_actor | isinstance | 14 | `isinstance(actor, AuthenticatedActor)` |
| record_api_audit_event | store.record_audit_event | 52 | `store.record_audit_event(actor_id=..., action=action, research_id=research_id, pipeline_id=pipeline_id, request_metadata=request_metadata(...), outcome=outcome, error_message=error_message)` |
| record_api_audit_event | request_metadata | 57 | `request_metadata(request, metadata)` |
| request_metadata | _request_actor | 20 | `_request_actor(request)` |
| request_metadata | request.headers.get | 27 | `request.headers.get('user-agent')` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `metadata.update` | `request_metadata` | 34 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `rollback_development_promotion` | `_promoter.rollback` | 444 |
| external_call | `_request_actor` | `getattr` | 13 |
| external_call | `_request_actor` | `isinstance` | 14 |
| unresolved_call | `record_api_audit_event` | `store.record_audit_event` | 52 |
| unresolved_call | `request_metadata` | `request.headers.get` | 27 |
| step_limit | `rollback_development_promotion` | `first 12 steps` | 0 |

## Behavior

This flow starts at `rollback_development_promotion` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
