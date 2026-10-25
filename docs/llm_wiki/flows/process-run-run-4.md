# run

**Entry point:** `main` (`process`)
**Source:** [conformance_eval_run](../modules/conformance_eval_run.md)
**Modules touched:** [conformance_eval_run](../modules/conformance_eval_run.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as _parse_flags
    participant p2 as float
    participant p3 as (…).split (tests/fixtures/conformance/eval/run.py:main)
    participant p4 as opts.get
    participant p5 as part.strip
    participant p6 as (…).strip().lower (tests/fixtures/conformance/eval/run.py:main, 1)
    participant p7 as (…).strip (tests/fixtures/conformance/eval/run.py:main, 1)
    participant p8 as part.strip().lower
    participant p9 as (…).split (tests/fixtures/conformance/eval/run.py:main, 1)
    participant p10 as pathlib.Path
    participant p11 as candidate.exists
    participant p12 as candidate.read_text(…).strip
    participant p13 as candidate.read_text
    participant p14 as counter_path.exists
    participant p15 as int
    participant p16 as counter_path.read_text(…).strip
    participant p17 as counter_path.read_text
    participant p18 as counter_path.write_text
    participant p19 as str
    participant p20 as min
    p0->>p1: _parse_flags
    p0-->>p2: float(part)
    p0-->>p3: (…).split (tests/fixtures/conformance/eval/run.py:main)(',')
    p0-->>p4: opts.get('sequence')
    p0-->>p5: part.strip
    p0-->>p4: opts.get('metric-name')
    p0-->>p4: opts.get('status')
    p0-->>p6: (…).strip().lower (tests/fixtures/conformance/eval/run.py:main, 1)
    p0-->>p7: (…).strip (tests/fixtures/conformance/eval/run.py:main, 1)
    p0-->>p4: opts.get('gates')
    p0-->>p4: opts.get('echo')
    p0-->>p8: part.strip().lower
    p0-->>p5: part.strip
    p0-->>p9: (…).split (tests/fixtures/conformance/eval/run.py:main, 1)(',')
    p0-->>p4: opts.get('threshold-sequence')
    p0-->>p5: part.strip
    p0-->>p4: opts.get('input')
    p0-->>p10: pathlib.Path(input_name)
    p0-->>p11: candidate.exists
    p0-->>p12: candidate.read_text(…).strip
    p0-->>p13: candidate.read_text(encoding='utf-8')
    p0-->>p10: pathlib.Path(...)
    p0-->>p4: opts.get('counter')
    p0-->>p14: counter_path.exists
    p0-->>p15: int(...)
    p0-->>p16: counter_path.read_text(…).strip
    p0-->>p17: counter_path.read_text(encoding='utf-8')
    p0-->>p18: counter_path.write_text(str(...), encoding='utf-8')
    p0-->>p19: str(...)
    p0-->>p20: min(index, ...)
```

> Call sequence diagram shows 30 of 61 interactions; 31 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 6 of 20 (14 omitted); unresolved 23 of 40 (17 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `tests/fixtures/conformance/eval/run.py:_parse_flags` | 2 | - | external | 2 |
| `tests/fixtures/conformance/eval/run.py:_parse_flags` | 2 | - | unresolved | 1 |
| `tests/fixtures/conformance/eval/run.py:main` | 1 | - | external | 12 |
| `tests/fixtures/conformance/eval/run.py:main` | 1 | - | unresolved | 16 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. _parse_flags"]
    s3["3. len (tests/fixtures/conformance/eval/run.py:_parse_flags)"]
    s4["4. token.startswith"]
    s5["5. len (tests/fixtures/conformance/eval/run.py:_parse_flags)"]
    s6["6. float"]
    s7["7. (…).split (tests/fixtures/conformance/eval/run.py:main)"]
    s8["8. opts.get"]
    s9["9. part.strip"]
    s10["10. opts.get"]
    s11["11. opts.get"]
    s12["12. (…).strip().lower (tests/fixtures/conformance/eval/run.py:main, 1)"]
    s1 -->|"_parse_flags(...)"| s2
    s2 -. "len (tests/fixtures/conformance/eval/run.py:_parse_flags)(argv)" .-> s3
    s2 -. "token.startswith('--')" .-> s4
    s2 -. "len (tests/fixtures/conformance/eval/run.py:_parse_flags)(argv)" .-> s5
    s1 -. "float(part)" .-> s6
    s1 -. "(…).split (tests/fixtures/conformance/eval/run.py:main)(',')" .-> s7
    s1 -. "opts.get('sequence')" .-> s8
    s1 -. "part.strip(data not statically known)" .-> s9
    s1 -. "opts.get('metric-name')" .-> s10
    s1 -. "opts.get('status')" .-> s11
    s1 -. "(…).strip().lower (tests/fixtures/conformance/eval/run.py:main, 1)(data not statically known)" .-> s12
    b0["filesystem_write counter_path.write_text"]
    s1 -. "filesystem_write counter_path.write_text" .-> b0
    b1["mutation kv_lines.append"]
    s1 -. "mutation kv_lines.append" .-> b1
    b2["mutation kv_lines.append"]
    s1 -. "mutation kv_lines.append" .-> b2
    b3["output print"]
    s1 -. "output print" .-> b3
    b4["output print"]
    s1 -. "output print" .-> b4
    click s1 "../modules/conformance_eval_run.md"
    click s2 "../modules/conformance_eval_run.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
    class b2 boundary
    class b3 boundary
    class b4 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | - | `sys` | `payload[...]`, `payload[...]` | `0` |
| `_parse_flags` | `argv: list[str]` | - | - | `opts` |
| `len (tests/fixtures/conformance/eval/run.py:_parse_flags)` | - | - | - | - |
| `token.startswith` | - | - | - | - |
| `len (tests/fixtures/conformance/eval/run.py:_parse_flags)` | - | - | - | - |
| `float` | - | - | - | - |
| `(…).split (tests/fixtures/conformance/eval/run.py:main)` | - | - | - | - |
| `opts.get` | - | - | - | - |
| `part.strip` | - | - | - | - |
| `opts.get` | - | - | - | - |
| `opts.get` | - | - | - | - |
| `(…).strip().lower (tests/fixtures/conformance/eval/run.py:main, 1)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | _parse_flags | 35 | `_parse_flags(...)` |
| _parse_flags | len (tests/fixtures/conformance/eval/run.py:_parse_flags) | 24 | `len(argv)` |
| _parse_flags | token.startswith | 26 | `token.startswith('--')` |
| _parse_flags | len (tests/fixtures/conformance/eval/run.py:_parse_flags) | 26 | `len(argv)` |
| main | float | 37 | `float(part)` |
| main | (…).split (tests/fixtures/conformance/eval/run.py:main) | 38 | `(opts.get('sequence') or '').split(',')` |
| main | opts.get | 38 | `opts.get('sequence')` |
| main | part.strip | 39 | `part.strip(data not statically known)` |
| main | opts.get | 41 | `opts.get('metric-name')` |
| main | opts.get | 42 | `opts.get('status')` |
| main | (…).strip().lower (tests/fixtures/conformance/eval/run.py:main, 1) | 43 | `(opts.get('gates') or 'pass').strip().lower(data not statically known)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_write | `counter_path.write_text` | `main` | 66 |
| mutation | `kv_lines.append` | `main` | 114 |
| mutation | `kv_lines.append` | `main` | 115 |
| output | `print` | `main` | 118 |
| output | `print` | `main` | 120 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `_parse_flags` | `token.startswith` | 26 |
| unresolved_call | `main` | `(opts.get('sequence') or '').split` | 38 |
| unresolved_call | `main` | `opts.get` | 38 |
| unresolved_call | `main` | `part.strip` | 39 |
| unresolved_call | `main` | `opts.get` | 41 |
| unresolved_call | `main` | `opts.get` | 42 |
| unresolved_call | `main` | `(opts.get('gates') or 'pass').strip().lower` | 43 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
