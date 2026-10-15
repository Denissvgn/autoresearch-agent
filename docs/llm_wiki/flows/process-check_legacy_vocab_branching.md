# check_legacy_vocab_branching

**Entry point:** `main` (`process`)
**Source:** [check_legacy_vocab_branching](../modules/check_legacy_vocab_branching.md)
**Modules touched:** [check_legacy_vocab_branching](../modules/check_legacy_vocab_branching.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as sorted
    participant p2 as src_root.rglob
    participant p3 as path.relative_to(…).as_posix
    participant p4 as path.relative_to
    participant p5 as rel.startswith
    participant p6 as path.read_text(…).splitlines
    participant p7 as path.read_text
    participant p8 as enumerate
    participant p9 as line.lstrip
    participant p10 as stripped.startswith
    participant p11 as pattern.search
    participant p12 as violations.append
    participant p13 as stripped.strip
    participant p14 as print
    participant p15 as len
    p0-->>p1: sorted(src_root.rglob(...))
    p0-->>p2: src_root.rglob('*.py')
    p0-->>p3: path.relative_to(…).as_posix
    p0-->>p4: path.relative_to(REPO_ROOT)
    p0-->>p5: rel.startswith('src/compat/')
    p0-->>p6: path.read_text(…).splitlines
    p0-->>p7: path.read_text(encoding='utf-8')
    p0-->>p8: enumerate(lines, 1)
    p0-->>p9: line.lstrip
    p0-->>p10: stripped.startswith(' ')
    p0-->>p11: pattern.search(line)
    p0-->>p12: violations.append(...)
    p0-->>p13: stripped.strip
    p0-->>p14: print('Legacy-vocabulary branching outside the frozen surfaces:')
    p0-->>p14: print(...)
    p0-->>p14: print(…)
    p0-->>p14: print(...)
    p0-->>p15: len(ALLOWED)
```

> Call sequence diagram shows 18 of 18 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 7 of 7 (0 omitted); unresolved 11 of 11 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. sorted"]
    s3["3. src_root.rglob"]
    s4["4. path.relative_to(…).as_posix"]
    s5["5. path.relative_to"]
    s6["6. rel.startswith"]
    s7["7. path.read_text(…).splitlines"]
    s8["8. path.read_text"]
    s9["9. enumerate"]
    s10["10. line.lstrip"]
    s11["11. stripped.startswith"]
    s12["12. pattern.search"]
    s1 -. "sorted(src_root.rglob(...))" .-> s2
    s1 -. "src_root.rglob('*.py')" .-> s3
    s1 -. "path.relative_to(…).as_posix(data not statically known)" .-> s4
    s1 -. "path.relative_to(REPO_ROOT)" .-> s5
    s1 -. "rel.startswith('src/compat/')" .-> s6
    s1 -. "path.read_text(…).splitlines(data not statically known)" .-> s7
    s1 -. "path.read_text(encoding='utf-8')" .-> s8
    s1 -. "enumerate(lines, 1)" .-> s9
    s1 -. "line.lstrip(data not statically known)" .-> s10
    s1 -. "stripped.startswith('#35;')" .-> s11
    s1 -. "pattern.search(line)" .-> s12
    b0["mutation violations.append"]
    s1 -. "mutation violations.append" .-> b0
    b1["output print"]
    s1 -. "output print" .-> b1
    b2["output print"]
    s1 -. "output print" .-> b2
    b3["output print"]
    s1 -. "output print" .-> b3
    b4["output print"]
    s1 -. "output print" .-> b4
    click s1 "../modules/check_legacy_vocab_branching.md"
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
| `main` | - | `REPO_ROOT`, `ALLOWED`, `PATTERNS`, `ALLOWED` | - | `1`, `0` |
| `sorted` | - | - | - | - |
| `src_root.rglob` | - | - | - | - |
| `path.relative_to(…).as_posix` | - | - | - | - |
| `path.relative_to` | - | - | - | - |
| `rel.startswith` | - | - | - | - |
| `path.read_text(…).splitlines` | - | - | - | - |
| `path.read_text` | - | - | - | - |
| `enumerate` | - | - | - | - |
| `line.lstrip` | - | - | - | - |
| `stripped.startswith` | - | - | - | - |
| `pattern.search` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | sorted | 56 | `sorted(src_root.rglob(...))` |
| main | src_root.rglob | 56 | `src_root.rglob('*.py')` |
| main | path.relative_to(…).as_posix | 57 | `path.relative_to(REPO_ROOT).as_posix(data not statically known)` |
| main | path.relative_to | 57 | `path.relative_to(REPO_ROOT)` |
| main | rel.startswith | 58 | `rel.startswith('src/compat/')` |
| main | path.read_text(…).splitlines | 63 | `path.read_text(encoding='utf-8').splitlines(data not statically known)` |
| main | path.read_text | 63 | `path.read_text(encoding='utf-8')` |
| main | enumerate | 66 | `enumerate(lines, 1)` |
| main | line.lstrip | 67 | `line.lstrip(data not statically known)` |
| main | stripped.startswith | 68 | `stripped.startswith('#')` |
| main | pattern.search | 71 | `pattern.search(line)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `violations.append` | `main` | 72 |
| output | `print` | `main` | 77 |
| output | `print` | `main` | 79 |
| output | `print` | `main` | 80 |
| output | `print` | `main` | 86 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `main` | `sorted` | 56 |
| unresolved_call | `main` | `src_root.rglob` | 56 |
| unresolved_call | `main` | `path.relative_to(REPO_ROOT).as_posix` | 57 |
| unresolved_call | `main` | `path.relative_to` | 57 |
| unresolved_call | `main` | `rel.startswith` | 58 |
| unresolved_call | `main` | `path.read_text(encoding='utf-8').splitlines` | 63 |
| unresolved_call | `main` | `path.read_text` | 63 |
| external_call | `main` | `enumerate` | 66 |
| unresolved_call | `main` | `line.lstrip` | 67 |
| unresolved_call | `main` | `stripped.startswith` | 68 |
| unresolved_call | `main` | `pattern.search` | 71 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
