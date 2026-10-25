# verify_run_spec

**Entry point:** `verify_run_spec` (`api`)
**Source:** [run_spec](../modules/run_spec.md)
**Modules touched:** [run_spec](../modules/run_spec.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as verify_run_spec
    participant p1 as spec.get
    participant p2 as isinstance
    participant p3 as hashlib.sha256(…).hexdigest
    participant p4 as hashlib.sha256
    participant p5 as canonical_spec_json(…).encode
    participant p6 as canonical_spec_json
    participant p7 as dict
    participant p8 as payload.pop
    participant p9 as json.dumps
    p0-->>p1: spec.get('spec_sha256')
    p0-->>p2: isinstance(recorded, str)
    p0-->>p3: hashlib.sha256(…).hexdigest
    p0-->>p4: hashlib.sha256(...)
    p0-->>p5: canonical_spec_json(…).encode('utf-8')
    p0->>p6: canonical_spec_json
    p6-->>p7: dict(spec)
    p6-->>p8: payload.pop('spec_sha256', None)
    p6-->>p9: json.dumps(payload, sort_keys=True, separators=(...))
```

> Call sequence diagram shows 9 of 9 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 4 of 4 (0 omitted); unresolved 4 of 4 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. verify_run_spec"]
    s2["2. spec.get"]
    s3["3. isinstance"]
    s4["4. hashlib.sha256(…).hexdigest"]
    s5["5. hashlib.sha256"]
    s6["6. canonical_spec_json(…).encode"]
    s7["7. canonical_spec_json"]
    s8["8. dict"]
    s9["9. payload.pop"]
    s10["10. json.dumps"]
    s1 -. "spec.get('spec_sha256')" .-> s2
    s1 -. "isinstance(recorded, str)" .-> s3
    s1 -. "hashlib.sha256(…).hexdigest(data not statically known)" .-> s4
    s1 -. "hashlib.sha256(...)" .-> s5
    s1 -. "canonical_spec_json(…).encode('utf-8')" .-> s6
    s1 -->|"canonical_spec_json(spec)"| s7
    s7 -. "dict(spec)" .-> s8
    s7 -. "payload.pop('spec_sha256', None)" .-> s9
    s7 -. "json.dumps(payload, sort_keys=True, separators=(...))" .-> s10
    b0["mutation payload.pop"]
    s7 -. "mutation payload.pop" .-> b0
    click s1 "../modules/run_spec.md"
    click s7 "../modules/run_spec.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `verify_run_spec` | `spec: Mapping[str, Any]` | - | - | `False`, `...` |
| `spec.get` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `hashlib.sha256(…).hexdigest` | - | - | - | - |
| `hashlib.sha256` | - | - | - | - |
| `canonical_spec_json(…).encode` | - | - | - | - |
| `canonical_spec_json` | `spec: Mapping[str, Any]` | - | - | `json.dumps(...)` |
| `dict` | - | - | - | - |
| `payload.pop` | - | - | - | - |
| `json.dumps` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| verify_run_spec | spec.get | 216 | `spec.get('spec_sha256')` |
| verify_run_spec | isinstance | 217 | `isinstance(recorded, str)` |
| verify_run_spec | hashlib.sha256(…).hexdigest | 219 | `hashlib.sha256(canonical_spec_json(spec).encode('utf-8')).hexdigest(data not statically known)` |
| verify_run_spec | hashlib.sha256 | 219 | `hashlib.sha256(...)` |
| verify_run_spec | canonical_spec_json(…).encode | 220 | `canonical_spec_json(spec).encode('utf-8')` |
| verify_run_spec | canonical_spec_json | 220 | `canonical_spec_json(spec)` |
| canonical_spec_json | dict | 138 | `dict(spec)` |
| canonical_spec_json | payload.pop | 139 | `payload.pop('spec_sha256', None)` |
| canonical_spec_json | json.dumps | 140 | `json.dumps(payload, sort_keys=True, separators=(...))` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `payload.pop` | `canonical_spec_json` | 139 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `verify_run_spec` | `spec.get` | 216 |
| external_call | `verify_run_spec` | `isinstance` | 217 |
| unresolved_call | `verify_run_spec` | `hashlib.sha256(canonical_spec_json(spec).encode('utf-8')).hexdigest` | 219 |
| external_call | `verify_run_spec` | `hashlib.sha256` | 219 |
| unresolved_call | `verify_run_spec` | `canonical_spec_json(spec).encode` | 220 |
| external_call | `canonical_spec_json` | `json.dumps` | 140 |

## Behavior

This flow starts at `verify_run_spec` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
