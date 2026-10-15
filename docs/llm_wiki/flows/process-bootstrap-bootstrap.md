# bootstrap

**Entry point:** `main` (`process`)
**Source:** [code-refactor_bootstrap](../modules/code-refactor_bootstrap.md)
**Modules touched:** [code-refactor_bootstrap](../modules/code-refactor_bootstrap.md)

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
    participant p6 as ws.mkdir
    participant p7 as (…).write_text (skills/code-refactor/bootstrap.py:main, 1)
    participant p8 as (…).write_text (skills/code-refactor/bootstrap.py:main)
    participant p9 as open
    participant p10 as f.write
    participant p11 as json.dumps
    p0-->>p1: json.load(sys.stdin)
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p3: Path(...)
    p0-->>p4: payload.get('workspace')
    p0-->>p5: str(ws)
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p4: payload.get('mode', 'live')
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p6: ws.mkdir(parents=True, exist_ok=True)
    p0-->>p7: (…).write_text (skills/code-refactor/bootstrap.py:main, 1)(_DEFAULT_TARGET, encoding='utf-8')
    p0-->>p8: (…).write_text (skills/code-refactor/bootstrap.py:main)(_DEFAULT_TARGET, encoding='utf-8')
    p0-->>p9: open(..., 'w', encoding='utf-8')
    p0-->>p10: f.write(...)
    p0-->>p11: json.dumps(t)
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p5: str(ws)
```

> Call sequence diagram shows 16 of 16 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 10 of 10 (0 omitted); unresolved 6 of 6 (0 omitted). These counts cover the captured static trace.
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
    s9["9. json.dump"]
    s10["10. ws.mkdir"]
    s11["11. (…).write_text (skills/code-refactor/bootstrap.py:main, 1)"]
    s12["12. (…).write_text (skills/code-refactor/bootstrap.py:main)"]
    s1 -. "json.load(sys.stdin)" .-> s2
    s1 -. "json.dump({...}, sys.stdout)" .-> s3
    s1 -. "Path(...)" .-> s4
    s1 -. "payload.get('workspace')" .-> s5
    s1 -. "str(ws)" .-> s6
    s1 -. "json.dump({...}, sys.stdout)" .-> s7
    s1 -. "payload.get('mode', 'live')" .-> s8
    s1 -. "json.dump({...}, sys.stdout)" .-> s9
    s1 -. "ws.mkdir(parents=True, exist_ok=True)" .-> s10
    s1 -. "(…).write_text (skills/code-refactor/bootstrap.py:main, 1)(_DEFAULT_TARGET, encoding='utf-8')" .-> s11
    s1 -. "(…).write_text (skills/code-refactor/bootstrap.py:main)(_DEFAULT_TARGET, encoding='utf-8')" .-> s12
    b0["filesystem_read json.load"]
    s1 -. "filesystem_read json.load" .-> b0
    b1["filesystem_write open"]
    s1 -. "filesystem_write open" .-> b1
    click s1 "../modules/code-refactor_bootstrap.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | - | `sys`, `json`, `sys`, `sys`, `_RENDERED`, `sys`, `_DEFAULT_TARGET`, `_DEFAULT_TARGET` | - | `2`, `2`, `0`, `0` |
| `json.load` | - | - | - | - |
| `json.dump` | - | - | - | - |
| `Path` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `str` | - | - | - | - |
| `json.dump` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `json.dump` | - | - | - | - |
| `ws.mkdir` | - | - | - | - |
| `(…).write_text (skills/code-refactor/bootstrap.py:main, 1)` | - | - | - | - |
| `(…).write_text (skills/code-refactor/bootstrap.py:main)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | json.load | 10 | `json.load(sys.stdin)` |
| main | json.dump | 12 | `json.dump({...}, sys.stdout)` |
| main | Path | 13 | `Path(...)` |
| main | payload.get | 13 | `payload.get('workspace')` |
| main | str | 14 | `str(ws)` |
| main | json.dump | 15 | `json.dump({...}, sys.stdout)` |
| main | payload.get | 16 | `payload.get('mode', 'live')` |
| main | json.dump | 17 | `json.dump({...}, sys.stdout)` |
| main | ws.mkdir | 18 | `ws.mkdir(parents=True, exist_ok=True)` |
| main | (…).write_text (skills/code-refactor/bootstrap.py:main, 1) | 19 | `(ws / 'refactor_target.py').write_text(_DEFAULT_TARGET, encoding='utf-8')` |
| main | (…).write_text (skills/code-refactor/bootstrap.py:main) | 20 | `(ws / 'best_refactor_target.py').write_text(_DEFAULT_TARGET, encoding='utf-8')` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_read | `json.load` | `main` | 10 |
| filesystem_write | `open` | `main` | 21 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `main` | `json.dump` | 12 |
| unresolved_call | `main` | `payload.get` | 13 |
| external_call | `main` | `json.dump` | 15 |
| unresolved_call | `main` | `payload.get` | 16 |
| external_call | `main` | `json.dump` | 17 |
| unresolved_call | `main` | `ws.mkdir` | 18 |
| unresolved_call | `main` | `(ws / 'refactor_target.py').write_text` | 19 |
| unresolved_call | `main` | `(ws / 'best_refactor_target.py').write_text` | 20 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
