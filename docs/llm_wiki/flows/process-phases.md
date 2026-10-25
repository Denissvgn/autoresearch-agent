# phases

**Entry point:** `main` (`process`)
**Source:** [phases](../modules/phases.md)
**Modules touched:** [phases](../modules/phases.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as json.load
    participant p2 as payload.get
    participant p3 as bool
    participant p4 as evidence.get
    participant p5 as len
    participant p6 as max
    participant p7 as min
    participant p8 as print
    participant p9 as json.dumps
    p0-->>p1: json.load(sys.stdin)
    p0-->>p2: payload.get('evidence')
    p0-->>p3: bool(payload.get(...))
    p0-->>p2: payload.get('declarative_share')
    p0-->>p4: evidence.get('trend')
    p0-->>p3: bool(evidence.get(...))
    p0-->>p4: evidence.get('converged_early')
    p0-->>p5: len(history)
    p0-->>p6: max(...)
    p0-->>p7: min(...)
    p0-->>p8: print(json.dumps(...))
    p0-->>p9: json.dumps({...})
```

> Call sequence diagram shows 12 of 12 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 8 of 8 (0 omitted); unresolved 4 of 4 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. json.load"]
    s3["3. payload.get"]
    s4["4. bool"]
    s5["5. payload.get"]
    s6["6. evidence.get"]
    s7["7. bool"]
    s8["8. evidence.get"]
    s9["9. len"]
    s10["10. max"]
    s11["11. min"]
    s12["12. print"]
    s1 -. "json.load(sys.stdin)" .-> s2
    s1 -. "payload.get('evidence')" .-> s3
    s1 -. "bool(payload.get(...))" .-> s4
    s1 -. "payload.get('declarative_share')" .-> s5
    s1 -. "evidence.get('trend')" .-> s6
    s1 -. "bool(evidence.get(...))" .-> s7
    s1 -. "evidence.get('converged_early')" .-> s8
    s1 -. "len(history)" .-> s9
    s1 -. "max(...)" .-> s10
    s1 -. "min(...)" .-> s11
    s1 -. "print(json.dumps(...))" .-> s12
    b0["filesystem_read json.load"]
    s1 -. "filesystem_read json.load" .-> b0
    b1["output print"]
    s1 -. "output print" .-> b1
    click s1 "../modules/phases.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | - | `sys`, `SCHEMA` | - | - |
| `json.load` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `bool` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `evidence.get` | - | - | - | - |
| `bool` | - | - | - | - |
| `evidence.get` | - | - | - | - |
| `len` | - | - | - | - |
| `max` | - | - | - | - |
| `min` | - | - | - | - |
| `print` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | json.load | 16 | `json.load(sys.stdin)` |
| main | payload.get | 17 | `payload.get('evidence')` |
| main | bool | 18 | `bool(payload.get(...))` |
| main | payload.get | 18 | `payload.get('declarative_share')` |
| main | evidence.get | 19 | `evidence.get('trend')` |
| main | bool | 21 | `bool(evidence.get(...))` |
| main | evidence.get | 21 | `evidence.get('converged_early')` |
| main | len | 22 | `len(history)` |
| main | max | 22 | `max(...)` |
| main | min | 22 | `min(...)` |
| main | print | 28 | `print(json.dumps(...))` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_read | `json.load` | `main` | 16 |
| output | `print` | `main` | 28 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `main` | `payload.get` | 17 |
| unresolved_call | `main` | `payload.get` | 18 |
| unresolved_call | `main` | `evidence.get` | 19 |
| unresolved_call | `main` | `evidence.get` | 21 |
| external_call | `main` | `max` | 22 |
| external_call | `main` | `min` | 22 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
