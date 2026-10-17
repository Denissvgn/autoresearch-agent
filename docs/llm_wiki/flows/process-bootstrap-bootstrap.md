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
    participant p4 as payload.get (skills/code-refactor/bootstrap.py:main)
    participant p5 as str
    participant p6 as _target_name
    participant p7 as ws.mkdir
    participant p8 as (…).write_text (skills/code-refactor/bootstrap.py:main, 1)
    participant p9 as (…).write_text (skills/code-refactor/bootstrap.py:main)
    participant p10 as open
    participant p11 as f.write
    participant p12 as json.dumps
    participant p13 as payload.get (skills/code-refactor/bootstrap.py:_target_name)
    participant p14 as params.get
    participant p15 as isinstance
    participant p16 as name.endswith
    participant p17 as ValueError
    p0-->>p1: json.load(sys.stdin)
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p3: Path(...)
    p0-->>p4: payload.get (skills/code-refactor/bootstrap.py:main)('workspace')
    p0-->>p5: str(ws)
    p0-->>p2: json.dump({...}, sys.stdout)
    p0->>p6: _target_name
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p5: str(exc)
    p0-->>p4: payload.get (skills/code-refactor/bootstrap.py:main)('mode', 'live')
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p7: ws.mkdir(parents=True, exist_ok=True)
    p0-->>p8: (…).write_text (skills/code-refactor/bootstrap.py:main, 1)(_DEFAULT_TARGET, encoding='utf-8')
    p0-->>p9: (…).write_text (skills/code-refactor/bootstrap.py:main)(_DEFAULT_TARGET, encoding='utf-8')
    p0-->>p10: open(..., 'w', encoding='utf-8')
    p0-->>p11: f.write(...)
    p0-->>p12: json.dumps(t)
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p5: str(ws)
    p6-->>p13: payload.get (skills/code-refactor/bootstrap.py:_target_name)('skill_params')
    p6-->>p14: params.get('target_file')
    p6-->>p15: isinstance(name, str)
    p6-->>p16: name.endswith('.py')
    p6-->>p17: ValueError('target_file must be a workspace-relative .py file name')
```

> Call sequence diagram shows 24 of 24 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 14 of 14 (0 omitted); unresolved 9 of 9 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. json.load"]
    s3["3. json.dump"]
    s4["4. Path"]
    s5["5. payload.get (skills/code-refactor/bootstrap.py:main)"]
    s6["6. str"]
    s7["7. json.dump"]
    s8["8. _target_name"]
    s9["9. payload.get (skills/code-refactor/bootstrap.py:_target_name)"]
    s10["10. params.get"]
    s11["11. isinstance"]
    s12["12. name.endswith"]
    s1 -. "json.load(sys.stdin)" .-> s2
    s1 -. "json.dump({...}, sys.stdout)" .-> s3
    s1 -. "Path(...)" .-> s4
    s1 -. "payload.get (skills/code-refactor/bootstrap.py:main)('workspace')" .-> s5
    s1 -. "str(ws)" .-> s6
    s1 -. "json.dump({...}, sys.stdout)" .-> s7
    s1 -->|"_target_name(payload)"| s8
    s8 -. "payload.get (skills/code-refactor/bootstrap.py:_target_name)('skill_params')" .-> s9
    s8 -. "params.get('target_file')" .-> s10
    s8 -. "isinstance(name, str)" .-> s11
    s8 -. "name.endswith('.py')" .-> s12
    b0["filesystem_read json.load"]
    s1 -. "filesystem_read json.load" .-> b0
    b1["filesystem_write open"]
    s1 -. "filesystem_write open" .-> b1
    click s1 "../modules/code-refactor_bootstrap.md"
    click s8 "../modules/code-refactor_bootstrap.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | - | `sys`, `json`, `sys`, `sys`, `sys`, `sys`, `_DEFAULT_TARGET`, `_DEFAULT_TARGET` | - | `2`, `2`, `2`, `0`, `0`, `0` |
| `json.load` | - | - | - | - |
| `json.dump` | - | - | - | - |
| `Path` | - | - | - | - |
| `payload.get (skills/code-refactor/bootstrap.py:main)` | - | - | - | - |
| `str` | - | - | - | - |
| `json.dump` | - | - | - | - |
| `_target_name` | `payload` | - | - | `name` |
| `payload.get (skills/code-refactor/bootstrap.py:_target_name)` | - | - | - | - |
| `params.get` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `name.endswith` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | json.load | 16 | `json.load(sys.stdin)` |
| main | json.dump | 18 | `json.dump({...}, sys.stdout)` |
| main | Path | 19 | `Path(...)` |
| main | payload.get (skills/code-refactor/bootstrap.py:main) | 19 | `payload.get('workspace')` |
| main | str | 20 | `str(ws)` |
| main | json.dump | 21 | `json.dump({...}, sys.stdout)` |
| main | _target_name | 23 | `_target_name(payload)` |
| _target_name | payload.get (skills/code-refactor/bootstrap.py:_target_name) | 8 | `payload.get('skill_params')` |
| _target_name | params.get | 9 | `params.get('target_file')` |
| _target_name | isinstance | 10 | `isinstance(name, str)` |
| _target_name | name.endswith | 11 | `name.endswith('.py')` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_read | `json.load` | `main` | 16 |
| filesystem_write | `open` | `main` | 32 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `main` | `json.dump` | 18 |
| unresolved_call | `main` | `payload.get` | 19 |
| external_call | `main` | `json.dump` | 21 |
| unresolved_call | `_target_name` | `payload.get` | 8 |
| unresolved_call | `_target_name` | `params.get` | 9 |
| external_call | `_target_name` | `isinstance` | 10 |
| unresolved_call | `_target_name` | `name.endswith` | 11 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
