# reload_skills

**Entry point:** `reload_skills` (`http`)
**Source:** [src_api_skills](../modules/src_api_skills.md)
**Modules touched:** [audit](../modules/audit.md), [src_api_skills](../modules/src_api_skills.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as reload_skills
    participant p1 as _audit
    participant p2 as HTTPException
    participant p3 as _registry.reload_all
    participant p4 as _registry.available
    participant p5 as record_api_audit_event
    participant p6 as _request_actor
    participant p7 as store.record_audit_event
    participant p8 as request_metadata
    participant p9 as getattr
    participant p10 as isinstance
    participant p11 as request.headers.get
    participant p12 as metadata.update
    participant p13 as extra.items
    p0->>p1: _audit
    p0-->>p2: HTTPException(status_code=403, detail={...})
    p0-->>p3: _registry.reload_all
    p0->>p1: _audit
    p0-->>p4: _registry.available
    p0-->>p4: _registry.available
    p1->>p5: record_api_audit_event
    p5->>p6: _request_actor
    p5-->>p7: store.record_audit_event(…)
    p5->>p8: request_metadata
    p6-->>p9: getattr(request.state, 'auth_actor', None)
    p8->>p6: _request_actor
    p6-->>p10: isinstance(actor, AuthenticatedActor)
    p8-->>p11: request.headers.get('user-agent')
    p8-->>p12: metadata.update(...)
    p8-->>p13: extra.items
```

> Call sequence diagram shows 16 of 16 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 7 of 7 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. reload_skills"]
    s2["2. _audit"]
    s3["3. record_api_audit_event"]
    s4["4. _request_actor"]
    s5["5. getattr"]
    s6["6. isinstance"]
    s7["7. store.record_audit_event"]
    s8["8. request_metadata"]
    s9["9. _request_actor"]
    s10["10. request.headers.get"]
    s11["11. metadata.update"]
    s12["12. extra.items"]
    s1 -->|"_audit(request, action='skills.reload', outcome='denied', metadata={...}, error_message='skills.reload disabled in production')"| s2
    s2 -->|"record_api_audit_event(request, _store, action=action, outcome=outcome, metadata=metadata, error_message=error_message)"| s3
    s3 -->|"_request_actor(request)"| s4
    s4 -. "getattr(request.state, 'auth_actor', None)" .-> s5
    s4 -. "isinstance(actor, AuthenticatedActor)" .-> s6
    s3 -. "store.record_audit_event(…)" .-> s7
    s3 -->|"request_metadata(request, metadata)"| s8
    s8 -->|"_request_actor(request)"| s9
    s8 -. "request.headers.get('user-agent')" .-> s10
    s8 -. "metadata.update(...)" .-> s11
    s8 -. "extra.items(data not statically known)" .-> s12
    b0["mutation metadata.update"]
    s8 -. "mutation metadata.update" .-> b0
    click s1 "../modules/src_api_skills.md"
    click s2 "../modules/src_api_skills.md"
    click s3 "../modules/audit.md"
    click s4 "../modules/audit.md"
    click s8 "../modules/audit.md"
    click s9 "../modules/audit.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `reload_skills` | `request: Request` | `settings`, `settings`, `settings` | - | `{...}` |
| `_audit` | `request: Request`, `action: str`, `outcome: str`, `metadata: dict[str, Any] \| None`, `error_message: str \| None` | `_store`, `_store` | - | `None`, `...` |
| `record_api_audit_event` | `request: Request`, `store`, `action: str`, `outcome: str`, `research_id: str \| None`, `pipeline_id: str \| None`, `metadata: dict[str, Any] \| None`, `error_message: str \| None` | - | - | `...` |
| `_request_actor` | `request: Request` | `AuthenticatedActor` | - | `...` |
| `getattr` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `store.record_audit_event` | - | - | - | - |
| `request_metadata` | `request: Request`, `extra: dict[str, Any] \| None` | - | `metadata[...]`, `metadata[...]`, `metadata[...]`, `metadata[...]` | `metadata` |
| `_request_actor` | `request: Request` | `AuthenticatedActor` | - | `...` |
| `request.headers.get` | - | - | - | - |
| `metadata.update` | - | - | - | - |
| `extra.items` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| reload_skills | _audit | 405 | `_audit(request, action='skills.reload', outcome='denied', metadata={...}, error_message='skills.reload disabled in production')` |
| _audit | record_api_audit_event | 168 | `record_api_audit_event(request, _store, action=action, outcome=outcome, metadata=metadata, error_message=error_message)` |
| record_api_audit_event | _request_actor | 51 | `_request_actor(request)` |
| _request_actor | getattr | 13 | `getattr(request.state, 'auth_actor', None)` |
| _request_actor | isinstance | 14 | `isinstance(actor, AuthenticatedActor)` |
| record_api_audit_event | store.record_audit_event | 52 | `store.record_audit_event(actor_id=..., action=action, research_id=research_id, pipeline_id=pipeline_id, request_metadata=request_metadata(...), outcome=outcome, error_message=error_message)` |
| record_api_audit_event | request_metadata | 57 | `request_metadata(request, metadata)` |
| request_metadata | _request_actor | 20 | `_request_actor(request)` |
| request_metadata | request.headers.get | 27 | `request.headers.get('user-agent')` |
| request_metadata | metadata.update | 34 | `metadata.update(...)` |
| request_metadata | extra.items | 34 | `extra.items(data not statically known)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `metadata.update` | `request_metadata` | 34 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `_request_actor` | `getattr` | 13 |
| external_call | `_request_actor` | `isinstance` | 14 |
| unresolved_call | `record_api_audit_event` | `store.record_audit_event` | 52 |
| unresolved_call | `request_metadata` | `request.headers.get` | 27 |
| step_limit | `reload_skills` | `first 12 steps` | 0 |

## Behavior

This flow starts at `reload_skills` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
