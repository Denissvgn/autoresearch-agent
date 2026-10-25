# session_workspace_path

**Entry point:** `session_workspace_path` (`api`)
**Source:** [skill_paths](../modules/skill_paths.md)
**Modules touched:** [skill_paths](../modules/skill_paths.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as session_workspace_path
    participant p1 as getattr
    participant p2 as render_path_template
    participant p3 as sanitize_path_segment
    participant p4 as validate_path_template
    participant p5 as values.items
    participant p6 as rendered.replace
    participant p7 as template.strip
    participant p8 as any (src/core/skill_paths.py:sanitize_path_segment)
    participant p9 as ValueError (src/core/skill_paths.py:validate_path_template)
    participant p10 as ValueError (src/core/skill_paths.py:sanitize_path_segment)
    participant p11 as template.split
    participant p12 as any (src/core/skill_paths.py:validate_path_template)
    participant p13 as _template_placeholder_tokens
    participant p14 as sorted
    participant p15 as re.findall
    p0-->>p1: getattr(getattr(...), 'session_path_template', None)
    p0-->>p1: getattr(skill_manifest, 'workspace', None)
    p0->>p2: render_path_template
    p0->>p3: sanitize_path_segment
    p2->>p4: validate_path_template
    p2->>p3: sanitize_path_segment
    p2->>p3: sanitize_path_segment
    p2->>p3: sanitize_path_segment
    p2-->>p5: values.items
    p2-->>p6: rendered.replace(..., value)
    p4-->>p7: template.strip
    p3-->>p8: any (src/core/skill_paths.py:sanitize_path_segment)(...)
    p4-->>p9: ValueError (src/core/skill_paths.py:validate_path_template)('path template must not be blank')
    p3-->>p10: ValueError (src/core/skill_paths.py:sanitize_path_segment)(...)
    p4-->>p9: ValueError (src/core/skill_paths.py:validate_path_template)(...)
    p4-->>p11: template.split('/')
    p4-->>p12: any (src/core/skill_paths.py:validate_path_template)(...)
    p4-->>p9: ValueError (src/core/skill_paths.py:validate_path_template)(...)
    p4->>p13: _template_placeholder_tokens
    p4-->>p9: ValueError (src/core/skill_paths.py:validate_path_template)(...)
    p4-->>p9: ValueError (src/core/skill_paths.py:validate_path_template)(...)
    p4-->>p14: sorted(PATH_TEMPLATE_PLACEHOLDERS)
    p13-->>p15: re.findall('\\{([A-Za-z_][A-Za-z0-9_]*)\\}', template)
```

> Call sequence diagram shows 23 of 23 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 12 of 12 (0 omitted); unresolved 4 of 4 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. session_workspace_path"]
    s2["2. getattr"]
    s3["3. getattr"]
    s4["4. render_path_template"]
    s5["5. validate_path_template"]
    s6["6. template.strip"]
    s7["7. ValueError (src/core/skill_paths.py:validate_path_template)"]
    s8["8. ValueError (src/core/skill_paths.py:validate_path_template)"]
    s9["9. template.split"]
    s10["10. any (src/core/skill_paths.py:validate_path_template)"]
    s11["11. ValueError (src/core/skill_paths.py:validate_path_template)"]
    s12["12. _template_placeholder_tokens"]
    s1 -. "getattr(getattr(...), 'session_path_template', None)" .-> s2
    s1 -. "getattr(skill_manifest, 'workspace', None)" .-> s3
    s1 -->|"render_path_template(template, skill_id=skill_id, subject_id=subject_id, variant=variant)"| s4
    s4 -->|"validate_path_template(template)"| s5
    s5 -. "template.strip(data not statically known)" .-> s6
    s5 -. "ValueError (src/core/skill_paths.py:validate_path_template)('path template must not be blank')" .-> s7
    s5 -. "ValueError (src/core/skill_paths.py:validate_path_template)(...)" .-> s8
    s5 -. "template.split('/')" .-> s9
    s5 -. "any (src/core/skill_paths.py:validate_path_template)(...)" .-> s10
    s5 -. "ValueError (src/core/skill_paths.py:validate_path_template)(...)" .-> s11
    s5 -->|"_template_placeholder_tokens(template)"| s12
    click s1 "../modules/skill_paths.md"
    click s4 "../modules/skill_paths.md"
    click s5 "../modules/skill_paths.md"
    click s12 "../modules/skill_paths.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `session_workspace_path` | `skill_manifest: Any`, `skill_id: str`, `subject_id: str`, `variant: str`, `research_id: Optional[str]` | - | - | `None`, `rendered` |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |
| `render_path_template` | `template: str`, `skill_id: str`, `subject_id: str`, `variant: str` | - | - | `rendered` |
| `validate_path_template` | `template: str`, `allowed: frozenset[str]` | `PATH_TEMPLATE_PLACEHOLDERS`, `PATH_TEMPLATE_PLACEHOLDERS` | - | - |
| `template.strip` | - | - | - | - |
| `ValueError (src/core/skill_paths.py:validate_path_template)` | - | - | - | - |
| `ValueError (src/core/skill_paths.py:validate_path_template)` | - | - | - | - |
| `template.split` | - | - | - | - |
| `any (src/core/skill_paths.py:validate_path_template)` | - | - | - | - |
| `ValueError (src/core/skill_paths.py:validate_path_template)` | - | - | - | - |
| `_template_placeholder_tokens` | `template: str` | - | - | `re.findall(...)` |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| session_workspace_path | getattr | 142 | `getattr(getattr(...), 'session_path_template', None)` |
| session_workspace_path | getattr | 143 | `getattr(skill_manifest, 'workspace', None)` |
| session_workspace_path | render_path_template | 147 | `render_path_template(template, skill_id=skill_id, subject_id=subject_id, variant=variant)` |
| render_path_template | validate_path_template | 104 | `validate_path_template(template)` |
| validate_path_template | template.strip | 69 | `template.strip(data not statically known)` |
| validate_path_template | ValueError (src/core/skill_paths.py:validate_path_template) | 70 | `ValueError('path template must not be blank')` |
| validate_path_template | ValueError (src/core/skill_paths.py:validate_path_template) | 72 | `ValueError(...)` |
| validate_path_template | template.split | 75 | `template.split('/')` |
| validate_path_template | any (src/core/skill_paths.py:validate_path_template) | 76 | `any(...)` |
| validate_path_template | ValueError (src/core/skill_paths.py:validate_path_template) | 77 | `ValueError(...)` |
| validate_path_template | _template_placeholder_tokens | 78 | `_template_placeholder_tokens(template)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `session_workspace_path` | `getattr` | 142 |
| external_call | `session_workspace_path` | `getattr` | 143 |
| unresolved_call | `validate_path_template` | `template.strip` | 69 |
| external_call | `validate_path_template` | `ValueError` | 70 |
| external_call | `validate_path_template` | `ValueError` | 72 |
| unresolved_call | `validate_path_template` | `template.split` | 75 |
| external_call | `validate_path_template` | `any` | 76 |
| external_call | `validate_path_template` | `ValueError` | 77 |
| step_limit | `session_workspace_path` | `first 12 steps` | 0 |

## Behavior

This flow starts at `session_workspace_path` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
