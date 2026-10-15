# render_path_template

**Entry point:** `render_path_template` (`api`)
**Source:** [skill_paths](../modules/skill_paths.md)
**Modules touched:** [skill_paths](../modules/skill_paths.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as render_path_template
    participant p1 as validate_path_template
    participant p2 as sanitize_path_segment
    participant p3 as values.items
    participant p4 as rendered.replace
    participant p5 as template.strip
    participant p6 as any (src/core/skill_paths.py:sanitize_path_segment)
    participant p7 as ValueError (src/core/skill_paths.py:validate_path_template)
    participant p8 as ValueError (src/core/skill_paths.py:sanitize_path_segment)
    participant p9 as template.split
    participant p10 as any (src/core/skill_paths.py:validate_path_template)
    participant p11 as _template_placeholder_tokens
    participant p12 as sorted
    participant p13 as re.findall
    p0->>p1: validate_path_template
    p0->>p2: sanitize_path_segment
    p0->>p2: sanitize_path_segment
    p0->>p2: sanitize_path_segment
    p0-->>p3: values.items
    p0-->>p4: rendered.replace(..., value)
    p1-->>p5: template.strip
    p2-->>p6: any (src/core/skill_paths.py:sanitize_path_segment)(...)
    p1-->>p7: ValueError (src/core/skill_paths.py:validate_path_template)('path template must not be blank')
    p2-->>p8: ValueError (src/core/skill_paths.py:sanitize_path_segment)(...)
    p1-->>p7: ValueError (src/core/skill_paths.py:validate_path_template)(...)
    p1-->>p9: template.split('/')
    p1-->>p10: any (src/core/skill_paths.py:validate_path_template)(...)
    p1-->>p7: ValueError (src/core/skill_paths.py:validate_path_template)(...)
    p1->>p11: _template_placeholder_tokens
    p1-->>p7: ValueError (src/core/skill_paths.py:validate_path_template)(...)
    p1-->>p7: ValueError (src/core/skill_paths.py:validate_path_template)(...)
    p1-->>p12: sorted(PATH_TEMPLATE_PLACEHOLDERS)
    p11-->>p13: re.findall('\\{([A-Za-z_][A-Za-z0-9_]*)\\}', template)
```

> Call sequence diagram shows 19 of 19 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 10 of 10 (0 omitted); unresolved 4 of 4 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. render_path_template"]
    s2["2. validate_path_template"]
    s3["3. template.strip"]
    s4["4. ValueError (src/core/skill_paths.py:validate_path_template)"]
    s5["5. ValueError (src/core/skill_paths.py:validate_path_template)"]
    s6["6. template.split"]
    s7["7. any (src/core/skill_paths.py:validate_path_template)"]
    s8["8. ValueError (src/core/skill_paths.py:validate_path_template)"]
    s9["9. _template_placeholder_tokens"]
    s10["10. re.findall"]
    s11["11. ValueError (src/core/skill_paths.py:validate_path_template)"]
    s12["12. ValueError (src/core/skill_paths.py:validate_path_template)"]
    s1 -->|"validate_path_template(template)"| s2
    s2 -. "template.strip(data not statically known)" .-> s3
    s2 -. "ValueError (src/core/skill_paths.py:validate_path_template)('path template must not be blank')" .-> s4
    s2 -. "ValueError (src/core/skill_paths.py:validate_path_template)(...)" .-> s5
    s2 -. "template.split('/')" .-> s6
    s2 -. "any (src/core/skill_paths.py:validate_path_template)(...)" .-> s7
    s2 -. "ValueError (src/core/skill_paths.py:validate_path_template)(...)" .-> s8
    s2 -->|"_template_placeholder_tokens(template)"| s9
    s9 -. "re.findall('\\{([A-Za-z_][A-Za-z0-9_]*)\\}', template)" .-> s10
    s2 -. "ValueError (src/core/skill_paths.py:validate_path_template)(...)" .-> s11
    s2 -. "ValueError (src/core/skill_paths.py:validate_path_template)(...)" .-> s12
    click s1 "../modules/skill_paths.md"
    click s2 "../modules/skill_paths.md"
    click s9 "../modules/skill_paths.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `render_path_template` | `template: str`, `skill_id: str`, `subject_id: str`, `variant: str` | - | - | `rendered` |
| `validate_path_template` | `template: str`, `allowed: frozenset[str]` | `PATH_TEMPLATE_PLACEHOLDERS`, `PATH_TEMPLATE_PLACEHOLDERS` | - | - |
| `template.strip` | - | - | - | - |
| `ValueError (src/core/skill_paths.py:validate_path_template)` | - | - | - | - |
| `ValueError (src/core/skill_paths.py:validate_path_template)` | - | - | - | - |
| `template.split` | - | - | - | - |
| `any (src/core/skill_paths.py:validate_path_template)` | - | - | - | - |
| `ValueError (src/core/skill_paths.py:validate_path_template)` | - | - | - | - |
| `_template_placeholder_tokens` | `template: str` | - | - | `re.findall(...)` |
| `re.findall` | - | - | - | - |
| `ValueError (src/core/skill_paths.py:validate_path_template)` | - | - | - | - |
| `ValueError (src/core/skill_paths.py:validate_path_template)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| render_path_template | validate_path_template | 104 | `validate_path_template(template)` |
| validate_path_template | template.strip | 69 | `template.strip(data not statically known)` |
| validate_path_template | ValueError (src/core/skill_paths.py:validate_path_template) | 70 | `ValueError('path template must not be blank')` |
| validate_path_template | ValueError (src/core/skill_paths.py:validate_path_template) | 72 | `ValueError(...)` |
| validate_path_template | template.split | 75 | `template.split('/')` |
| validate_path_template | any (src/core/skill_paths.py:validate_path_template) | 76 | `any(...)` |
| validate_path_template | ValueError (src/core/skill_paths.py:validate_path_template) | 77 | `ValueError(...)` |
| validate_path_template | _template_placeholder_tokens | 78 | `_template_placeholder_tokens(template)` |
| _template_placeholder_tokens | re.findall | 119 | `re.findall('\\{([A-Za-z_][A-Za-z0-9_]*)\\}', template)` |
| validate_path_template | ValueError (src/core/skill_paths.py:validate_path_template) | 81 | `ValueError(...)` |
| validate_path_template | ValueError (src/core/skill_paths.py:validate_path_template) | 85 | `ValueError(...)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `validate_path_template` | `template.strip` | 69 |
| external_call | `validate_path_template` | `ValueError` | 70 |
| external_call | `validate_path_template` | `ValueError` | 72 |
| unresolved_call | `validate_path_template` | `template.split` | 75 |
| external_call | `validate_path_template` | `any` | 76 |
| external_call | `validate_path_template` | `ValueError` | 77 |
| external_call | `_template_placeholder_tokens` | `re.findall` | 119 |
| external_call | `validate_path_template` | `ValueError` | 81 |
| external_call | `validate_path_template` | `ValueError` | 85 |
| step_limit | `render_path_template` | `first 12 steps` | 0 |

## Behavior

This flow starts at `render_path_template` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
