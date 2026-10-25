# validate_manifest_support

**Entry point:** `validate_manifest_support` (`api`)
**Source:** [support_matrix](../modules/support_matrix.md)
**Modules touched:** [support_matrix](../modules/support_matrix.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as validate_manifest_support
    participant p1 as getattr
    participant p2 as reject
    participant p3 as str
    participant p4 as SUPPORT_MATRIX[…].get (src/core/support_matrix.p…lidate_manifest_support, 1)
    participant p5 as SUPPORT_MATRIX[…].get (src/core/support_matrix.p…lidate_manifest_support, 2)
    participant p6 as SUPPORT_MATRIX[…].get (src/core/support_matrix.py:validate_manifest_support)
    p0-->>p1: getattr(manifest, 'metric_schema', None)
    p0-->>p1: getattr(metric_schema, 'goal', None)
    p0-->>p2: reject('metric_schema.goal', str(...), 'unsupported goal semantics', 'declare goal=optimize or goal=satisfice')
    p0-->>p3: str(goal)
    p0-->>p1: getattr(manifest, 'output_parser', None)
    p0-->>p1: getattr(output_parser, 'format', None)
    p0-->>p2: reject('output_parser.format', str(...), 'no parser handler implements this format', 'declare delimited_kv or json_marker')
    p0-->>p3: str(fmt)
    p0-->>p1: getattr(manifest, 'promotion_target', None)
    p0-->>p1: getattr(promotion, 'primary', None)
    p0-->>p1: getattr(primary, 'kind', None)
    p0-->>p4: SUPPORT_MATRIX[…].get (src/core/support_matrix.p…lidate_manifest_support, 1)('rejected', {...})
    p0-->>p2: reject('promotion_target.kind', str(...), rejected_kinds[...], 'use file_path, registry_api, or webhook until the target is qualified')
    p0-->>p3: str(kind)
    p0-->>p1: getattr(manifest, 'trial_identity', None)
    p0-->>p1: getattr(trial_identity, 'resolve', None)
    p0-->>p1: getattr(resolve, 'mode', None)
    p0-->>p5: SUPPORT_MATRIX[…].get (src/core/support_matrix.p…lidate_manifest_support, 2)('rejected', {...})
    p0-->>p2: reject('trial_identity.resolve.mode', str(...), rejected_modes[...], 'declare mode=declarative with hash_fields')
    p0-->>p3: str(mode)
    p0-->>p1: getattr(manifest, 'phase_advancement', None)
    p0-->>p1: getattr(advancement, 'mode', None)
    p0-->>p6: SUPPORT_MATRIX[…].get (src/core/support_matrix.py:validate_manifest_support)('rejected', {...})
    p0-->>p2: reject('phase_advancement.mode', str(...), rejected_adv[...], 'declare mode=declarative with per-phase evidence_keys')
    p0-->>p3: str(adv_mode)
    p0-->>p1: getattr(manifest, 'phase_plan', None)
    p0-->>p1: getattr(phase, 'advancement', None)
    p0-->>p1: getattr(override, 'mode', None)
    p0-->>p2: reject(..., str(...), rejected_adv[...], 'declare mode=declarative with evidence_keys')
    p0-->>p1: getattr(phase, 'id', '?')
```

> Call sequence diagram shows 30 of 31 interactions; 1 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 21 of 22 (1 omitted); unresolved 9 of 9 (0 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/support_matrix.py:validate_manifest_support` | 1 | - | external | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. validate_manifest_support"]
    s2["2. getattr"]
    s3["3. getattr"]
    s4["4. reject"]
    s5["5. str"]
    s6["6. getattr"]
    s7["7. getattr"]
    s8["8. reject"]
    s9["9. str"]
    s10["10. getattr"]
    s11["11. getattr"]
    s12["12. getattr"]
    s1 -. "getattr(manifest, 'metric_schema', None)" .-> s2
    s1 -. "getattr(metric_schema, 'goal', None)" .-> s3
    s1 -. "reject('metric_schema.goal', str(...), 'unsupported goal semantics', 'declare goal=optimize or goal=satisfice')" .-> s4
    s1 -. "str(goal)" .-> s5
    s1 -. "getattr(manifest, 'output_parser', None)" .-> s6
    s1 -. "getattr(output_parser, 'format', None)" .-> s7
    s1 -. "reject('output_parser.format', str(...), 'no parser handler implements this format', 'declare delimited_kv or json_marker')" .-> s8
    s1 -. "str(fmt)" .-> s9
    s1 -. "getattr(manifest, 'promotion_target', None)" .-> s10
    s1 -. "getattr(promotion, 'primary', None)" .-> s11
    s1 -. "getattr(primary, 'kind', None)" .-> s12
    click s1 "../modules/support_matrix.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `validate_manifest_support` | `manifest: Any` | `SUPPORT_MATRIX`, `SUPPORT_MATRIX` | - | `diagnostics` |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |
| `reject` | - | - | - | - |
| `str` | - | - | - | - |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |
| `reject` | - | - | - | - |
| `str` | - | - | - | - |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| validate_manifest_support | getattr | 101 | `getattr(manifest, 'metric_schema', None)` |
| validate_manifest_support | getattr | 102 | `getattr(metric_schema, 'goal', None)` |
| validate_manifest_support | reject | 104 | `reject('metric_schema.goal', str(...), 'unsupported goal semantics', 'declare goal=optimize or goal=satisfice')` |
| validate_manifest_support | str | 104 | `str(goal)` |
| validate_manifest_support | getattr | 107 | `getattr(manifest, 'output_parser', None)` |
| validate_manifest_support | getattr | 108 | `getattr(output_parser, 'format', None)` |
| validate_manifest_support | reject | 110 | `reject('output_parser.format', str(...), 'no parser handler implements this format', 'declare delimited_kv or json_marker')` |
| validate_manifest_support | str | 110 | `str(fmt)` |
| validate_manifest_support | getattr | 113 | `getattr(manifest, 'promotion_target', None)` |
| validate_manifest_support | getattr | 114 | `getattr(promotion, 'primary', None)` |
| validate_manifest_support | getattr | 115 | `getattr(primary, 'kind', None)` |

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
| external_call | `validate_manifest_support` | `getattr` | 115 |
| step_limit | `validate_manifest_support` | `first 12 steps` | 0 |

## Behavior

This flow starts at `validate_manifest_support` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
