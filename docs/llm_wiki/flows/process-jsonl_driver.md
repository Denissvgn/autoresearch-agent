# jsonl_driver

**Entry point:** `main` (`process`)
**Source:** [jsonl_driver](../modules/jsonl_driver.md)
**Modules touched:** [jsonl_driver](../modules/jsonl_driver.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as emit
    participant p2 as subprocess.run
    participant p3 as result.stdout.split
    participant p4 as next_event
    participant p5 as os.environ.get
    participant p6 as sys.stdout.write
    participant p7 as json.dumps
    participant p8 as sys.stdout.flush
    p0->>p1: emit
    p0-->>p2: subprocess.run([...], capture_output=True, text=True, check=True)
    p0-->>p3: result.stdout.split
    p0-->>p4: next_event('proposal', {...})
    p0-->>p5: os.environ.get('AGENT_RUN_ID', 'run')
    p0-->>p4: next_event('evaluation_request', {...})
    p0-->>p5: os.environ.get('AGENT_RUN_ID', 'run')
    p0-->>p4: next_event('closed', {...})
    p1-->>p6: sys.stdout.write(...)
    p1-->>p7: json.dumps(event, sort_keys=True)
    p1-->>p8: sys.stdout.flush
```

> Call sequence diagram shows 11 of 11 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 6 of 6 (0 omitted); unresolved 4 of 4 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. emit"]
    s3["3. sys.stdout.write"]
    s4["4. json.dumps"]
    s5["5. sys.stdout.flush"]
    s6["6. subprocess.run"]
    s7["7. result.stdout.split"]
    s8["8. next_event"]
    s9["9. os.environ.get"]
    s10["10. next_event"]
    s11["11. os.environ.get"]
    s12["12. next_event"]
    s1 -->|"emit({...})"| s2
    s2 -. "sys.stdout.write(...)" .-> s3
    s2 -. "json.dumps(event, sort_keys=True)" .-> s4
    s2 -. "sys.stdout.flush(data not statically known)" .-> s5
    s1 -. "subprocess.run([...], capture_output=True, text=True, check=True)" .-> s6
    s1 -. "result.stdout.split(data not statically known)" .-> s7
    s1 -. "next_event('proposal', {...})" .-> s8
    s1 -. "os.environ.get('AGENT_RUN_ID', 'run')" .-> s9
    s1 -. "next_event('evaluation_request', {...})" .-> s10
    s1 -. "os.environ.get('AGENT_RUN_ID', 'run')" .-> s11
    s1 -. "next_event('closed', {...})" .-> s12
    b0["process subprocess.run"]
    s1 -. "process subprocess.run" .-> b0
    b1["environment_read os.environ.get"]
    s1 -. "environment_read os.environ.get" .-> b1
    b2["environment_read os.environ.get"]
    s1 -. "environment_read os.environ.get" .-> b2
    b3["output sys.stdout.write"]
    s2 -. "output sys.stdout.write" .-> b3
    click s1 "../modules/jsonl_driver.md"
    click s2 "../modules/jsonl_driver.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
    class b2 boundary
    class b3 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | - | `CONTRACT_VERSION` | - | `0` |
| `emit` | `event: dict` | - | - | - |
| `sys.stdout.write` | - | - | - | - |
| `json.dumps` | - | - | - | - |
| `sys.stdout.flush` | - | - | - | - |
| `subprocess.run` | - | - | - | - |
| `result.stdout.split` | - | - | - | - |
| `next_event` | - | - | - | - |
| `os.environ.get` | - | - | - | - |
| `next_event` | - | - | - | - |
| `os.environ.get` | - | - | - | - |
| `next_event` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | emit | 42 | `emit({...})` |
| emit | sys.stdout.write | 22 | `sys.stdout.write(...)` |
| emit | json.dumps | 22 | `json.dumps(event, sort_keys=True)` |
| emit | sys.stdout.flush | 23 | `sys.stdout.flush(data not statically known)` |
| main | subprocess.run | 54 | `subprocess.run([...], capture_output=True, text=True, check=True)` |
| main | result.stdout.split | 60 | `result.stdout.split(data not statically known)` |
| main | next_event | 63 | `next_event('proposal', {...})` |
| main | os.environ.get | 68 | `os.environ.get('AGENT_RUN_ID', 'run')` |
| main | next_event | 74 | `next_event('evaluation_request', {...})` |
| main | os.environ.get | 76 | `os.environ.get('AGENT_RUN_ID', 'run')` |
| main | next_event | 80 | `next_event('closed', {...})` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| process | `subprocess.run` | `main` | 54 |
| environment_read | `os.environ.get` | `main` | 68 |
| environment_read | `os.environ.get` | `main` | 76 |
| output | `sys.stdout.write` | `emit` | 22 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `emit` | `sys.stdout.flush` | 23 |
| unresolved_call | `main` | `result.stdout.split` | 60 |
| unresolved_call | `main` | `next_event` | 63 |
| unresolved_call | `main` | `next_event` | 74 |
| unresolved_call | `main` | `next_event` | 80 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
