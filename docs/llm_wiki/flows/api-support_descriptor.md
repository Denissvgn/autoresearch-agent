# support_descriptor

**Entry point:** `support_descriptor` (`api`)
**Source:** [support_matrix](../modules/support_matrix.md)
**Modules touched:** [support_matrix](../modules/support_matrix.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as support_descriptor
    participant p1 as toolchain_diagnostics
    participant p2 as validate_manifest_support
    participant p3 as _declared
    participant p4 as getattr (src/core/support_matrix.py:support_descriptor)
    participant p5 as reject
    participant p6 as getattr (src/core/support_matrix.py:validate_manifest_support)
    participant p7 as getattr (src/core/support_matrix.py:toolchain_diagnostics)
    participant p8 as str (src/core/support_matrix.py:validate_manifest_support)
    participant p9 as which
    participant p10 as out.append
    participant p11 as SUPPORT_MATRIX[…].get (src/core/support_matrix.p…lidate_manifest_support, 1)
    p0->>p1: toolchain_diagnostics
    p0->>p2: validate_manifest_support
    p1->>p3: _declared
    p0-->>p4: getattr (src/core/support_matrix.py:support_descriptor)(getattr(...), 'format', None)
    p2-->>p5: reject('metric_schema.goal', str(...), 'unsupported goal semantics', 'declare goal=optimize or goal=satisfice')
    p0-->>p4: getattr (src/core/support_matrix.py:support_descriptor)(manifest, 'output_parser', None)
    p0-->>p4: getattr (src/core/support_matrix.py:support_descriptor)(getattr(...), 'goal', None)
    p0-->>p4: getattr (src/core/support_matrix.py:support_descriptor)(manifest, 'metric_schema', None)
    p0-->>p4: getattr (src/core/support_matrix.py:support_descriptor)(getattr(...), 'kind', None)
    p0-->>p4: getattr (src/core/support_matrix.py:support_descriptor)(getattr(...), 'primary', None)
    p0-->>p4: getattr (src/core/support_matrix.py:support_descriptor)(manifest, 'promotion_target', None)
    p2-->>p6: getattr (src/core/support_matrix.py:validate_manifest_support)(manifest, 'metric_schema', None)
    p1-->>p7: getattr (src/core/support_matrix.py:toolchain_diagnostics)(manifest, 'command_policy', None)
    p2-->>p6: getattr (src/core/support_matrix.py:validate_manifest_support)(metric_schema, 'goal', None)
    p1-->>p7: getattr (src/core/support_matrix.py:toolchain_diagnostics)(policy, 'allowed_executables', None)
    p2-->>p8: str (src/core/support_matrix.py:validate_manifest_support)(goal)
    p1-->>p9: which(name)
    p2-->>p6: getattr (src/core/support_matrix.py:validate_manifest_support)(manifest, 'output_parser', None)
    p1-->>p10: out.append({...})
    p2-->>p6: getattr (src/core/support_matrix.py:validate_manifest_support)(output_parser, 'format', None)
    p2-->>p5: reject('output_parser.format', str(...), 'no parser handler implements this format', 'declare delimited_kv or json_marker')
    p1-->>p7: getattr (src/core/support_matrix.py:toolchain_diagnostics)(policy, 'allowed_python', None)
    p2-->>p8: str (src/core/support_matrix.py:validate_manifest_support)(fmt)
    p1-->>p10: out.append({...})
    p2-->>p6: getattr (src/core/support_matrix.py:validate_manifest_support)(manifest, 'promotion_target', None)
    p2-->>p6: getattr (src/core/support_matrix.py:validate_manifest_support)(promotion, 'primary', None)
    p2-->>p6: getattr (src/core/support_matrix.py:validate_manifest_support)(primary, 'kind', None)
    p2-->>p11: SUPPORT_MATRIX[…].get (src/core/support_matrix.p…lidate_manifest_support, 1)('rejected', {...})
    p2-->>p5: reject('promotion_target.kind', str(...), rejected_kinds[...], 'use file_path, registry_api, or webhook until the target is qualified')
    p2-->>p8: str (src/core/support_matrix.py:validate_manifest_support)(kind)
```

> Call sequence diagram shows 30 of 51 interactions; 21 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 20 of 35 (15 omitted); unresolved 7 of 12 (5 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/support_matrix.py:validate_manifest_support` | 2 | - | external | 12 |
| `src/core/support_matrix.py:validate_manifest_support` | 2 | - | unresolved | 5 |
| `src/core/support_matrix.py:_declared` | 36 | - | external | 3 |
| `src/core/support_matrix.py:toolchain_diagnostics` | 34 | [src/core/support_matrix.py](../modules/support_matrix.md) | internal | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. support_descriptor"]
    s2["2. validate_manifest_support"]
    s3["3. getattr (src/core/support_matrix.py:validate_manifest_support)"]
    s4["4. getattr (src/core/support_matrix.py:validate_manifest_support)"]
    s5["5. reject"]
    s6["6. str (src/core/support_matrix.py:validate_manifest_support)"]
    s7["7. getattr (src/core/support_matrix.py:validate_manifest_support)"]
    s8["8. getattr (src/core/support_matrix.py:validate_manifest_support)"]
    s9["9. reject"]
    s10["10. str (src/core/support_matrix.py:validate_manifest_support)"]
    s11["11. getattr (src/core/support_matrix.py:validate_manifest_support)"]
    s12["12. getattr (src/core/support_matrix.py:validate_manifest_support)"]
    s1 -->|"validate_manifest_support(manifest)"| s2
    s2 -. "getattr (src/core/support_matrix.py:validate_manifest_support)(manifest, 'metric_schema', None)" .-> s3
    s2 -. "getattr (src/core/support_matrix.py:validate_manifest_support)(metric_schema, 'goal', None)" .-> s4
    s2 -. "reject('metric_schema.goal', str(...), 'unsupported goal semantics', 'declare goal=optimize or goal=satisfice')" .-> s5
    s2 -. "str (src/core/support_matrix.py:validate_manifest_support)(goal)" .-> s6
    s2 -. "getattr (src/core/support_matrix.py:validate_manifest_support)(manifest, 'output_parser', None)" .-> s7
    s2 -. "getattr (src/core/support_matrix.py:validate_manifest_support)(output_parser, 'format', None)" .-> s8
    s2 -. "reject('output_parser.format', str(...), 'no parser handler implements this format', 'declare delimited_kv or json_marker')" .-> s9
    s2 -. "str (src/core/support_matrix.py:validate_manifest_support)(fmt)" .-> s10
    s2 -. "getattr (src/core/support_matrix.py:validate_manifest_support)(manifest, 'promotion_target', None)" .-> s11
    s2 -. "getattr (src/core/support_matrix.py:validate_manifest_support)(promotion, 'primary', None)" .-> s12
    click s1 "../modules/support_matrix.md"
    click s2 "../modules/support_matrix.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `support_descriptor` | `manifest: Any`, `which: Any` | `SUPPORT_MATRIX`, `ACCEPTED_ADVISORY` | - | `{...}` |
| `validate_manifest_support` | `manifest: Any` | `SUPPORT_MATRIX`, `SUPPORT_MATRIX` | - | `diagnostics` |
| `getattr (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |
| `getattr (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |
| `reject` | - | - | - | - |
| `str (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |
| `getattr (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |
| `getattr (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |
| `reject` | - | - | - | - |
| `str (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |
| `getattr (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |
| `getattr (src/core/support_matrix.py:validate_manifest_support)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| support_descriptor | validate_manifest_support | 179 | `validate_manifest_support(manifest)` |
| validate_manifest_support | getattr (src/core/support_matrix.py:validate_manifest_support) | 101 | `getattr(manifest, 'metric_schema', None)` |
| validate_manifest_support | getattr (src/core/support_matrix.py:validate_manifest_support) | 102 | `getattr(metric_schema, 'goal', None)` |
| validate_manifest_support | reject | 104 | `reject('metric_schema.goal', str(...), 'unsupported goal semantics', 'declare goal=optimize or goal=satisfice')` |
| validate_manifest_support | str (src/core/support_matrix.py:validate_manifest_support) | 104 | `str(goal)` |
| validate_manifest_support | getattr (src/core/support_matrix.py:validate_manifest_support) | 107 | `getattr(manifest, 'output_parser', None)` |
| validate_manifest_support | getattr (src/core/support_matrix.py:validate_manifest_support) | 108 | `getattr(output_parser, 'format', None)` |
| validate_manifest_support | reject | 110 | `reject('output_parser.format', str(...), 'no parser handler implements this format', 'declare delimited_kv or json_marker')` |
| validate_manifest_support | str (src/core/support_matrix.py:validate_manifest_support) | 110 | `str(fmt)` |
| validate_manifest_support | getattr (src/core/support_matrix.py:validate_manifest_support) | 113 | `getattr(manifest, 'promotion_target', None)` |
| validate_manifest_support | getattr (src/core/support_matrix.py:validate_manifest_support) | 114 | `getattr(promotion, 'primary', None)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `validate_manifest_support` | `getattr` | 101 |
| external_call | `validate_manifest_support` | `getattr` | 102 |
| unresolved_call | `validate_manifest_support` | `reject` | 104 |
| external_call | `validate_manifest_support` | `getattr` | 107 |
| external_call | `validate_manifest_support` | `getattr` | 108 |
| unresolved_call | `validate_manifest_support` | `reject` | 110 |
| external_call | `validate_manifest_support` | `getattr` | 113 |
| external_call | `validate_manifest_support` | `getattr` | 114 |
| step_limit | `support_descriptor` | `first 12 steps` | 0 |

## Behavior

This flow starts at `support_descriptor` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
