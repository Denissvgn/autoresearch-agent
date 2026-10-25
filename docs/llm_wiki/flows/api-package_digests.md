# package_digests

**Entry point:** `package_digests` (`api`)
**Source:** [run_spec](../modules/run_spec.md)
**Modules touched:** [run_spec](../modules/run_spec.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as package_digests
    participant p1 as Path
    participant p2 as path.is_file
    participant p3 as hashlib.sha256(…).hexdigest
    participant p4 as hashlib.sha256
    participant p5 as path.read_bytes
    participant p6 as directory.is_dir
    participant p7 as sorted
    participant p8 as directory.rglob
    participant p9 as str
    participant p10 as path.relative_to
    p0-->>p1: Path(skill_dir)
    p0-->>p2: path.is_file
    p0-->>p3: hashlib.sha256(…).hexdigest
    p0-->>p4: hashlib.sha256(path.read_bytes(...))
    p0-->>p5: path.read_bytes
    p0-->>p6: directory.is_dir
    p0-->>p7: sorted(directory.rglob(...))
    p0-->>p8: directory.rglob('*')
    p0-->>p2: path.is_file
    p0-->>p9: str(path.relative_to(...))
    p0-->>p10: path.relative_to(root)
    p0-->>p3: hashlib.sha256(…).hexdigest
    p0-->>p4: hashlib.sha256(path.read_bytes(...))
    p0-->>p5: path.read_bytes
```

> Call sequence diagram shows 14 of 14 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 5 of 5 (0 omitted); unresolved 9 of 9 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. package_digests"]
    s2["2. Path"]
    s3["3. path.is_file"]
    s4["4. hashlib.sha256(…).hexdigest"]
    s5["5. hashlib.sha256"]
    s6["6. path.read_bytes"]
    s7["7. directory.is_dir"]
    s8["8. sorted"]
    s9["9. directory.rglob"]
    s10["10. path.is_file"]
    s11["11. str"]
    s12["12. path.relative_to"]
    s1 -. "Path(skill_dir)" .-> s2
    s1 -. "path.is_file(data not statically known)" .-> s3
    s1 -. "hashlib.sha256(…).hexdigest(data not statically known)" .-> s4
    s1 -. "hashlib.sha256(path.read_bytes(...))" .-> s5
    s1 -. "path.read_bytes(data not statically known)" .-> s6
    s1 -. "directory.is_dir(data not statically known)" .-> s7
    s1 -. "sorted(directory.rglob(...))" .-> s8
    s1 -. "directory.rglob('*')" .-> s9
    s1 -. "path.is_file(data not statically known)" .-> s10
    s1 -. "str(path.relative_to(...))" .-> s11
    s1 -. "path.relative_to(root)" .-> s12
    click s1 "../modules/run_spec.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `package_digests` | `skill_dir: Optional[str]` | - | `digests[...]`, `digests[...]` | `{...}`, `digests` |
| `Path` | - | - | - | - |
| `path.is_file` | - | - | - | - |
| `hashlib.sha256(…).hexdigest` | - | - | - | - |
| `hashlib.sha256` | - | - | - | - |
| `path.read_bytes` | - | - | - | - |
| `directory.is_dir` | - | - | - | - |
| `sorted` | - | - | - | - |
| `directory.rglob` | - | - | - | - |
| `path.is_file` | - | - | - | - |
| `str` | - | - | - | - |
| `path.relative_to` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| package_digests | Path | 100 | `Path(skill_dir)` |
| package_digests | path.is_file | 104 | `path.is_file(data not statically known)` |
| package_digests | hashlib.sha256(…).hexdigest | 105 | `hashlib.sha256(path.read_bytes()).hexdigest(data not statically known)` |
| package_digests | hashlib.sha256 | 105 | `hashlib.sha256(path.read_bytes(...))` |
| package_digests | path.read_bytes | 105 | `path.read_bytes(data not statically known)` |
| package_digests | directory.is_dir | 108 | `directory.is_dir(data not statically known)` |
| package_digests | sorted | 109 | `sorted(directory.rglob(...))` |
| package_digests | directory.rglob | 109 | `directory.rglob('*')` |
| package_digests | path.is_file | 110 | `path.is_file(data not statically known)` |
| package_digests | str | 111 | `str(path.relative_to(...))` |
| package_digests | path.relative_to | 111 | `path.relative_to(root)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `package_digests` | `path.is_file` | 104 |
| unresolved_call | `package_digests` | `hashlib.sha256(path.read_bytes()).hexdigest` | 105 |
| external_call | `package_digests` | `hashlib.sha256` | 105 |
| unresolved_call | `package_digests` | `path.read_bytes` | 105 |
| unresolved_call | `package_digests` | `directory.is_dir` | 108 |
| external_call | `package_digests` | `sorted` | 109 |
| unresolved_call | `package_digests` | `directory.rglob` | 109 |
| unresolved_call | `package_digests` | `path.is_file` | 110 |
| unresolved_call | `package_digests` | `path.relative_to` | 111 |
| step_limit | `package_digests` | `first 12 steps` | 0 |

## Behavior

This flow starts at `package_digests` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
