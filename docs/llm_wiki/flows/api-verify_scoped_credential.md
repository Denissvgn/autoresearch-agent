# verify_scoped_credential

**Entry point:** `verify_scoped_credential` (`api`)
**Source:** [scoped_credentials](../modules/scoped_credentials.md)
**Modules touched:** [scoped_credentials](../modules/scoped_credentials.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as verify_scoped_credential
    participant p1 as _decode
    participant p2 as time.time
    participant p3 as str
    participant p4 as CredentialRevoked
    participant p5 as float
    participant p6 as CredentialExpired
    participant p7 as CredentialDenied
    participant p8 as frozenset
    participant p9 as sorted
    participant p10 as ScopedPrincipal
    participant p11 as token.rsplit
    participant p12 as hmac.new(…).hexdigest
    participant p13 as hmac.new
    participant p14 as key.encode
    participant p15 as body.encode
    participant p16 as hmac.compare_digest
    participant p17 as json.loads
    p0->>p1: _decode
    p0-->>p2: time.time
    p0-->>p3: str(payload[...])
    p0->>p4: CredentialRevoked
    p0-->>p5: float(payload[...])
    p0->>p6: CredentialExpired
    p0->>p7: CredentialDenied
    p0->>p7: CredentialDenied
    p0-->>p8: frozenset(payload[...])
    p0-->>p8: frozenset(required_permissions)
    p0->>p7: CredentialDenied
    p0-->>p9: sorted(missing)
    p0->>p10: ScopedPrincipal
    p0-->>p3: str(payload[...])
    p0-->>p3: str(payload[...])
    p0-->>p3: str(payload[...])
    p0-->>p5: float(payload[...])
    p1-->>p11: token.rsplit('.', 1)
    p1->>p7: CredentialDenied
    p1-->>p12: hmac.new(…).hexdigest
    p1-->>p13: hmac.new(key.encode(...), body.encode(...), hashlib.sha256)
    p1-->>p14: key.encode('utf-8')
    p1-->>p15: body.encode('utf-8')
    p1-->>p16: hmac.compare_digest(expected, signature)
    p1->>p7: CredentialDenied
    p1-->>p17: json.loads(body)
    p1->>p7: CredentialDenied
    p1->>p7: CredentialDenied
```

> Call sequence diagram shows 28 of 28 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 13 of 13 (0 omitted); unresolved 4 of 4 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. verify_scoped_credential"]
    s2["2. _decode"]
    s3["3. token.rsplit"]
    s4["4. CredentialDenied"]
    s5["5. hmac.new(…).hexdigest"]
    s6["6. hmac.new"]
    s7["7. key.encode"]
    s8["8. body.encode"]
    s9["9. hmac.compare_digest"]
    s10["10. CredentialDenied"]
    s11["11. json.loads"]
    s12["12. CredentialDenied"]
    s1 -->|"_decode(token, key)"| s2
    s2 -. "token.rsplit('.', 1)" .-> s3
    s2 -->|"CredentialDenied('malformed credential')"| s4
    s2 -. "hmac.new(…).hexdigest(data not statically known)" .-> s5
    s2 -. "hmac.new(key.encode(...), body.encode(...), hashlib.sha256)" .-> s6
    s2 -. "key.encode('utf-8')" .-> s7
    s2 -. "body.encode('utf-8')" .-> s8
    s2 -. "hmac.compare_digest(expected, signature)" .-> s9
    s2 -->|"CredentialDenied('credential signature is invalid')"| s10
    s2 -. "json.loads(body)" .-> s11
    s2 -->|"CredentialDenied('malformed credential')"| s12
    click s1 "../modules/scoped_credentials.md"
    click s2 "../modules/scoped_credentials.md"
    click s4 "../modules/scoped_credentials.md"
    click s10 "../modules/scoped_credentials.md"
    click s12 "../modules/scoped_credentials.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `verify_scoped_credential` | `token: str`, `key: str`, `run_id: Optional[str]`, `tenant_id: Optional[str]`, `required_permissions: Iterable[str]`, `now: Optional[float]` | `_REVOKED` | - | `ScopedPrincipal(...)` |
| `_decode` | `token: str`, `key: str` | `json` | - | `payload` |
| `token.rsplit` | - | - | - | - |
| `CredentialDenied` | - | - | - | - |
| `hmac.new(…).hexdigest` | - | - | - | - |
| `hmac.new` | - | - | - | - |
| `key.encode` | - | - | - | - |
| `body.encode` | - | - | - | - |
| `hmac.compare_digest` | - | - | - | - |
| `CredentialDenied` | - | - | - | - |
| `json.loads` | - | - | - | - |
| `CredentialDenied` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| verify_scoped_credential | _decode | 119 | `_decode(token, key)` |
| _decode | token.rsplit | 154 | `token.rsplit('.', 1)` |
| _decode | CredentialDenied | 156 | `CredentialDenied('malformed credential')` |
| _decode | hmac.new(…).hexdigest | 157 | `hmac.new(key.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest(data not statically known)` |
| _decode | hmac.new | 157 | `hmac.new(key.encode(...), body.encode(...), hashlib.sha256)` |
| _decode | key.encode | 158 | `key.encode('utf-8')` |
| _decode | body.encode | 158 | `body.encode('utf-8')` |
| _decode | hmac.compare_digest | 160 | `hmac.compare_digest(expected, signature)` |
| _decode | CredentialDenied | 161 | `CredentialDenied('credential signature is invalid')` |
| _decode | json.loads | 163 | `json.loads(body)` |
| _decode | CredentialDenied | 165 | `CredentialDenied('malformed credential')` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `_decode` | `token.rsplit` | 154 |
| unresolved_call | `_decode` | `hmac.new(key.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest` | 157 |
| external_call | `_decode` | `hmac.new` | 157 |
| unresolved_call | `_decode` | `key.encode` | 158 |
| unresolved_call | `_decode` | `body.encode` | 158 |
| external_call | `_decode` | `hmac.compare_digest` | 160 |
| external_call | `_decode` | `json.loads` | 163 |
| step_limit | `verify_scoped_credential` | `first 12 steps` | 0 |

## Behavior

This flow starts at `verify_scoped_credential` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
