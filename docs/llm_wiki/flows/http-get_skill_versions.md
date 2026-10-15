# get_skill_versions

**Entry point:** `get_skill_versions` (`http`)
**Source:** [src_api_skills](../modules/src_api_skills.md)
**Modules touched:** [src_api_skills](../modules/src_api_skills.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as get_skill_versions
    participant p1 as _get_or_404
    participant p2 as _skill_git_tags
    participant p3 as _registry.get
    participant p4 as subprocess.run
    participant p5 as HTTPException
    participant p6 as str
    participant p7 as _skill_dir
    participant p8 as line.strip
    participant p9 as proc.stdout.splitlines
    p0->>p1: _get_or_404
    p0->>p2: _skill_git_tags
    p1-->>p3: _registry.get(skill_id)
    p2-->>p4: subprocess.run([...], cwd=str(...), capture_output=True, text=True, timeout=5)
    p1-->>p5: HTTPException(status_code=404, detail={...})
    p2-->>p6: str(...)
    p2->>p7: _skill_dir
    p2-->>p8: line.strip
    p2-->>p9: proc.stdout.splitlines
    p2-->>p8: line.strip
```

> Call sequence diagram shows 10 of 10 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 4 of 4 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. get_skill_versions"]
    s2["2. _get_or_404"]
    s3["3. _registry.get"]
    s4["4. HTTPException"]
    s5["5. _skill_git_tags"]
    s6["6. subprocess.run"]
    s7["7. str"]
    s8["8. _skill_dir"]
    s9["9. line.strip"]
    s10["10. proc.stdout.splitlines"]
    s11["11. line.strip"]
    s1 -->|"_get_or_404(skill_id)"| s2
    s2 -. "_registry.get(skill_id)" .-> s3
    s2 -. "HTTPException(status_code=404, detail={...})" .-> s4
    s1 -->|"_skill_git_tags(skill_id)"| s5
    s5 -. "subprocess.run([...], cwd=str(...), capture_output=True, text=True, timeout=5)" .-> s6
    s5 -. "str(...)" .-> s7
    s5 -->|"_skill_dir(skill_id)"| s8
    s5 -. "line.strip(data not statically known)" .-> s9
    s5 -. "proc.stdout.splitlines(data not statically known)" .-> s10
    s5 -. "line.strip(data not statically known)" .-> s11
    b0["process subprocess.run"]
    s5 -. "process subprocess.run" .-> b0
    click s1 "../modules/src_api_skills.md"
    click s2 "../modules/src_api_skills.md"
    click s5 "../modules/src_api_skills.md"
    click s8 "../modules/src_api_skills.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `get_skill_versions` | `skill_id: str` | - | - | `{...}` |
| `_get_or_404` | `skill_id: str` | `SkillNotRegisteredError` | - | `_registry.get(...)` |
| `_registry.get` | - | - | - | - |
| `HTTPException` | - | - | - | - |
| `_skill_git_tags` | `skill_id: str` | - | - | `[...]`, `[...]`, `...` |
| `subprocess.run` | - | - | - | - |
| `str` | - | - | - | - |
| `_skill_dir` | `manifest_id: str` | `DEFAULT_SKILLS_ROOT` | - | `...` |
| `line.strip` | - | - | - | - |
| `proc.stdout.splitlines` | - | - | - | - |
| `line.strip` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| get_skill_versions | _get_or_404 | 324 | `_get_or_404(skill_id)` |
| _get_or_404 | _registry.get | 181 | `_registry.get(skill_id)` |
| _get_or_404 | HTTPException | 183 | `HTTPException(status_code=404, detail={...})` |
| get_skill_versions | _skill_git_tags | 325 | `_skill_git_tags(skill_id)` |
| _skill_git_tags | subprocess.run | 349 | `subprocess.run([...], cwd=str(...), capture_output=True, text=True, timeout=5)` |
| _skill_git_tags | str | 351 | `str(...)` |
| _skill_git_tags | _skill_dir | 351 | `_skill_dir(skill_id)` |
| _skill_git_tags | line.strip | 358 | `line.strip(data not statically known)` |
| _skill_git_tags | proc.stdout.splitlines | 358 | `proc.stdout.splitlines(data not statically known)` |
| _skill_git_tags | line.strip | 358 | `line.strip(data not statically known)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| process | `subprocess.run` | `_skill_git_tags` | 349 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `_get_or_404` | `_registry.get` | 181 |
| external_call | `_get_or_404` | `HTTPException` | 183 |
| unresolved_call | `_skill_git_tags` | `line.strip` | 358 |
| unresolved_call | `_skill_git_tags` | `proc.stdout.splitlines` | 358 |

## Behavior

This flow starts at `get_skill_versions` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
