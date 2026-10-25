# inspect_results

**Entry point:** `inspect_results` (`http`)
**Source:** [agent](../modules/agent.md)
**Modules touched:** [agent](../modules/agent.md), [config](../modules/config.md), [scoped_credentials](../modules/scoped_credentials.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as inspect_results
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
    participant p11 as HTTPException (src/api/agent.py:inspect_results)
    participant p12 as _store.get_iterations
    participant p13 as row.get
    participant p14 as _authority
    participant p15 as _router_auth
    participant p16 as credentials.scheme.lower
    participant p17 as HTTPException (src/api/agent.py:_require_agent)
    participant p18 as str (src/api/agent.py:_require_agent)
    participant p19 as time.time (src/api/agent.py:_check_rate_limit)
    participant p20 as time.time (src/core/scoped_credentia…y:verify_scoped_credential)
    participant p21 as _rate_buckets.setdefault
    participant p22 as str (src/core/scoped_credentia…y:verify_scoped_credential)
    participant p23 as len
    participant p24 as HTTPException (src/api/agent.py:_check_rate_limit)
    participant p25 as float
    participant p26 as window.append
    participant p27 as frozenset
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
    p0-->>p11: HTTPException (src/api/agent.py:inspect_results)(status_code=503, detail='store is not initialized')
    p0-->>p12: _store.get_iterations(run_id)
    p0-->>p13: row.get('iteration')
    p0-->>p13: row.get('metrics_json')
    p0-->>p14: _authority(row)
    p1-->>p15: _router_auth(request)
    p1-->>p16: credentials.scheme.lower
    p1-->>p17: HTTPException (src/api/agent.py:_require_agent)(status_code=401, detail='a run-scoped credential is required')
    p1-->>p17: HTTPException (src/api/agent.py:_require_agent)(status_code=403, detail=str(...))
    p1-->>p18: str (src/api/agent.py:_require_agent)(exc)
    p5-->>p19: time.time (src/api/agent.py:_check_rate_limit)
    p2-->>p20: time.time (src/core/scoped_credentia…y:verify_scoped_credential)
    p5-->>p21: _rate_buckets.setdefault(token_id, [...])
    p2-->>p22: str (src/core/scoped_credentia…y:verify_scoped_credential)(payload[...])
    p5-->>p23: len(window)
    p5-->>p24: HTTPException (src/api/agent.py:_check_rate_limit)(status_code=429, detail='rate limit exceeded for this credential')
    p2-->>p25: float(payload[...])
    p5-->>p26: window.append(now)
    p2-->>p27: frozenset(payload[...])
    p2-->>p27: frozenset(required_permissions)
```

> Call sequence diagram shows 30 of 50 interactions; 20 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 12 of 21 (9 omitted); unresolved 8 of 13 (5 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/scoped_credentials.py:_decode` | 7 | - | unresolved | 4 |
| `src/core/scoped_credentials.py:_decode` | 7 | [src/core/scoped_credentials.py](../modules/scoped_credentials.md) | internal | 4 |
| `src/core/scoped_credentials.py:_decode` | 7 | - | external | 3 |
| `src/core/scoped_credentials.py:verify_scoped_credential` | 6 | [src/core/scoped_credentials.py](../modules/scoped_credentials.md) | internal | 2 |
| `src/core/scoped_credentials.py:verify_scoped_credential` | 6 | - | external | 5 |
| `src/config.py:secret_value` | 36 | - | external | 1 |
| `src/config.py:secret_value` | 36 | - | unresolved | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. inspect_results"]
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
| `inspect_results` | `run_id: str`, `request: Request` | `PERM_READ`, `_store` | - | `{...}` |
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
| inspect_results | _require_agent | 279 | `_require_agent(request, run_id, PERM_READ)` |
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
| step_limit | `inspect_results` | `first 12 steps` | 0 |

## Behavior

This flow starts at `inspect_results` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
