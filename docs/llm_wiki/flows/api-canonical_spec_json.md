# canonical_spec_json

**Entry point:** `canonical_spec_json` (`api`)
**Source:** [run_spec](../modules/run_spec.md)
**Modules touched:** [run_spec](../modules/run_spec.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as canonical_spec_json
    participant p1 as dict
    participant p2 as payload.pop
    participant p3 as json.dumps
    p0-->>p1: dict(spec)
    p0-->>p2: payload.pop('spec_sha256', None)
    p0-->>p3: json.dumps(payload, sort_keys=True, separators=(...))
```

> Call sequence diagram shows 3 of 3 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 2 of 2 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. canonical_spec_json"]
    s2["2. dict"]
    s3["3. payload.pop"]
    s4["4. json.dumps"]
    s1 -. "dict(spec)" .-> s2
    s1 -. "payload.pop('spec_sha256', None)" .-> s3
    s1 -. "json.dumps(payload, sort_keys=True, separators=(...))" .-> s4
    b0["mutation payload.pop"]
    s1 -. "mutation payload.pop" .-> b0
    click s1 "../modules/run_spec.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `canonical_spec_json` | `spec: Mapping[str, Any]` | - | - | `json.dumps(...)` |
| `dict` | - | - | - | - |
| `payload.pop` | - | - | - | - |
| `json.dumps` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
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
| external_call | `canonical_spec_json` | `json.dumps` | 140 |

## Behavior

This flow starts at `canonical_spec_json` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
