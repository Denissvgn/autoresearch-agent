# list_subjects

**Entry point:** `list_subjects` (`http`)
**Source:** [subjects](../modules/subjects.md)
**Modules touched:** [subjects](../modules/subjects.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as list_subjects
    participant p1 as _get_manifest_or_404
    participant p2 as _enumerate_subjects
    participant p3 as _registry.get
    participant p4 as HTTPException
    p0->>p1: _get_manifest_or_404
    p0->>p2: _enumerate_subjects
    p1-->>p3: _registry.get(skill_id)
    p1-->>p4: HTTPException(status_code=404, detail={...})
```

> Call sequence diagram shows 4 of 4 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 1 of 1 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. list_subjects"]
    s2["2. _get_manifest_or_404"]
    s3["3. _registry.get"]
    s4["4. HTTPException"]
    s5["5. _enumerate_subjects"]
    s1 -->|"_get_manifest_or_404(skill_id)"| s2
    s2 -. "_registry.get(skill_id)" .-> s3
    s2 -. "HTTPException(status_code=404, detail={...})" .-> s4
    s1 -->|"_enumerate_subjects(manifest)"| s5
    click s1 "../modules/subjects.md"
    click s2 "../modules/subjects.md"
    click s5 "../modules/subjects.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `list_subjects` | `skill_id: str` | - | - | `_enumerate_subjects(...)` |
| `_get_manifest_or_404` | `skill_id: str` | `SkillNotRegisteredError` | - | `_registry.get(...)` |
| `_registry.get` | - | - | - | - |
| `HTTPException` | - | - | - | - |
| `_enumerate_subjects` | `manifest: ResearchSkillManifest` | - | - | `[...]`, `...`, `[...]` |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| list_subjects | _get_manifest_or_404 | 105 | `_get_manifest_or_404(skill_id)` |
| _get_manifest_or_404 | _registry.get | 57 | `_registry.get(skill_id)` |
| _get_manifest_or_404 | HTTPException | 59 | `HTTPException(status_code=404, detail={...})` |
| list_subjects | _enumerate_subjects | 106 | `_enumerate_subjects(manifest)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `_get_manifest_or_404` | `_registry.get` | 57 |
| external_call | `_get_manifest_or_404` | `HTTPException` | 59 |

## Behavior

This flow starts at `list_subjects` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
