# get_skill_support

**Entry point:** `get_skill_support` (`http`)
**Source:** [src_api_skills](../modules/src_api_skills.md)
**Modules touched:** [src_api_skills](../modules/src_api_skills.md), [support_matrix](../modules/support_matrix.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as get_skill_support
    participant p1 as support_descriptor
    participant p2 as _get_or_404
    participant p3 as toolchain_diagnostics
    participant p4 as validate_manifest_support
    participant p5 as _declared
    participant p6 as HTTPException
    participant p7 as _registry.get
    participant p8 as getattr (src/core/support_matrix.py:support_descriptor)
    participant p9 as getattr (src/core/support_matrix.py:validate_manifest_support)
    participant p10 as getattr (src/core/support_matrix.py:toolchain_diagnostics)
    participant p11 as reject
    participant p12 as str (src/core/support_matrix.py:validate_manifest_support)
    participant p13 as which
    participant p14 as out.append
    p0->>p1: support_descriptor
    p0->>p2: _get_or_404
    p1->>p3: toolchain_diagnostics
    p1->>p4: validate_manifest_support
    p3->>p5: _declared
    p2-->>p6: HTTPException(status_code=404, detail={...})
    p2-->>p7: _registry.get(skill_id)
    p1-->>p8: getattr (src/core/support_matrix.py:support_descriptor)(getattr(...), 'format', None)
    p1-->>p8: getattr (src/core/support_matrix.py:support_descriptor)(manifest, 'output_parser', None)
    p1-->>p8: getattr (src/core/support_matrix.py:support_descriptor)(getattr(...), 'goal', None)
    p1-->>p8: getattr (src/core/support_matrix.py:support_descriptor)(manifest, 'metric_schema', None)
    p1-->>p8: getattr (src/core/support_matrix.py:support_descriptor)(getattr(...), 'kind', None)
    p1-->>p8: getattr (src/core/support_matrix.py:support_descriptor)(getattr(...), 'primary', None)
    p1-->>p8: getattr (src/core/support_matrix.py:support_descriptor)(manifest, 'promotion_target', None)
    p4-->>p9: getattr (src/core/support_matrix.py:validate_manifest_support)(manifest, 'metric_schema', None)
    p3-->>p10: getattr (src/core/support_matrix.py:toolchain_diagnostics)(manifest, 'command_policy', None)
    p4-->>p9: getattr (src/core/support_matrix.py:validate_manifest_support)(metric_schema, 'goal', None)
    p4-->>p11: reject('metric_schema.goal', str(...), 'unsupported goal semantics', 'declare goal=optimize or goal=satisfice')
    p3-->>p10: getattr (src/core/support_matrix.py:toolchain_diagnostics)(policy, 'allowed_executables', None)
    p4-->>p12: str (src/core/support_matrix.py:validate_manifest_support)(goal)
    p3-->>p13: which(name)
    p4-->>p9: getattr (src/core/support_matrix.py:validate_manifest_support)(manifest, 'output_parser', None)
    p3-->>p14: out.append({...})
    p4-->>p9: getattr (src/core/support_matrix.py:validate_manifest_support)(output_parser, 'format', None)
    p4-->>p11: reject('output_parser.format', str(...), 'no parser handler implements this format', 'declare delimited_kv or json_marker')
    p3-->>p10: getattr (src/core/support_matrix.py:toolchain_diagnostics)(policy, 'allowed_python', None)
    p4-->>p12: str (src/core/support_matrix.py:validate_manifest_support)(fmt)
    p3-->>p14: out.append({...})
    p4-->>p9: getattr (src/core/support_matrix.py:validate_manifest_support)(manifest, 'promotion_target', None)
    p4-->>p9: getattr (src/core/support_matrix.py:validate_manifest_support)(promotion, 'primary', None)
```

> Call sequence diagram shows 30 of 55 interactions; 25 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 19 of 36 (17 omitted); unresolved 6 of 13 (7 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/support_matrix.py:validate_manifest_support` | 6 | - | external | 14 |
| `src/core/support_matrix.py:validate_manifest_support` | 6 | - | unresolved | 7 |
| `src/core/support_matrix.py:_declared` | 40 | - | external | 3 |
| `src/core/support_matrix.py:toolchain_diagnostics` | 38 | [src/core/support_matrix.py](../modules/support_matrix.md) | internal | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. get_skill_support"]
    s2["2. _get_or_404"]
    s3["3. _registry.get"]
    s4["4. HTTPException"]
    s5["5. support_descriptor"]
    s6["6. validate_manifest_support"]
    s7["7. getattr (src/core/support_matrix.py:validate_manifest_support)"]
    s8["8. getattr (src/core/support_matrix.py:validate_manifest_support)"]
    s9["9. reject"]
    s10["10. str (src/core/support_matrix.py:validate_manifest_support)"]
    s11["11. getattr (src/core/support_matrix.py:validate_manifest_support)"]
    s12["12. getattr (src/core/support_matrix.py:validate_manifest_support)"]
    s1 -->|"_get_or_404(skill_id)"| s2
    s2 -. "_registry.get(skill_id)" .-> s3
    s2 -. "HTTPException(status_code=404, detail={...})" .-> s4
    s1 -->|"support_descriptor(manifest)"| s5
    s5 -->|"validate_manifest_support(manifest)"| s6
    s6 -. "getattr (src/core/support_matrix.py:validate_manifest_support)(manifest, 'metric_schema', None)" .-> s7
    s6 -. "getattr (src/core/support_matrix.py:validate_manifest_support)(metric_schema, 'goal', None)" .-> s8
    s6 -. "reject('metric_schema.goal', str(...), 'unsupported goal semantics', 'declare goal=optimize or goal=satisfice')" .-> s9
    s6 -. "str (src/core/support_matrix.py:validate_manifest_support)(goal)" .-> s10
    s6 -. "getattr (src/core/support_matrix.py:validate_manifest_support)(manifest, 'output_parser', None)" .-> s11
    s6 -. "getattr (src/core/support_matrix.py:validate_manifest_support)(output_parser, 'format', None)" .-> s12
    click s1 "../modules/src_api_skills.md"
    click s2 "../modules/src_api_skills.md"
    click s5 "../modules/support_matrix.md"
    click s6 "../modules/support_matrix.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `get_skill_support` | `skill_id: str` | - | - | `support_descriptor(...)` |
| `_get_or_404` | `skill_id: str` | `SkillNotRegisteredError` | - | `_registry.get(...)` |
| `_registry.get` | - | - | - | - |
| `HTTPException` | - | - | - | - |
| `support_descriptor` | `manifest: Any`, `which: Any` | `SUPPORT_MATRIX`, `ACCEPTED_ADVISORY` | - | `{...}` |
| `validate_manifest_support` | `manifest: Any` | `SUPPORT_MATRIX`, `SUPPORT_MATRIX` | - | `diagnostics` |
| `getattr (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |
| `getattr (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |
| `reject` | - | - | - | - |
| `str (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |
| `getattr (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |
| `getattr (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| get_skill_support | _get_or_404 | 253 | `_get_or_404(skill_id)` |
| _get_or_404 | _registry.get | 188 | `_registry.get(skill_id)` |
| _get_or_404 | HTTPException | 190 | `HTTPException(status_code=404, detail={...})` |
| get_skill_support | support_descriptor | 256 | `support_descriptor(manifest)` |
| support_descriptor | validate_manifest_support | 179 | `validate_manifest_support(manifest)` |
| validate_manifest_support | getattr (src/core/support_matrix.py:validate_manifest_support) | 101 | `getattr(manifest, 'metric_schema', None)` |
| validate_manifest_support | getattr (src/core/support_matrix.py:validate_manifest_support) | 102 | `getattr(metric_schema, 'goal', None)` |
| validate_manifest_support | reject | 104 | `reject('metric_schema.goal', str(...), 'unsupported goal semantics', 'declare goal=optimize or goal=satisfice')` |
| validate_manifest_support | str (src/core/support_matrix.py:validate_manifest_support) | 104 | `str(goal)` |
| validate_manifest_support | getattr (src/core/support_matrix.py:validate_manifest_support) | 107 | `getattr(manifest, 'output_parser', None)` |
| validate_manifest_support | getattr (src/core/support_matrix.py:validate_manifest_support) | 108 | `getattr(output_parser, 'format', None)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `_get_or_404` | `_registry.get` | 188 |
| external_call | `_get_or_404` | `HTTPException` | 190 |
| external_call | `validate_manifest_support` | `getattr` | 101 |
| external_call | `validate_manifest_support` | `getattr` | 102 |
| unresolved_call | `validate_manifest_support` | `reject` | 104 |
| external_call | `validate_manifest_support` | `getattr` | 107 |
| external_call | `validate_manifest_support` | `getattr` | 108 |
| step_limit | `get_skill_support` | `first 12 steps` | 0 |

## Behavior

This flow starts at `get_skill_support` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
