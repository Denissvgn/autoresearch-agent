# lifecycle_control

**Entry point:** `lifecycle_control` (`http`)
**Source:** [agent](../modules/agent.md)
**Modules touched:** [agent](../modules/agent.md), [config](../modules/config.md), [scoped_credentials](../modules/scoped_credentials.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as lifecycle_control
    participant p1 as _require_agent
    participant p2 as verify_scoped_credential
    participant p3 as _key
    participant p4 as _decode
    participant p5 as _check_rate_limit
    participant p6 as secret_value
    participant p7 as CredentialRevoked
    participant p8 as CredentialExpired
    participant p9 as CredentialDenied
    participant p10 as ScopedPrincipal
    participant p11 as HTTPException (src/api/agent.py:lifecycle_control)
    participant p12 as handler
    participant p13 as _router_auth
    participant p14 as credentials.scheme.lower
    participant p15 as HTTPException (src/api/agent.py:_require_agent)
    participant p16 as str (src/api/agent.py:_require_agent)
    participant p17 as time.time (src/api/agent.py:_check_rate_limit)
    participant p18 as time.time (src/core/scoped_credentia…y:verify_scoped_credential)
    participant p19 as _rate_buckets.setdefault
    participant p20 as str (src/core/scoped_credentia…y:verify_scoped_credential)
    participant p21 as len
    participant p22 as HTTPException (src/api/agent.py:_check_rate_limit)
    participant p23 as float
    participant p24 as window.append
    participant p25 as frozenset
    participant p26 as sorted
    p0->>p1: _require_agent
    p1->>p2: verify_scoped_credential
    p1->>p3: _key
    p2->>p4: _decode
    p1->>p5: _check_rate_limit
    p3->>p6: secret_value
    p2->>p7: CredentialRevoked
    p2->>p8: CredentialExpired
    p2->>p9: CredentialDenied
    p2->>p10: ScopedPrincipal
    p0-->>p11: HTTPException (src/api/agent.py:lifecycle_control)(status_code=400, detail='action must be pause, resume, or stop')
    p0-->>p12: handler(run_id)
    p0-->>p11: HTTPException (src/api/agent.py:lifecycle_control)(status_code=503, detail='lifecycle control is not initialized')
    p1-->>p13: _router_auth(request)
    p1-->>p14: credentials.scheme.lower
    p1-->>p15: HTTPException (src/api/agent.py:_require_agent)(status_code=401, detail='a run-scoped credential is required')
    p1-->>p15: HTTPException (src/api/agent.py:_require_agent)(status_code=403, detail=str(...))
    p1-->>p16: str (src/api/agent.py:_require_agent)(exc)
    p5-->>p17: time.time (src/api/agent.py:_check_rate_limit)
    p2-->>p18: time.time (src/core/scoped_credentia…y:verify_scoped_credential)
    p5-->>p19: _rate_buckets.setdefault(token_id, [...])
    p2-->>p20: str (src/core/scoped_credentia…y:verify_scoped_credential)(payload[...])
    p5-->>p21: len(window)
    p5-->>p22: HTTPException (src/api/agent.py:_check_rate_limit)(status_code=429, detail='rate limit exceeded for this credential')
    p2-->>p23: float(payload[...])
    p5-->>p24: window.append(now)
    p2-->>p25: frozenset(payload[...])
    p2-->>p25: frozenset(required_permissions)
    p2-->>p26: sorted(missing)
    p2-->>p20: str (src/core/scoped_credentia…y:verify_scoped_credential)(payload[...])
```

> Call sequence diagram shows 30 of 48 interactions; 18 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 15 of 22 (7 omitted); unresolved 5 of 10 (5 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/scoped_credentials.py:_decode` | 7 | - | unresolved | 4 |
| `src/core/scoped_credentials.py:_decode` | 7 | [src/core/scoped_credentials.py](../modules/scoped_credentials.md) | internal | 4 |
| `src/core/scoped_credentials.py:_decode` | 7 | - | external | 3 |
| `src/core/scoped_credentials.py:verify_scoped_credential` | 6 | [src/core/scoped_credentials.py](../modules/scoped_credentials.md) | internal | 2 |
| `src/core/scoped_credentials.py:verify_scoped_credential` | 6 | - | external | 3 |
| `src/config.py:secret_value` | 36 | - | external | 1 |
| `src/config.py:secret_value` | 36 | - | unresolved | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. lifecycle_control"]
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
    s1 -->|"_require_agent(request, run_id, PERM_LIFECYCLE)"| s2
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
| `lifecycle_control` | `run_id: str`, `body: LifecycleRequest`, `request: Request` | `PERM_LIFECYCLE`, `_orchestrator`, `_orchestrator`, `_orchestrator`, `_orchestrator` | - | `{...}` |
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
| lifecycle_control | _require_agent | 318 | `_require_agent(request, run_id, PERM_LIFECYCLE)` |
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
| step_limit | `lifecycle_control` | `first 12 steps` | 0 |

## Behavior

This flow starts at `lifecycle_control` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
