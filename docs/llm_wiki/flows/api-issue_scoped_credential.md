# issue_scoped_credential

**Entry point:** `issue_scoped_credential` (`api`)
**Source:** [scoped_credentials](../modules/scoped_credentials.md)
**Modules touched:** [scoped_credentials](../modules/scoped_credentials.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as issue_scoped_credential
    participant p1 as frozenset
    participant p2 as CredentialDenied
    participant p3 as sorted
    participant p4 as time.time
    participant p5 as secrets.token_hex
    participant p6 as _encode
    participant p7 as json.dumps
    participant p8 as hmac.new(…).hexdigest
    participant p9 as hmac.new
    participant p10 as key.encode
    participant p11 as body.encode
    p0-->>p1: frozenset(permissions)
    p0->>p2: CredentialDenied
    p0-->>p3: sorted(illegal)
    p0->>p2: CredentialDenied
    p0-->>p3: sorted(unknown)
    p0-->>p4: time.time
    p0-->>p5: secrets.token_hex(8)
    p0-->>p3: sorted(granted)
    p0->>p6: _encode
    p6-->>p7: json.dumps(payload, sort_keys=True, separators=(...))
    p6-->>p8: hmac.new(…).hexdigest
    p6-->>p9: hmac.new(key.encode(...), body.encode(...), hashlib.sha256)
    p6-->>p10: key.encode('utf-8')
    p6-->>p11: body.encode('utf-8')
```

> Call sequence diagram shows 14 of 14 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 8 of 8 (0 omitted); unresolved 3 of 3 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. issue_scoped_credential"]
    s2["2. frozenset"]
    s3["3. CredentialDenied"]
    s4["4. sorted"]
    s5["5. CredentialDenied"]
    s6["6. sorted"]
    s7["7. time.time"]
    s8["8. secrets.token_hex"]
    s9["9. sorted"]
    s10["10. _encode"]
    s11["11. json.dumps"]
    s12["12. hmac.new(…).hexdigest"]
    s1 -. "frozenset(permissions)" .-> s2
    s1 -->|"CredentialDenied(...)"| s3
    s1 -. "sorted(illegal)" .-> s4
    s1 -->|"CredentialDenied(...)"| s5
    s1 -. "sorted(unknown)" .-> s6
    s1 -. "time.time(data not statically known)" .-> s7
    s1 -. "secrets.token_hex(8)" .-> s8
    s1 -. "sorted(granted)" .-> s9
    s1 -->|"_encode(payload, key)"| s10
    s10 -. "json.dumps(payload, sort_keys=True, separators=(...))" .-> s11
    s10 -. "hmac.new(…).hexdigest(data not statically known)" .-> s12
    click s1 "../modules/scoped_credentials.md"
    click s3 "../modules/scoped_credentials.md"
    click s5 "../modules/scoped_credentials.md"
    click s10 "../modules/scoped_credentials.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `issue_scoped_credential` | `subject: str`, `run_id: str`, `tenant_id: str`, `permissions: Iterable[str]`, `ttl_s: float`, `key: str`, `now: Optional[float]` | `NON_GRANTABLE_PERMISSIONS`, `SCOPED_PERMISSIONS` | - | `_encode(...)` |
| `frozenset` | - | - | - | - |
| `CredentialDenied` | - | - | - | - |
| `sorted` | - | - | - | - |
| `CredentialDenied` | - | - | - | - |
| `sorted` | - | - | - | - |
| `time.time` | - | - | - | - |
| `secrets.token_hex` | - | - | - | - |
| `sorted` | - | - | - | - |
| `_encode` | `payload: Mapping[str, Any]`, `key: str` | - | - | `...` |
| `json.dumps` | - | - | - | - |
| `hmac.new(…).hexdigest` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| issue_scoped_credential | frozenset | 79 | `frozenset(permissions)` |
| issue_scoped_credential | CredentialDenied | 82 | `CredentialDenied(...)` |
| issue_scoped_credential | sorted | 83 | `sorted(illegal)` |
| issue_scoped_credential | CredentialDenied | 87 | `CredentialDenied(...)` |
| issue_scoped_credential | sorted | 87 | `sorted(unknown)` |
| issue_scoped_credential | time.time | 88 | `time.time(data not statically known)` |
| issue_scoped_credential | secrets.token_hex | 90 | `secrets.token_hex(8)` |
| issue_scoped_credential | sorted | 94 | `sorted(granted)` |
| issue_scoped_credential | _encode | 98 | `_encode(payload, key)` |
| _encode | json.dumps | 145 | `json.dumps(payload, sort_keys=True, separators=(...))` |
| _encode | hmac.new(…).hexdigest | 146 | `hmac.new(key.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest(data not statically known)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `issue_scoped_credential` | `frozenset` | 79 |
| external_call | `issue_scoped_credential` | `sorted` | 83 |
| external_call | `issue_scoped_credential` | `sorted` | 87 |
| external_call | `issue_scoped_credential` | `time.time` | 88 |
| external_call | `issue_scoped_credential` | `secrets.token_hex` | 90 |
| external_call | `issue_scoped_credential` | `sorted` | 94 |
| external_call | `_encode` | `json.dumps` | 145 |
| unresolved_call | `_encode` | `hmac.new(key.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest` | 146 |
| step_limit | `issue_scoped_credential` | `first 12 steps` | 0 |

## Behavior

This flow starts at `issue_scoped_credential` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
