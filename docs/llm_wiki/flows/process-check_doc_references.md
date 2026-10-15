# check_doc_references

**Entry point:** `main` (`process`)
**Source:** [check_doc_references](../modules/check_doc_references.md)
**Modules touched:** [check_doc_references](../modules/check_doc_references.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as set
    participant p2 as root.is_dir
    participant p3 as sorted
    participant p4 as root.rglob
    participant p5 as path.is_file
    participant p6 as path.relative_to
    participant p7 as path.read_text
    participant p8 as DOC_PATH_RE.finditer
    participant p9 as match.group
    participant p10 as seen_paths.add
    participant p11 as (…).is_file
    participant p12 as violations.append
    participant p13 as print
    participant p14 as len
    p0-->>p1: set
    p0-->>p2: root.is_dir
    p0-->>p3: sorted(root.rglob(...))
    p0-->>p4: root.rglob('*')
    p0-->>p5: path.is_file
    p0-->>p6: path.relative_to(REPO_ROOT)
    p0-->>p7: path.read_text(encoding='utf-8')
    p0-->>p8: DOC_PATH_RE.finditer(text)
    p0-->>p9: match.group(0)
    p0-->>p10: seen_paths.add(referenced)
    p0-->>p11: (…).is_file
    p0-->>p12: violations.append(...)
    p0-->>p13: print('Referenced-doc violations found:')
    p0-->>p13: print(...)
    p0-->>p13: print(...)
    p0-->>p14: len(seen_paths)
```

> Call sequence diagram shows 16 of 16 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 6 of 6 (0 omitted); unresolved 10 of 10 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. set"]
    s3["3. root.is_dir"]
    s4["4. sorted"]
    s5["5. root.rglob"]
    s6["6. path.is_file"]
    s7["7. path.relative_to"]
    s8["8. path.read_text"]
    s9["9. DOC_PATH_RE.finditer"]
    s10["10. match.group"]
    s11["11. seen_paths.add"]
    s12["12. (…).is_file"]
    s1 -. "set(data not statically known)" .-> s2
    s1 -. "root.is_dir(data not statically known)" .-> s3
    s1 -. "sorted(root.rglob(...))" .-> s4
    s1 -. "root.rglob('*')" .-> s5
    s1 -. "path.is_file(data not statically known)" .-> s6
    s1 -. "path.relative_to(REPO_ROOT)" .-> s7
    s1 -. "path.read_text(encoding='utf-8')" .-> s8
    s1 -. "DOC_PATH_RE.finditer(text)" .-> s9
    s1 -. "match.group(0)" .-> s10
    s1 -. "seen_paths.add(referenced)" .-> s11
    s1 -. "(…).is_file(data not statically known)" .-> s12
    b0["filesystem_read path.read_text"]
    s1 -. "filesystem_read path.read_text" .-> b0
    b1["mutation seen_paths.add"]
    s1 -. "mutation seen_paths.add" .-> b1
    b2["mutation violations.append"]
    s1 -. "mutation violations.append" .-> b2
    b3["output print"]
    s1 -. "output print" .-> b3
    b4["output print"]
    s1 -. "output print" .-> b4
    b5["output print"]
    s1 -. "output print" .-> b5
    click s1 "../modules/check_doc_references.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
    class b2 boundary
    class b3 boundary
    class b4 boundary
    class b5 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | - | `SCAN_ROOTS`, `REPO_ROOT`, `REPO_ROOT` | - | `1`, `0` |
| `set` | - | - | - | - |
| `root.is_dir` | - | - | - | - |
| `sorted` | - | - | - | - |
| `root.rglob` | - | - | - | - |
| `path.is_file` | - | - | - | - |
| `path.relative_to` | - | - | - | - |
| `path.read_text` | - | - | - | - |
| `DOC_PATH_RE.finditer` | - | - | - | - |
| `match.group` | - | - | - | - |
| `seen_paths.add` | - | - | - | - |
| `(…).is_file` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | set | 28 | `set(data not statically known)` |
| main | root.is_dir | 31 | `root.is_dir(data not statically known)` |
| main | sorted | 33 | `sorted(root.rglob(...))` |
| main | root.rglob | 33 | `root.rglob('*')` |
| main | path.is_file | 34 | `path.is_file(data not statically known)` |
| main | path.relative_to | 38 | `path.relative_to(REPO_ROOT)` |
| main | path.read_text | 40 | `path.read_text(encoding='utf-8')` |
| main | DOC_PATH_RE.finditer | 43 | `DOC_PATH_RE.finditer(text)` |
| main | match.group | 44 | `match.group(0)` |
| main | seen_paths.add | 45 | `seen_paths.add(referenced)` |
| main | (…).is_file | 46 | `(REPO_ROOT / referenced).is_file(data not statically known)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_read | `path.read_text` | `main` | 40 |
| mutation | `seen_paths.add` | `main` | 45 |
| mutation | `violations.append` | `main` | 47 |
| output | `print` | `main` | 49 |
| output | `print` | `main` | 51 |
| output | `print` | `main` | 53 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `main` | `root.is_dir` | 31 |
| external_call | `main` | `sorted` | 33 |
| unresolved_call | `main` | `root.rglob` | 33 |
| unresolved_call | `main` | `path.is_file` | 34 |
| unresolved_call | `main` | `path.relative_to` | 38 |
| unresolved_call | `main` | `DOC_PATH_RE.finditer` | 43 |
| unresolved_call | `main` | `match.group` | 44 |
| unresolved_call | `main` | `(REPO_ROOT / referenced).is_file` | 46 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
