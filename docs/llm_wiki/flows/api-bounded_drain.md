# bounded_drain

**Entry point:** `bounded_drain` (`api`)
**Source:** [process_limits](../modules/process_limits.md)
**Modules touched:** [process_limits](../modules/process_limits.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as bounded_drain
    participant p1 as terminate_process_tree
    participant p2 as signal_violation
    participant p3 as DrainOutcome
    participant p4 as bytearray
    participant p5 as proc.stdin.write
    participant p6 as proc.stdin.close
    participant p7 as selectors.DefaultSelector
    participant p8 as sel.register
    participant p9 as time.monotonic
    participant p10 as min
    participant p11 as max
    participant p12 as sel.select
    participant p13 as proc.poll (src/core/process_limits.py:bounded_drain)
    participant p14 as os.read
    participant p15 as sel.unregister
    participant p16 as len
    participant p17 as buf.extend
    participant p18 as sel.get_map
    participant p19 as sel.close
    participant p20 as proc.wait (src/core/process_limits.py:bounded_drain)
    participant p21 as bytes
    participant p22 as proc.terminate
    participant p23 as getattr
    participant p24 as proc.wait (src/core/process_limits.py:terminate_process_tree)
    p0->>p1: terminate_process_tree
    p0->>p2: signal_violation
    p0->>p3: DrainOutcome
    p0-->>p4: bytearray
    p0-->>p5: proc.stdin.write(input_bytes)
    p0-->>p4: bytearray
    p0-->>p6: proc.stdin.close
    p0-->>p7: selectors.DefaultSelector
    p0-->>p8: sel.register(stream, selectors.EVENT_READ, name)
    p0-->>p9: time.monotonic
    p0-->>p9: time.monotonic
    p0-->>p10: min(timeout, max(...))
    p0-->>p11: max(0.0, ...)
    p0-->>p12: sel.select(timeout)
    p0-->>p13: proc.poll (src/core/process_limits.py:bounded_drain)
    p0-->>p14: os.read(key.fd, _DRAIN_CHUNK_BYTES)
    p0-->>p15: sel.unregister(key.fileobj)
    p0-->>p16: len(chunk)
    p0-->>p17: buf.extend(chunk)
    p0-->>p16: len(buf)
    p0-->>p18: sel.get_map
    p0-->>p13: proc.poll (src/core/process_limits.py:bounded_drain)
    p0-->>p19: sel.close
    p0-->>p20: proc.wait (src/core/process_limits.py:bounded_drain)(timeout=TERMINATION_BOUND_S)
    p0-->>p21: bytes(stdout_buf)
    p0-->>p21: bytes(stderr_buf)
    p1-->>p22: proc.terminate
    p2-->>p23: getattr(signal, 'SIGXFSZ', 25)
    p1-->>p24: proc.wait (src/core/process_limits.py:terminate_process_tree)(timeout=TERMINATION_BOUND_S)
    p2-->>p23: getattr(signal, 'SIGXCPU', 24)
```

> Call sequence diagram shows 30 of 44 interactions; 14 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 14 of 14 (0 omitted); unresolved 13 of 26 (13 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/process_limits.py:terminate_process_tree` | 22 | - | unresolved | 13 |
| `src/core/process_limits.py:bounded_drain` | 1 | [src/core/process_limits.py](../modules/process_limits.md) | internal | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. bounded_drain"]
    s2["2. bytearray"]
    s3["3. bytearray"]
    s4["4. proc.stdin.write"]
    s5["5. proc.stdin.close"]
    s6["6. selectors.DefaultSelector"]
    s7["7. sel.register"]
    s8["8. time.monotonic"]
    s9["9. time.monotonic"]
    s10["10. min"]
    s11["11. max"]
    s12["12. sel.select"]
    s1 -. "bytearray(data not statically known)" .-> s2
    s1 -. "bytearray(data not statically known)" .-> s3
    s1 -. "proc.stdin.write(input_bytes)" .-> s4
    s1 -. "proc.stdin.close(data not statically known)" .-> s5
    s1 -. "selectors.DefaultSelector(data not statically known)" .-> s6
    s1 -. "sel.register(stream, selectors.EVENT_READ, name)" .-> s7
    s1 -. "time.monotonic(data not statically known)" .-> s8
    s1 -. "time.monotonic(data not statically known)" .-> s9
    s1 -. "min(timeout, max(...))" .-> s10
    s1 -. "max(0.0, ...)" .-> s11
    s1 -. "sel.select(timeout)" .-> s12
    b0["mutation buf.extend"]
    s1 -. "mutation buf.extend" .-> b0
    click s1 "../modules/process_limits.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `bounded_drain` | `proc: 'subprocess.Popen'`, `input_bytes: Optional[bytes]`, `caps: ProcessResourceCaps`, `guard: Optional[TreeResourceGuard]` | `selectors`, `_DRAIN_CHUNK_BYTES`, `TERMINATION_BOUND_S`, `subprocess` | - | `DrainOutcome(...)` |
| `bytearray` | - | - | - | - |
| `bytearray` | - | - | - | - |
| `proc.stdin.write` | - | - | - | - |
| `proc.stdin.close` | - | - | - | - |
| `selectors.DefaultSelector` | - | - | - | - |
| `sel.register` | - | - | - | - |
| `time.monotonic` | - | - | - | - |
| `time.monotonic` | - | - | - | - |
| `min` | - | - | - | - |
| `max` | - | - | - | - |
| `sel.select` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| bounded_drain | bytearray | 277 | `bytearray(data not statically known)` |
| bounded_drain | bytearray | 278 | `bytearray(data not statically known)` |
| bounded_drain | proc.stdin.write | 288 | `proc.stdin.write(input_bytes)` |
| bounded_drain | proc.stdin.close | 289 | `proc.stdin.close(data not statically known)` |
| bounded_drain | selectors.DefaultSelector | 293 | `selectors.DefaultSelector(data not statically known)` |
| bounded_drain | sel.register | 296 | `sel.register(stream, selectors.EVENT_READ, name)` |
| bounded_drain | time.monotonic | 298 | `time.monotonic(data not statically known)` |
| bounded_drain | time.monotonic | 305 | `time.monotonic(data not statically known)` |
| bounded_drain | min | 312 | `min(timeout, max(...))` |
| bounded_drain | max | 312 | `max(0.0, ...)` |
| bounded_drain | sel.select | 313 | `sel.select(timeout)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `buf.extend` | `bounded_drain` | 336 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `bounded_drain` | `bytearray` | 277 |
| external_call | `bounded_drain` | `bytearray` | 278 |
| unresolved_call | `bounded_drain` | `proc.stdin.write` | 288 |
| unresolved_call | `bounded_drain` | `proc.stdin.close` | 289 |
| external_call | `bounded_drain` | `selectors.DefaultSelector` | 293 |
| unresolved_call | `bounded_drain` | `sel.register` | 296 |
| external_call | `bounded_drain` | `time.monotonic` | 298 |
| external_call | `bounded_drain` | `time.monotonic` | 305 |
| external_call | `bounded_drain` | `min` | 312 |
| external_call | `bounded_drain` | `max` | 312 |
| unresolved_call | `bounded_drain` | `sel.select` | 313 |
| step_limit | `bounded_drain` | `first 12 steps` | 0 |

## Behavior

This flow starts at `bounded_drain` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
