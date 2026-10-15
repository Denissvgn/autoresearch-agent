# resume_research

**Entry point:** `resume_research` (`http`)
**Source:** [research](../modules/research.md)
**Modules touched:** [audit](../modules/audit.md), [research](../modules/research.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as resume_research
    participant p1 as _session_manager.resume_session
    participant p2 as _audit
    participant p3 as HTTPException
    participant p4 as record_api_audit_event
    participant p5 as _request_actor
    participant p6 as store.record_audit_event
    participant p7 as request_metadata
    participant p8 as getattr
    participant p9 as isinstance
    participant p10 as request.headers.get
    participant p11 as metadata.update
    participant p12 as extra.items
    p0-->>p1: _session_manager.resume_session(research_id)
    p0->>p2: _audit
    p0-->>p3: HTTPException(status_code=404, detail='Session not found or not running')
    p0->>p2: _audit
    p2->>p4: record_api_audit_event
    p4->>p5: _request_actor
    p4-->>p6: store.record_audit_event(…)
    p4->>p7: request_metadata
    p5-->>p8: getattr(request.state, 'auth_actor', None)
    p7->>p5: _request_actor
    p5-->>p9: isinstance(actor, AuthenticatedActor)
    p7-->>p10: request.headers.get('user-agent')
    p7-->>p11: metadata.update(...)
    p7-->>p12: extra.items
```

> Call sequence diagram shows 14 of 14 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 5 of 5 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. resume_research"]
    s2["2. _session_manager.resume_session"]
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
    s1 -. "_session_manager.resume_session(research_id)" .-> s2
    s1 -->|"_audit(request, action='research.resume', outcome='failure', research_id=research_id, error_message='Session not found or not running')"| s3
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
| `resume_research` | `request: Request`, `research_id: str` | - | - | `{...}` |
| `_session_manager.resume_session` | - | - | - | - |
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
| resume_research | _session_manager.resume_session | 873 | `_session_manager.resume_session(research_id)` |
| resume_research | _audit | 875 | `_audit(request, action='research.resume', outcome='failure', research_id=research_id, error_message='Session not found or not running')` |
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
| unresolved_call | `resume_research` | `_session_manager.resume_session` | 873 |
| external_call | `_request_actor` | `getattr` | 13 |
| external_call | `_request_actor` | `isinstance` | 14 |
| unresolved_call | `record_api_audit_event` | `store.record_audit_event` | 52 |
| unresolved_call | `request_metadata` | `request.headers.get` | 27 |
| step_limit | `resume_research` | `first 12 steps` | 0 |

## Behavior

This flow starts at `resume_research` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
