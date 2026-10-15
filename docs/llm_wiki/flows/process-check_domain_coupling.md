# check_domain_coupling

**Entry point:** `main` (`process`)
**Source:** [check_domain_coupling](../modules/check_domain_coupling.md)
**Modules touched:** [check_domain_coupling](../modules/check_domain_coupling.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as target.is_file
    participant p2 as sorted
    participant p3 as target.rglob
    participant p4 as path.is_file
    participant p5 as path.relative_to(…).as_posix
    participant p6 as path.relative_to
    participant p7 as path.read_text
    participant p8 as enumerate
    participant p9 as text.splitlines
    participant p10 as PATTERN.search
    participant p11 as violations.append
    participant p12 as line.strip
    participant p13 as print
    p0-->>p1: target.is_file
    p0-->>p2: sorted(target.rglob(...))
    p0-->>p3: target.rglob('*')
    p0-->>p4: path.is_file
    p0-->>p5: path.relative_to(…).as_posix
    p0-->>p6: path.relative_to(REPO_ROOT)
    p0-->>p7: path.read_text(encoding='utf-8', errors='replace')
    p0-->>p8: enumerate(text.splitlines(...), 1)
    p0-->>p9: text.splitlines
    p0-->>p10: PATTERN.search(line)
    p0-->>p11: violations.append(...)
    p0-->>p12: line.strip
    p0-->>p13: print('Domain-coupling violations found:')
    p0-->>p13: print(...)
    p0-->>p13: print('Domain-coupling guard: clean')
```

> Call sequence diagram shows 15 of 15 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 5 of 5 (0 omitted); unresolved 10 of 10 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. target.is_file"]
    s3["3. sorted"]
    s4["4. target.rglob"]
    s5["5. path.is_file"]
    s6["6. path.relative_to(…).as_posix"]
    s7["7. path.relative_to"]
    s8["8. path.read_text"]
    s9["9. enumerate"]
    s10["10. text.splitlines"]
    s11["11. PATTERN.search"]
    s12["12. violations.append"]
    s1 -. "target.is_file(data not statically known)" .-> s2
    s1 -. "sorted(target.rglob(...))" .-> s3
    s1 -. "target.rglob('*')" .-> s4
    s1 -. "path.is_file(data not statically known)" .-> s5
    s1 -. "path.relative_to(…).as_posix(data not statically known)" .-> s6
    s1 -. "path.relative_to(REPO_ROOT)" .-> s7
    s1 -. "path.read_text(encoding='utf-8', errors='replace')" .-> s8
    s1 -. "enumerate(text.splitlines(...), 1)" .-> s9
    s1 -. "text.splitlines(data not statically known)" .-> s10
    s1 -. "PATTERN.search(line)" .-> s11
    s1 -. "violations.append(...)" .-> s12
    b0["filesystem_read path.read_text"]
    s1 -. "filesystem_read path.read_text" .-> b0
    b1["mutation violations.append"]
    s1 -. "mutation violations.append" .-> b1
    b2["output print"]
    s1 -. "output print" .-> b2
    b3["output print"]
    s1 -. "output print" .-> b3
    b4["output print"]
    s1 -. "output print" .-> b4
    click s1 "../modules/check_domain_coupling.md"
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
| `main` | - | `TARGETS`, `EXEMPT_PATHS` | - | `1`, `0` |
| `target.is_file` | - | - | - | - |
| `sorted` | - | - | - | - |
| `target.rglob` | - | - | - | - |
| `path.is_file` | - | - | - | - |
| `path.relative_to(…).as_posix` | - | - | - | - |
| `path.relative_to` | - | - | - | - |
| `path.read_text` | - | - | - | - |
| `enumerate` | - | - | - | - |
| `text.splitlines` | - | - | - | - |
| `PATTERN.search` | - | - | - | - |
| `violations.append` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | target.is_file | 61 | `target.is_file(data not statically known)` |
| main | sorted | 61 | `sorted(target.rglob(...))` |
| main | target.rglob | 61 | `target.rglob('*')` |
| main | path.is_file | 63 | `path.is_file(data not statically known)` |
| main | path.relative_to(…).as_posix | 65 | `path.relative_to(REPO_ROOT).as_posix(data not statically known)` |
| main | path.relative_to | 65 | `path.relative_to(REPO_ROOT)` |
| main | path.read_text | 68 | `path.read_text(encoding='utf-8', errors='replace')` |
| main | enumerate | 69 | `enumerate(text.splitlines(...), 1)` |
| main | text.splitlines | 69 | `text.splitlines(data not statically known)` |
| main | PATTERN.search | 78 | `PATTERN.search(line)` |
| main | violations.append | 79 | `violations.append(...)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_read | `path.read_text` | `main` | 68 |
| mutation | `violations.append` | `main` | 79 |
| output | `print` | `main` | 81 |
| output | `print` | `main` | 83 |
| output | `print` | `main` | 85 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `main` | `target.is_file` | 61 |
| external_call | `main` | `sorted` | 61 |
| unresolved_call | `main` | `target.rglob` | 61 |
| unresolved_call | `main` | `path.is_file` | 63 |
| unresolved_call | `main` | `path.relative_to(REPO_ROOT).as_posix` | 65 |
| unresolved_call | `main` | `path.relative_to` | 65 |
| external_call | `main` | `enumerate` | 69 |
| unresolved_call | `main` | `text.splitlines` | 69 |
| unresolved_call | `main` | `PATTERN.search` | 78 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
