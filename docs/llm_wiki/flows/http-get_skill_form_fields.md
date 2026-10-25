# get_skill_form_fields

**Entry point:** `get_skill_form_fields` (`http`)
**Source:** [src_api_skills](../modules/src_api_skills.md)
**Modules touched:** [src_api_skills](../modules/src_api_skills.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as get_skill_form_fields
    participant p1 as _get_or_404
    participant p2 as _form_fields
    participant p3 as _registry.get
    participant p4 as list
    participant p5 as HTTPException
    participant p6 as manifest.param_schema.properties.items
    participant p7 as prop.model_dump
    participant p8 as {'minimum': 'min', 'maximum': 'max'}.get
    participant p9 as fields.append
    p0->>p1: _get_or_404
    p0->>p2: _form_fields
    p1-->>p3: _registry.get(skill_id)
    p2-->>p4: list(manifest.ui.form_fields)
    p1-->>p5: HTTPException(status_code=404, detail={...})
    p2-->>p6: manifest.param_schema.properties.items
    p2-->>p7: prop.model_dump(exclude_none=True)
    p2-->>p8: {'minimum': 'min', 'maximum': 'max'}.get(bound_key, bound_key)
    p2-->>p9: fields.append(field)
```

> Call sequence diagram shows 9 of 9 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 2 of 2 (0 omitted); unresolved 5 of 5 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. get_skill_form_fields"]
    s2["2. _get_or_404"]
    s3["3. _registry.get"]
    s4["4. HTTPException"]
    s5["5. _form_fields"]
    s6["6. list"]
    s7["7. manifest.param_schema.properties.items"]
    s8["8. prop.model_dump"]
    s9["9. {'minimum': 'min', 'maximum': 'max'}.get"]
    s10["10. fields.append"]
    s1 -->|"_get_or_404(skill_id)"| s2
    s2 -. "_registry.get(skill_id)" .-> s3
    s2 -. "HTTPException(status_code=404, detail={...})" .-> s4
    s1 -->|"_form_fields(manifest)"| s5
    s5 -. "list(manifest.ui.form_fields)" .-> s6
    s5 -. "manifest.param_schema.properties.items(data not statically known)" .-> s7
    s5 -. "prop.model_dump(exclude_none=True)" .-> s8
    s5 -. "{'minimum': 'min', 'maximum': 'max'}.get(bound_key, bound_key)" .-> s9
    s5 -. "fields.append(field)" .-> s10
    b0["mutation fields.append"]
    s5 -. "mutation fields.append" .-> b0
    click s1 "../modules/src_api_skills.md"
    click s2 "../modules/src_api_skills.md"
    click s5 "../modules/src_api_skills.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `get_skill_form_fields` | `skill_id: str` | - | - | `{...}` |
| `_get_or_404` | `skill_id: str` | `SkillNotRegisteredError` | - | `_registry.get(...)` |
| `_registry.get` | - | - | - | - |
| `HTTPException` | - | - | - | - |
| `_form_fields` | `manifest: ResearchSkillManifest` | - | `field[...]`, `field[...]`, `field[...]` | `list(...)`, `fields` |
| `list` | - | - | - | - |
| `manifest.param_schema.properties.items` | - | - | - | - |
| `prop.model_dump` | - | - | - | - |
| `{'minimum': 'min', 'maximum': 'max'}.get` | - | - | - | - |
| `fields.append` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| get_skill_form_fields | _get_or_404 | 240 | `_get_or_404(skill_id)` |
| _get_or_404 | _registry.get | 188 | `_registry.get(skill_id)` |
| _get_or_404 | HTTPException | 190 | `HTTPException(status_code=404, detail={...})` |
| get_skill_form_fields | _form_fields | 241 | `_form_fields(manifest)` |
| _form_fields | list | 137 | `list(manifest.ui.form_fields)` |
| _form_fields | manifest.param_schema.properties.items | 141 | `manifest.param_schema.properties.items(data not statically known)` |
| _form_fields | prop.model_dump | 151 | `prop.model_dump(exclude_none=True)` |
| _form_fields | {'minimum': 'min', 'maximum': 'max'}.get | 154 | `{'minimum': 'min', 'maximum': 'max'}.get(bound_key, bound_key)` |
| _form_fields | fields.append | 156 | `fields.append(field)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `fields.append` | `_form_fields` | 156 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `_get_or_404` | `_registry.get` | 188 |
| external_call | `_get_or_404` | `HTTPException` | 190 |
| unresolved_call | `_form_fields` | `manifest.param_schema.properties.items` | 141 |
| unresolved_call | `_form_fields` | `prop.model_dump` | 151 |
| unresolved_call | `_form_fields` | `{'minimum': 'min', 'maximum': 'max'}.get` | 154 |

## Behavior

This flow starts at `get_skill_form_fields` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
