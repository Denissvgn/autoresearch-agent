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
    participant p1 as UnsupportedCapabilityError
    participant p2 as (…).wrap
    participant p3 as select_backend
    participant p4 as probe_host
    participant p5 as info.get
    participant p6 as IsolationUnavailableError
    participant p7 as BwrapBackend
    participant p8 as shutil.which
    participant p9 as subprocess.run
    participant p10 as bool
    p0->>p1: UnsupportedCapabilityError
    p0-->>p2: (…).wrap(argv, policy=policy)
    p0->>p3: select_backend
    p3->>p4: probe_host
    p3-->>p5: info.get('ready')
    p3->>p6: IsolationUnavailableError
    p3-->>p5: info.get('reason', 'host probe failed')
    p3->>p7: BwrapBackend
    p4-->>p8: shutil.which('bwrap')
    p4-->>p9: subprocess.run([...], capture_output=True, timeout=10)
    p4-->>p10: bool(user_ns)
```

> Call sequence diagram shows 11 of 11 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 3 of 3 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. wrap_command"]
    s2["2. UnsupportedCapabilityError"]
    s3["3. (…).wrap"]
    s4["4. select_backend"]
    s5["5. probe_host"]
    s6["6. shutil.which"]
    s7["7. subprocess.run"]
    s8["8. bool"]
    s9["9. info.get"]
    s10["10. IsolationUnavailableError"]
    s11["11. info.get"]
    s12["12. BwrapBackend"]
    s1 -->|"UnsupportedCapabilityError(…)"| s2
    s1 -. "(…).wrap(argv, policy=policy)" .-> s3
    s1 -->|"select_backend(data not statically known)"| s4
    s4 -->|"probe_host(data not statically known)"| s5
    s5 -. "shutil.which('bwrap')" .-> s6
    s5 -. "subprocess.run([...], capture_output=True, timeout=10)" .-> s7
    s5 -. "bool(user_ns)" .-> s8
    s4 -. "info.get('ready')" .-> s9
    s4 -->|"IsolationUnavailableError(...)"| s10
    s4 -. "info.get('reason', 'host probe failed')" .-> s11
    s4 -->|"BwrapBackend(data not statically known)"| s12
    b0["process subprocess.run"]
    s5 -. "process subprocess.run" .-> b0
    click s1 "../modules/isolation.md"
    click s2 "../modules/isolation.md"
    click s4 "../modules/isolation.md"
    click s5 "../modules/isolation.md"
    click s10 "../modules/isolation.md"
    click s12 "../modules/isolation.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `wrap_command` | `argv: Sequence[str]`, `policy: IsolationPolicy`, `backend: Optional[BwrapBackend]` | - | - | `...` |
| `UnsupportedCapabilityError` | - | - | - | - |
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
| wrap_command | UnsupportedCapabilityError | 209 | `UnsupportedCapabilityError('network allowlist enforcement is not available at the OS boundary on this backend; capability refused (no fallback to unrestricted egress)')` |
| wrap_command | (…).wrap | 214 | `(backend or select_backend()).wrap(argv, policy=policy)` |
| wrap_command | select_backend | 214 | `select_backend(data not statically known)` |
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
| unresolved_call | `wrap_command` | `(backend or select_backend()).wrap` | 214 |
| external_call | `probe_host` | `shutil.which` | 167 |
| unresolved_call | `select_backend` | `info.get` | 197 |
| unresolved_call | `select_backend` | `info.get` | 199 |

## Behavior

This flow starts at `wrap_command` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
