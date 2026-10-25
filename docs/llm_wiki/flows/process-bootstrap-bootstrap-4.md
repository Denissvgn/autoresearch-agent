# bootstrap

**Entry point:** `main` (`process`)
**Source:** [conformance_bootstrap](../modules/conformance_bootstrap.md)
**Modules touched:** [conformance_bootstrap](../modules/conformance_bootstrap.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as json.load
    participant p2 as json.dump
    participant p3 as Path
    participant p4 as payload.get
    participant p5 as str
    participant p6 as params.get
    participant p7 as isinstance
    participant p8 as ws.mkdir
    participant p9 as (…).write_text (tests/fixtures/conformance/bootstrap.py:main, 1)
    participant p10 as (…).write_text (tests/fixtures/conformance/bootstrap.py:main)
    p0-->>p1: json.load(sys.stdin)
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p3: Path(...)
    p0-->>p4: payload.get('workspace')
    p0-->>p5: str(ws)
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p4: payload.get('skill_params')
    p0-->>p6: params.get('input_file')
    p0-->>p7: isinstance(name, str)
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p4: payload.get('mode', 'live')
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p8: ws.mkdir(parents=True, exist_ok=True)
    p0-->>p9: (…).write_text (tests/fixtures/conformance/bootstrap.py:main, 1)('conformance input\n', encoding='utf-8')
    p0-->>p10: (…).write_text (tests/fixtures/conformance/bootstrap.py:main)('metric: 0.0\n', encoding='utf-8')
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p5: str(ws)
```

> Call sequence diagram shows 17 of 17 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 10 of 10 (0 omitted); unresolved 7 of 7 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. json.load"]
    s3["3. json.dump"]
    s4["4. Path"]
    s5["5. payload.get"]
    s6["6. str"]
    s7["7. json.dump"]
    s8["8. payload.get"]
    s9["9. params.get"]
    s10["10. isinstance"]
    s11["11. json.dump"]
    s12["12. payload.get"]
    s1 -. "json.load(sys.stdin)" .-> s2
    s1 -. "json.dump({...}, sys.stdout)" .-> s3
    s1 -. "Path(...)" .-> s4
    s1 -. "payload.get('workspace')" .-> s5
    s1 -. "str(ws)" .-> s6
    s1 -. "json.dump({...}, sys.stdout)" .-> s7
    s1 -. "payload.get('skill_params')" .-> s8
    s1 -. "params.get('input_file')" .-> s9
    s1 -. "isinstance(name, str)" .-> s10
    s1 -. "json.dump({...}, sys.stdout)" .-> s11
    s1 -. "payload.get('mode', 'live')" .-> s12
    b0["filesystem_read json.load"]
    s1 -. "filesystem_read json.load" .-> b0
    click s1 "../modules/conformance_bootstrap.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | - | `sys`, `json`, `sys`, `sys`, `sys`, `sys`, `sys` | - | `2`, `2`, `2`, `0`, `0` |
| `json.load` | - | - | - | - |
| `json.dump` | - | - | - | - |
| `Path` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `str` | - | - | - | - |
| `json.dump` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `params.get` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `json.dump` | - | - | - | - |
| `payload.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | json.load | 11 | `json.load(sys.stdin)` |
| main | json.dump | 13 | `json.dump({...}, sys.stdout)` |
| main | Path | 15 | `Path(...)` |
| main | payload.get | 15 | `payload.get('workspace')` |
| main | str | 16 | `str(ws)` |
| main | json.dump | 17 | `json.dump({...}, sys.stdout)` |
| main | payload.get | 19 | `payload.get('skill_params')` |
| main | params.get | 20 | `params.get('input_file')` |
| main | isinstance | 21 | `isinstance(name, str)` |
| main | json.dump | 22 | `json.dump({...}, sys.stdout)` |
| main | payload.get | 24 | `payload.get('mode', 'live')` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_read | `json.load` | `main` | 11 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `main` | `json.dump` | 13 |
| unresolved_call | `main` | `payload.get` | 15 |
| external_call | `main` | `json.dump` | 17 |
| unresolved_call | `main` | `payload.get` | 19 |
| unresolved_call | `main` | `params.get` | 20 |
| external_call | `main` | `isinstance` | 21 |
| external_call | `main` | `json.dump` | 22 |
| unresolved_call | `main` | `payload.get` | 24 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
