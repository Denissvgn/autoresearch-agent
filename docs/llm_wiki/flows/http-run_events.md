# run_events

**Entry point:** `run_events` (`http`)
**Source:** [agent](../modules/agent.md)
**Modules touched:** [agent](../modules/agent.md), [config](../modules/config.md), [events](../modules/events.md), [scoped_credentials](../modules/scoped_credentials.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as run_events
    participant p1 as _require_agent
    participant p2 as poll_events
    participant p3 as verify_scoped_credential
    participant p4 as _key
    participant p5 as _decode
    participant p6 as _check_rate_limit
    participant p7 as secret_value
    participant p8 as CredentialRevoked
    participant p9 as CredentialExpired
    participant p10 as CredentialDenied
    participant p11 as ScopedPrincipal
    participant p12 as HTTPException (src/api/agent.py:run_events)
    participant p13 as events[…].get
    participant p14 as max
    participant p15 as min
    participant p16 as int (src/api/agent.py:run_events)
    participant p17 as event.get
    participant p18 as _router_auth
    participant p19 as store.list_events
    participant p20 as credentials.scheme.lower
    participant p21 as int (src/ws/events.py:poll_events)
    participant p22 as HTTPException (src/api/agent.py:_require_agent)
    participant p23 as str (src/api/agent.py:_require_agent)
    participant p24 as time.time (src/api/agent.py:_check_rate_limit)
    p0->>p1: _require_agent
    p0->>p2: poll_events
    p1->>p3: verify_scoped_credential
    p1->>p4: _key
    p3->>p5: _decode
    p1->>p6: _check_rate_limit
    p4->>p7: secret_value
    p3->>p8: CredentialRevoked
    p3->>p9: CredentialExpired
    p3->>p10: CredentialDenied
    p3->>p11: ScopedPrincipal
    p0-->>p12: HTTPException (src/api/agent.py:run_events)(status_code=503, detail='store is not initialized')
    p0-->>p13: events[…].get('sequence')
    p0-->>p14: max(1, min(...))
    p0-->>p15: min(limit, 500)
    p0-->>p16: int (src/api/agent.py:run_events)(...)
    p0-->>p16: int (src/api/agent.py:run_events)(cursor)
    p0-->>p17: event.get('event_id')
    p0-->>p17: event.get('event_type')
    p0-->>p17: event.get('sequence')
    p0-->>p17: event.get('payload')
    p1-->>p18: _router_auth(request)
    p2-->>p19: store.list_events(stream_key=stream_key, after_sequence=int(...), limit=int(...))
    p1-->>p20: credentials.scheme.lower
    p2-->>p21: int (src/ws/events.py:poll_events)(cursor)
    p1-->>p22: HTTPException (src/api/agent.py:_require_agent)(status_code=401, detail='a run-scoped credential is required')
    p2-->>p21: int (src/ws/events.py:poll_events)(limit)
    p1-->>p22: HTTPException (src/api/agent.py:_require_agent)(status_code=403, detail=str(...))
    p1-->>p23: str (src/api/agent.py:_require_agent)(exc)
    p6-->>p24: time.time (src/api/agent.py:_check_rate_limit)
```

> Call sequence diagram shows 30 of 59 interactions; 29 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 11 of 27 (16 omitted); unresolved 8 of 15 (7 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/scoped_credentials.py:_decode` | 7 | - | unresolved | 4 |
| `src/core/scoped_credentials.py:_decode` | 7 | [src/core/scoped_credentials.py](../modules/scoped_credentials.md) | internal | 4 |
| `src/core/scoped_credentials.py:_decode` | 7 | - | external | 3 |
| `src/core/scoped_credentials.py:verify_scoped_credential` | 6 | - | external | 10 |
| `src/core/scoped_credentials.py:verify_scoped_credential` | 6 | [src/core/scoped_credentials.py](../modules/scoped_credentials.md) | internal | 2 |
| `src/config.py:secret_value` | 36 | - | external | 1 |
| `src/config.py:secret_value` | 36 | - | unresolved | 1 |
| `src/api/agent.py:_check_rate_limit` | 41 | - | unresolved | 2 |
> Omission summary shows 8 of 9 groups; 1 further groups are not expanded here. Counts above include all omitted interactions.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. run_events"]
    s2["2. _require_agent"]
    s3["3. _router_auth"]
    s4["4. credentials.scheme.lower"]
    s5["5. HTTPException (src/api/agent.py:_require_agent)"]
    s6["6. verify_scoped_credential"]
    s7["7. _decode"]
    s8["8. token.rsplit"]
    s9["9. CredentialDenied"]
    s10["10. hmac.new(…).hexdigest"]
    s11["11. hmac.new"]
    s12["12. key.encode"]
    s1 -->|"_require_agent(request, run_id, PERM_READ)"| s2
    s2 -. "_router_auth(request)" .-> s3
    s2 -. "credentials.scheme.lower(data not statically known)" .-> s4
    s2 -. "HTTPException (src/api/agent.py:_require_agent)(status_code=401, detail='a run-scoped credential is required')" .-> s5
    s2 -->|"verify_scoped_credential(credentials.credentials, key=_key(...), run_id=run_id, required_permissions=(...))"| s6
    s6 -->|"_decode(token, key)"| s7
    s7 -. "token.rsplit('.', 1)" .-> s8
    s7 -->|"CredentialDenied('malformed credential')"| s9
    s7 -. "hmac.new(…).hexdigest(data not statically known)" .-> s10
    s7 -. "hmac.new(key.encode(...), body.encode(...), hashlib.sha256)" .-> s11
    s7 -. "key.encode('utf-8')" .-> s12
    click s1 "../modules/agent.md"
    click s2 "../modules/agent.md"
    click s6 "../modules/scoped_credentials.md"
    click s7 "../modules/scoped_credentials.md"
    click s9 "../modules/scoped_credentials.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `run_events` | `run_id: str`, `request: Request`, `cursor: int`, `limit: int` | `PERM_READ`, `_store`, `_store` | - | `{...}` |
| `_require_agent` | `request: Request`, `run_id: Optional[str]`, `permission: str` | `ScopedAuthError` | - | `principal` |
| `_router_auth` | - | - | - | - |
| `credentials.scheme.lower` | - | - | - | - |
| `HTTPException (src/api/agent.py:_require_agent)` | - | - | - | - |
| `verify_scoped_credential` | `token: str`, `key: str`, `run_id: Optional[str]`, `tenant_id: Optional[str]`, `required_permissions: Iterable[str]`, `now: Optional[float]` | `_REVOKED` | - | `ScopedPrincipal(...)` |
| `_decode` | `token: str`, `key: str` | `json` | - | `payload` |
| `token.rsplit` | - | - | - | - |
| `CredentialDenied` | - | - | - | - |
| `hmac.new(…).hexdigest` | - | - | - | - |
| `hmac.new` | - | - | - | - |
| `key.encode` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| run_events | _require_agent | 373 | `_require_agent(request, run_id, PERM_READ)` |
| _require_agent | _router_auth | 80 | `_router_auth(request)` |
| _require_agent | credentials.scheme.lower | 83 | `credentials.scheme.lower(data not statically known)` |
| _require_agent | HTTPException (src/api/agent.py:_require_agent) | 84 | `HTTPException(status_code=401, detail='a run-scoped credential is required')` |
| _require_agent | verify_scoped_credential | 89 | `scoped.verify_scoped_credential(credentials.credentials, key=_key(...), run_id=run_id, required_permissions=(...))` |
| verify_scoped_credential | _decode | 119 | `_decode(token, key)` |
| _decode | token.rsplit | 154 | `token.rsplit('.', 1)` |
| _decode | CredentialDenied | 156 | `CredentialDenied('malformed credential')` |
| _decode | hmac.new(…).hexdigest | 157 | `hmac.new(key.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest(data not statically known)` |
| _decode | hmac.new | 157 | `hmac.new(key.encode(...), body.encode(...), hashlib.sha256)` |
| _decode | key.encode | 158 | `key.encode('utf-8')` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `_require_agent` | `_router_auth` | 80 |
| unresolved_call | `_require_agent` | `credentials.scheme.lower` | 83 |
| external_call | `_require_agent` | `HTTPException` | 84 |
| unresolved_call | `_decode` | `token.rsplit` | 154 |
| unresolved_call | `_decode` | `hmac.new(key.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest` | 157 |
| external_call | `_decode` | `hmac.new` | 157 |
| unresolved_call | `_decode` | `key.encode` | 158 |
| step_limit | `run_events` | `first 12 steps` | 0 |

## Behavior

This flow starts at `run_events` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
