# delete_research

**Entry point:** `delete_research` (`http`)
**Source:** [research](../modules/research.md)
**Modules touched:** [audit](../modules/audit.md), [research](../modules/research.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as delete_research
    participant p1 as _session_manager.is_running
    participant p2 as _audit
    participant p3 as HTTPException
    participant p4 as _store.get_session
    participant p5 as session.get
    participant p6 as _store.get_pipeline
    participant p7 as pipeline.get
    participant p8 as _store.delete_session
    participant p9 as record_api_audit_event
    participant p10 as _request_actor
    participant p11 as store.record_audit_event
    participant p12 as request_metadata
    participant p13 as getattr
    participant p14 as isinstance
    participant p15 as request.headers.get
    participant p16 as metadata.update
    participant p17 as extra.items
    p0-->>p1: _session_manager.is_running(research_id)
    p0->>p2: _audit
    p0-->>p3: HTTPException(status_code=409, detail='Cannot delete a running session — stop it first')
    p0-->>p4: _store.get_session(research_id)
    p0-->>p5: session.get('pipeline_id')
    p0-->>p6: _store.get_pipeline(pipeline_id)
    p0-->>p7: pipeline.get('status')
    p0-->>p3: HTTPException(status_code=409, detail=...)
    p0-->>p8: _store.delete_session(research_id)
    p0->>p2: _audit
    p0-->>p3: HTTPException(status_code=404, detail='Session not found')
    p0->>p2: _audit
    p2->>p9: record_api_audit_event
    p9->>p10: _request_actor
    p9-->>p11: store.record_audit_event(…)
    p9->>p12: request_metadata
    p10-->>p13: getattr(request.state, 'auth_actor', None)
    p12->>p10: _request_actor
    p10-->>p14: isinstance(actor, AuthenticatedActor)
    p12-->>p15: request.headers.get('user-agent')
    p12-->>p16: metadata.update(...)
    p12-->>p17: extra.items
```

> Call sequence diagram shows 22 of 22 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 5 of 5 (0 omitted); unresolved 10 of 10 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. delete_research"]
    s2["2. _session_manager.is_running"]
    s3["3. _audit"]
    s4["4. record_api_audit_event"]
    s5["5. _request_actor"]
    s6["6. getattr"]
    s7["7. isinstance"]
    s8["8. store.record_audit_event"]
    s9["9. request_metadata"]
    s10["10. _request_actor"]
    s11["11. request.headers.get"]
    s12["12. metadata.update"]
    s1 -. "_session_manager.is_running(research_id)" .-> s2
    s1 -->|"_audit(request, action='research.delete', outcome='failure', research_id=research_id, error_message='Cannot delete a running session — stop it first')"| s3
    s3 -->|"record_api_audit_event(…)"| s4
    s4 -->|"_request_actor(request)"| s5
    s5 -. "getattr(request.state, 'auth_actor', None)" .-> s6
    s5 -. "isinstance(actor, AuthenticatedActor)" .-> s7
    s4 -. "store.record_audit_event(…)" .-> s8
    s4 -->|"request_metadata(request, metadata)"| s9
    s9 -->|"_request_actor(request)"| s10
    s9 -. "request.headers.get('user-agent')" .-> s11
    s9 -. "metadata.update(...)" .-> s12
    b0["mutation metadata.update"]
    s9 -. "mutation metadata.update" .-> b0
    click s1 "../modules/research.md"
    click s3 "../modules/research.md"
    click s4 "../modules/audit.md"
    click s5 "../modules/audit.md"
    click s9 "../modules/audit.md"
    click s10 "../modules/audit.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `delete_research` | `request: Request`, `research_id: str` | - | - | `{...}` |
| `_session_manager.is_running` | - | - | - | - |
| `_audit` | `request: Request`, `action: str`, `outcome: str`, `research_id: str \| None`, `pipeline_id: str \| None`, `metadata: dict[str, Any] \| None`, `error_message: str \| None` | `_store` | - | `...` |
| `record_api_audit_event` | `request: Request`, `store`, `action: str`, `outcome: str`, `research_id: str \| None`, `pipeline_id: str \| None`, `metadata: dict[str, Any] \| None`, `error_message: str \| None` | - | - | `...` |
| `_request_actor` | `request: Request` | `AuthenticatedActor` | - | `...` |
| `getattr` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `store.record_audit_event` | - | - | - | - |
| `request_metadata` | `request: Request`, `extra: dict[str, Any] \| None` | - | `metadata[...]`, `metadata[...]`, `metadata[...]`, `metadata[...]` | `metadata` |
| `_request_actor` | `request: Request` | `AuthenticatedActor` | - | `...` |
| `request.headers.get` | - | - | - | - |
| `metadata.update` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| delete_research | _session_manager.is_running | 1044 | `_session_manager.is_running(research_id)` |
| delete_research | _audit | 1045 | `_audit(request, action='research.delete', outcome='failure', research_id=research_id, error_message='Cannot delete a running session — stop it first')` |
| _audit | record_api_audit_event | 109 | `record_api_audit_event(request, _store, action=action, outcome=outcome, research_id=research_id, pipeline_id=pipeline_id, metadata=metadata, error_message=error_message)` |
| record_api_audit_event | _request_actor | 51 | `_request_actor(request)` |
| _request_actor | getattr | 13 | `getattr(request.state, 'auth_actor', None)` |
| _request_actor | isinstance | 14 | `isinstance(actor, AuthenticatedActor)` |
| record_api_audit_event | store.record_audit_event | 52 | `store.record_audit_event(actor_id=..., action=action, research_id=research_id, pipeline_id=pipeline_id, request_metadata=request_metadata(...), outcome=outcome, error_message=error_message)` |
| record_api_audit_event | request_metadata | 57 | `request_metadata(request, metadata)` |
| request_metadata | _request_actor | 20 | `_request_actor(request)` |
| request_metadata | request.headers.get | 27 | `request.headers.get('user-agent')` |
| request_metadata | metadata.update | 34 | `metadata.update(...)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `metadata.update` | `request_metadata` | 34 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `delete_research` | `_session_manager.is_running` | 1044 |
| external_call | `_request_actor` | `getattr` | 13 |
| external_call | `_request_actor` | `isinstance` | 14 |
| unresolved_call | `record_api_audit_event` | `store.record_audit_event` | 52 |
| unresolved_call | `request_metadata` | `request.headers.get` | 27 |
| step_limit | `delete_research` | `first 12 steps` | 0 |

## Behavior

This flow starts at `delete_research` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
