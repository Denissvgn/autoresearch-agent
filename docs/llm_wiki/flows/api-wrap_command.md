# wrap_command

**Entry point:** `wrap_command` (`api`)
**Source:** [isolation](../modules/isolation.md)
**Modules touched:** [isolation](../modules/isolation.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as wrap_command
    participant p1 as (…).wrap
    participant p2 as select_backend
    participant p3 as probe_host
    participant p4 as info.get
    participant p5 as IsolationUnavailableError
    participant p6 as BwrapBackend
    participant p7 as shutil.which
    participant p8 as subprocess.run
    participant p9 as bool
    p0-->>p1: (…).wrap(argv, policy=policy)
    p0->>p2: select_backend
    p2->>p3: probe_host
    p2-->>p4: info.get('ready')
    p2->>p5: IsolationUnavailableError
    p2-->>p4: info.get('reason', 'host probe failed')
    p2->>p6: BwrapBackend
    p3-->>p7: shutil.which('bwrap')
    p3-->>p8: subprocess.run([...], capture_output=True, timeout=10)
    p3-->>p9: bool(user_ns)
```

> Call sequence diagram shows 10 of 10 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 3 of 3 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. wrap_command"]
    s2["2. (…).wrap"]
    s3["3. select_backend"]
    s4["4. probe_host"]
    s5["5. shutil.which"]
    s6["6. subprocess.run"]
    s7["7. bool"]
    s8["8. info.get"]
    s9["9. IsolationUnavailableError"]
    s10["10. info.get"]
    s11["11. BwrapBackend"]
    s1 -. "(…).wrap(argv, policy=policy)" .-> s2
    s1 -->|"select_backend(data not statically known)"| s3
    s3 -->|"probe_host(data not statically known)"| s4
    s4 -. "shutil.which('bwrap')" .-> s5
    s4 -. "subprocess.run([...], capture_output=True, timeout=10)" .-> s6
    s4 -. "bool(user_ns)" .-> s7
    s3 -. "info.get('ready')" .-> s8
    s3 -->|"IsolationUnavailableError(...)"| s9
    s3 -. "info.get('reason', 'host probe failed')" .-> s10
    s3 -->|"BwrapBackend(data not statically known)"| s11
    b0["process subprocess.run"]
    s4 -. "process subprocess.run" .-> b0
    click s1 "../modules/isolation.md"
    click s3 "../modules/isolation.md"
    click s4 "../modules/isolation.md"
    click s9 "../modules/isolation.md"
    click s11 "../modules/isolation.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `wrap_command` | `argv: Sequence[str]`, `policy: IsolationPolicy`, `backend: Optional[BwrapBackend]` | - | - | `...` |
| `(…).wrap` | - | - | - | - |
| `select_backend` | - | - | - | `BwrapBackend(...)` |
| `probe_host` | `bwrap_bin: Optional[str]` | `subprocess` | `info[...]`, `info[...]`, `info[...]`, `info[...]`, `info[...]` | `info`, `info` |
| `shutil.which` | - | - | - | - |
| `subprocess.run` | - | - | - | - |
| `bool` | - | - | - | - |
| `info.get` | - | - | - | - |
| `IsolationUnavailableError` | - | - | - | - |
| `info.get` | - | - | - | - |
| `BwrapBackend` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| wrap_command | (…).wrap | 208 | `(backend or select_backend()).wrap(argv, policy=policy)` |
| wrap_command | select_backend | 208 | `select_backend(data not statically known)` |
| select_backend | probe_host | 196 | `probe_host(data not statically known)` |
| probe_host | shutil.which | 167 | `shutil.which('bwrap')` |
| probe_host | subprocess.run | 174 | `subprocess.run([...], capture_output=True, timeout=10)` |
| probe_host | bool | 183 | `bool(user_ns)` |
| select_backend | info.get | 197 | `info.get('ready')` |
| select_backend | IsolationUnavailableError | 198 | `IsolationUnavailableError(...)` |
| select_backend | info.get | 199 | `info.get('reason', 'host probe failed')` |
| select_backend | BwrapBackend | 201 | `BwrapBackend(data not statically known)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| process | `subprocess.run` | `probe_host` | 174 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `wrap_command` | `(backend or select_backend()).wrap` | 208 |
| external_call | `probe_host` | `shutil.which` | 167 |
| unresolved_call | `select_backend` | `info.get` | 197 |
| unresolved_call | `select_backend` | `info.get` | 199 |

## Behavior

This flow starts at `wrap_command` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
