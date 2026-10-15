# get_skill_changelog

**Entry point:** `get_skill_changelog` (`http`)
**Source:** [src_api_skills](../modules/src_api_skills.md)
**Modules touched:** [src_api_skills](../modules/src_api_skills.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as get_skill_changelog
    participant p1 as _get_or_404
    participant p2 as _skill_dir
    participant p3 as changelog_path.is_file
    participant p4 as changelog_path.stat
    participant p5 as HTTPException (src/api/skills.py:get_skill_changelog)
    participant p6 as changelog_path.read_text
    participant p7 as _registry.get
    participant p8 as HTTPException (src/api/skills.py:_get_or_404)
    p0->>p1: _get_or_404
    p0->>p2: _skill_dir
    p0-->>p3: changelog_path.is_file
    p0-->>p4: changelog_path.stat
    p0-->>p5: HTTPException (src/api/skills.py:get_skill_changelog)(status_code=413, detail={...})
    p0-->>p6: changelog_path.read_text(encoding='utf-8')
    p1-->>p7: _registry.get(skill_id)
    p1-->>p8: HTTPException (src/api/skills.py:_get_or_404)(status_code=404, detail={...})
```

> Call sequence diagram shows 8 of 8 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 2 of 2 (0 omitted); unresolved 4 of 4 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. get_skill_changelog"]
    s2["2. _get_or_404"]
    s3["3. _registry.get"]
    s4["4. HTTPException (src/api/skills.py:_get_or_404)"]
    s5["5. _skill_dir"]
    s6["6. changelog_path.is_file"]
    s7["7. changelog_path.stat"]
    s8["8. HTTPException (src/api/skills.py:get_skill_changelog)"]
    s9["9. changelog_path.read_text"]
    s1 -->|"_get_or_404(skill_id)"| s2
    s2 -. "_registry.get(skill_id)" .-> s3
    s2 -. "HTTPException (src/api/skills.py:_get_or_404)(status_code=404, detail={...})" .-> s4
    s1 -->|"_skill_dir(skill_id)"| s5
    s1 -. "changelog_path.is_file(data not statically known)" .-> s6
    s1 -. "changelog_path.stat(data not statically known)" .-> s7
    s1 -. "HTTPException (src/api/skills.py:get_skill_changelog)(status_code=413, detail={...})" .-> s8
    s1 -. "changelog_path.read_text(encoding='utf-8')" .-> s9
    b0["filesystem_read changelog_path.read_text"]
    s1 -. "filesystem_read changelog_path.read_text" .-> b0
    click s1 "../modules/src_api_skills.md"
    click s2 "../modules/src_api_skills.md"
    click s5 "../modules/src_api_skills.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `get_skill_changelog` | `skill_id: str` | `_MAX_CHANGELOG_BYTES`, `_MAX_CHANGELOG_BYTES`, `_MAX_CHANGELOG_BYTES` | - | `{...}`, `{...}` |
| `_get_or_404` | `skill_id: str` | `SkillNotRegisteredError` | - | `_registry.get(...)` |
| `_registry.get` | - | - | - | - |
| `HTTPException (src/api/skills.py:_get_or_404)` | - | - | - | - |
| `_skill_dir` | `manifest_id: str` | `DEFAULT_SKILLS_ROOT` | - | `...` |
| `changelog_path.is_file` | - | - | - | - |
| `changelog_path.stat` | - | - | - | - |
| `HTTPException (src/api/skills.py:get_skill_changelog)` | - | - | - | - |
| `changelog_path.read_text` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| get_skill_changelog | _get_or_404 | 369 | `_get_or_404(skill_id)` |
| _get_or_404 | _registry.get | 181 | `_registry.get(skill_id)` |
| _get_or_404 | HTTPException (src/api/skills.py:_get_or_404) | 183 | `HTTPException(status_code=404, detail={...})` |
| get_skill_changelog | _skill_dir | 370 | `_skill_dir(skill_id)` |
| get_skill_changelog | changelog_path.is_file | 371 | `changelog_path.is_file(data not statically known)` |
| get_skill_changelog | changelog_path.stat | 373 | `changelog_path.stat(data not statically known)` |
| get_skill_changelog | HTTPException (src/api/skills.py:get_skill_changelog) | 375 | `HTTPException(status_code=413, detail={...})` |
| get_skill_changelog | changelog_path.read_text | 389 | `changelog_path.read_text(encoding='utf-8')` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_read | `changelog_path.read_text` | `get_skill_changelog` | 389 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `_get_or_404` | `_registry.get` | 181 |
| external_call | `_get_or_404` | `HTTPException` | 183 |
| unresolved_call | `get_skill_changelog` | `changelog_path.is_file` | 371 |
| unresolved_call | `get_skill_changelog` | `changelog_path.stat` | 373 |
| external_call | `get_skill_changelog` | `HTTPException` | 375 |

## Behavior

This flow starts at `get_skill_changelog` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
