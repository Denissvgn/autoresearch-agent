# bootstrap

**Entry point:** `main` (`process`)
**Source:** [prompt-engineering_bootstrap](../modules/prompt-engineering_bootstrap.md)
**Modules touched:** [prompt-engineering_bootstrap](../modules/prompt-engineering_bootstrap.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as json.load
    participant p2 as json.dump
    participant p3 as isinstance
    participant p4 as payload.get
    participant p5 as Path
    participant p6 as workspace.is_absolute
    participant p7 as ValueError
    participant p8 as params.get
    participant p9 as source_path.is_absolute
    participant p10 as load_examples
    participant p11 as any
    participant p12 as part.is_symlink
    participant p13 as target.is_symlink
    participant p14 as target.exists
    participant p15 as target.is_file
    participant p16 as ''.join
    participant p17 as json.dumps
    p0-->>p1: json.load(sys.stdin)
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p3: isinstance(payload, dict)
    p0-->>p3: isinstance(payload.get(...), str)
    p0-->>p4: payload.get('workspace')
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p5: Path(payload[...])
    p0-->>p4: payload.get('mode', 'live')
    p0-->>p6: workspace.is_absolute
    p0-->>p3: isinstance(mode, str)
    p0-->>p2: json.dump({...}, sys.stdout)
    p0-->>p4: payload.get('skill_params', {...})
    p0-->>p3: isinstance(params, dict)
    p0-->>p7: ValueError('skill_params must be an object')
    p0-->>p8: params.get('eval_set')
    p0-->>p4: payload.get('demo_mode')
    p0-->>p3: isinstance(source, str)
    p0-->>p7: ValueError('eval_set is required outside explicit demo')
    p0-->>p5: Path(source)
    p0-->>p9: source_path.is_absolute
    p0-->>p10: load_examples(source_path)
    p0-->>p11: any(...)
    p0-->>p12: part.is_symlink
    p0-->>p7: ValueError('workspace must not use symlinks')
    p0-->>p13: target.is_symlink
    p0-->>p14: target.exists
    p0-->>p15: target.is_file
    p0-->>p7: ValueError('bootstrap destinations must be regular files')
    p0-->>p16: ''.join(...)
    p0-->>p17: json.dumps(example)
```

> Call sequence diagram shows 30 of 43 interactions; 13 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 18 of 24 (6 omitted); unresolved 12 of 19 (7 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `skills/prompt-engineering/bootstrap.py:main` | 1 | - | unresolved | 7 |
| `skills/prompt-engineering/bootstrap.py:main` | 1 | - | external | 6 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. json.load"]
    s3["3. json.dump"]
    s4["4. isinstance"]
    s5["5. isinstance"]
    s6["6. payload.get"]
    s7["7. json.dump"]
    s8["8. Path"]
    s9["9. payload.get"]
    s10["10. workspace.is_absolute"]
    s11["11. isinstance"]
    s12["12. json.dump"]
    s1 -. "json.load(sys.stdin)" .-> s2
    s1 -. "json.dump({...}, sys.stdout)" .-> s3
    s1 -. "isinstance(payload, dict)" .-> s4
    s1 -. "isinstance(payload.get(...), str)" .-> s5
    s1 -. "payload.get('workspace')" .-> s6
    s1 -. "json.dump({...}, sys.stdout)" .-> s7
    s1 -. "Path(payload[...])" .-> s8
    s1 -. "payload.get('mode', 'live')" .-> s9
    s1 -. "workspace.is_absolute(data not statically known)" .-> s10
    s1 -. "isinstance(mode, str)" .-> s11
    s1 -. "json.dump({...}, sys.stdout)" .-> s12
    b0["filesystem_read json.load"]
    s1 -. "filesystem_read json.load" .-> b0
    click s1 "../modules/prompt-engineering_bootstrap.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | - | `sys`, `json`, `sys`, `sys`, `sys`, `_DEFAULT_EVAL_SET`, `_RENDERED`, `sys` | - | `2`, `2`, `2`, `2`, `0`, `0` |
| `json.load` | - | - | - | - |
| `json.dump` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `json.dump` | - | - | - | - |
| `Path` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `workspace.is_absolute` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `json.dump` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | json.load | 43 | `json.load(sys.stdin)` |
| main | json.dump | 45 | `json.dump({...}, sys.stdout)` |
| main | isinstance | 49 | `isinstance(payload, dict)` |
| main | isinstance | 50 | `isinstance(payload.get(...), str)` |
| main | payload.get | 50 | `payload.get('workspace')` |
| main | json.dump | 53 | `json.dump({...}, sys.stdout)` |
| main | Path | 55 | `Path(payload[...])` |
| main | payload.get | 56 | `payload.get('mode', 'live')` |
| main | workspace.is_absolute | 57 | `workspace.is_absolute(data not statically known)` |
| main | isinstance | 57 | `isinstance(mode, str)` |
| main | json.dump | 58 | `json.dump({...}, sys.stdout)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_read | `json.load` | `main` | 43 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `main` | `json.dump` | 45 |
| external_call | `main` | `isinstance` | 49 |
| external_call | `main` | `isinstance` | 50 |
| unresolved_call | `main` | `payload.get` | 50 |
| external_call | `main` | `json.dump` | 53 |
| unresolved_call | `main` | `payload.get` | 56 |
| unresolved_call | `main` | `workspace.is_absolute` | 57 |
| external_call | `main` | `isinstance` | 57 |
| external_call | `main` | `json.dump` | 58 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
