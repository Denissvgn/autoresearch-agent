# select_backend

**Entry point:** `select_backend` (`api`)
**Source:** [isolation](../modules/isolation.md)
**Modules touched:** [isolation](../modules/isolation.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as select_backend
    participant p1 as probe_host
    participant p2 as info.get
    participant p3 as IsolationUnavailableError
    participant p4 as BwrapBackend
    participant p5 as shutil.which
    participant p6 as subprocess.run
    participant p7 as bool
    p0->>p1: probe_host
    p0-->>p2: info.get('ready')
    p0->>p3: IsolationUnavailableError
    p0-->>p2: info.get('reason', 'host probe failed')
    p0->>p4: BwrapBackend
    p1-->>p5: shutil.which('bwrap')
    p1-->>p6: subprocess.run([...], capture_output=True, timeout=10)
    p1-->>p7: bool(user_ns)
```

> Call sequence diagram shows 8 of 8 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 2 of 2 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. select_backend"]
    s2["2. probe_host"]
    s3["3. shutil.which"]
    s4["4. subprocess.run"]
    s5["5. bool"]
    s6["6. info.get"]
    s7["7. IsolationUnavailableError"]
    s8["8. info.get"]
    s9["9. BwrapBackend"]
    s1 -->|"probe_host(data not statically known)"| s2
    s2 -. "shutil.which('bwrap')" .-> s3
    s2 -. "subprocess.run([...], capture_output=True, timeout=10)" .-> s4
    s2 -. "bool(user_ns)" .-> s5
    s1 -. "info.get('ready')" .-> s6
    s1 -->|"IsolationUnavailableError(...)"| s7
    s1 -. "info.get('reason', 'host probe failed')" .-> s8
    s1 -->|"BwrapBackend(data not statically known)"| s9
    b0["process subprocess.run"]
    s2 -. "process subprocess.run" .-> b0
    click s1 "../modules/isolation.md"
    click s2 "../modules/isolation.md"
    click s7 "../modules/isolation.md"
    click s9 "../modules/isolation.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
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
| external_call | `probe_host` | `shutil.which` | 167 |
| unresolved_call | `select_backend` | `info.get` | 197 |
| unresolved_call | `select_backend` | `info.get` | 199 |

## Behavior

This flow starts at `select_backend` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
