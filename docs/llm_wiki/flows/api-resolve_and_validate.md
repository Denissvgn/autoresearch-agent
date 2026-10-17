# resolve_and_validate

**Entry point:** `resolve_and_validate` (`api`)
**Source:** [skill_params](../modules/skill_params.md)
**Modules touched:** [skill_params](../modules/skill_params.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as resolve_and_validate
    participant p1 as apply_defaults
    participant p2 as validate_resolved
    participant p3 as _apply_defaults_at
    participant p4 as schema_to_json_schema
    participant p5 as _field_address
    participant p6 as Draft202012Validator
    participant p7 as document.get
    participant p8 as dict (src/core/skill_params.py:apply_defaults)
    participant p9 as violations.append
    participant p10 as sorted
    participant p11 as validator.iter_errors
    participant p12 as dict (src/core/skill_params.py:validate_resolved)
    participant p13 as list (src/core/skill_params.py:validate_resolved)
    participant p14 as isinstance (src/core/skill_params.py:schema_to_json_schema)
    participant p15 as dict (src/core/skill_params.py:_apply_defaults_at)
    participant p16 as isinstance (src/core/skill_params.py:_field_address)
    participant p17 as dict (src/core/skill_params.py:schema_to_json_schema)
    participant p18 as node.get
    participant p19 as parts.append
    participant p20 as getattr
    participant p21 as properties.items (src/core/skill_params.py:_apply_defaults_at)
    participant p22 as bool
    participant p23 as isinstance (src/core/skill_params.py:_apply_defaults_at)
    participant p24 as ''.join
    p0->>p1: apply_defaults
    p0->>p2: validate_resolved
    p1->>p3: _apply_defaults_at
    p1->>p4: schema_to_json_schema
    p2->>p5: _field_address
    p2-->>p6: Draft202012Validator(document)
    p2-->>p7: document.get('properties')
    p1-->>p8: dict (src/core/skill_params.py:apply_defaults)(...)
    p2-->>p7: document.get('additionalProperties')
    p2-->>p9: violations.append({...})
    p2-->>p10: sorted(validator.iter_errors(...), key=...)
    p2-->>p11: validator.iter_errors(dict(...))
    p2-->>p12: dict (src/core/skill_params.py:validate_resolved)(resolved)
    p2-->>p13: list (src/core/skill_params.py:validate_resolved)(e.absolute_path)
    p2-->>p9: violations.append({...})
    p4-->>p14: isinstance (src/core/skill_params.py:schema_to_json_schema)(schema, Mapping)
    p3-->>p15: dict (src/core/skill_params.py:_apply_defaults_at)(value)
    p5-->>p16: isinstance (src/core/skill_params.py:_field_address)(part, int)
    p4-->>p17: dict (src/core/skill_params.py:schema_to_json_schema)(schema)
    p3-->>p18: node.get('properties')
    p5-->>p19: parts.append(...)
    p4-->>p20: getattr(schema, 'type', None)
    p3-->>p21: properties.items (src/core/skill_params.py:_apply_defaults_at)
    p5-->>p19: parts.append(...)
    p4-->>p22: bool(getattr(...))
    p3-->>p23: isinstance (src/core/skill_params.py:_apply_defaults_at)(prop, Mapping)
    p5-->>p24: ''.join(parts)
    p4-->>p20: getattr(schema, 'additionalProperties', False)
    p3-->>p23: isinstance (src/core/skill_params.py:_apply_defaults_at)(default, Mapping)
    p4-->>p20: getattr(schema, 'properties', None)
```

> Call sequence diagram shows 30 of 47 interactions; 17 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 15 of 23 (8 omitted); unresolved 10 of 16 (6 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/skill_params.py:schema_to_json_schema` | 3 | - | external | 5 |
| `src/core/skill_params.py:schema_to_json_schema` | 3 | - | unresolved | 4 |
| `src/core/skill_params.py:_apply_defaults_at` | 19 | - | unresolved | 2 |
| `src/core/skill_params.py:_apply_defaults_at` | 19 | [src/core/skill_params.py](../modules/skill_params.md) | internal | 2 |
| `src/core/skill_params.py:_apply_defaults_at` | 19 | - | external | 3 |
| `src/core/skill_params.py:validate_resolved` | 33 | [src/core/skill_params.py](../modules/skill_params.md) | internal | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. resolve_and_validate"]
    s2["2. apply_defaults"]
    s3["3. schema_to_json_schema"]
    s4["4. isinstance (src/core/skill_params.py:schema_to_json_schema)"]
    s5["5. dict (src/core/skill_params.py:schema_to_json_schema)"]
    s6["6. getattr"]
    s7["7. bool"]
    s8["8. getattr"]
    s9["9. getattr"]
    s10["10. hasattr"]
    s11["11. prop.model_dump"]
    s12["12. dict (src/core/skill_params.py:schema_to_json_schema)"]
    s1 -->|"apply_defaults(schema, raw)"| s2
    s2 -->|"schema_to_json_schema(schema)"| s3
    s3 -. "isinstance (src/core/skill_params.py:schema_to_json_schema)(schema, Mapping)" .-> s4
    s3 -. "dict (src/core/skill_params.py:schema_to_json_schema)(schema)" .-> s5
    s3 -. "getattr(schema, 'type', None)" .-> s6
    s3 -. "bool(getattr(...))" .-> s7
    s3 -. "getattr(schema, 'additionalProperties', False)" .-> s8
    s3 -. "getattr(schema, 'properties', None)" .-> s9
    s3 -. "hasattr(prop, 'model_dump')" .-> s10
    s3 -. "prop.model_dump(exclude_unset=True)" .-> s11
    s3 -. "dict (src/core/skill_params.py:schema_to_json_schema)(prop)" .-> s12
    click s1 "../modules/skill_params.md"
    click s2 "../modules/skill_params.md"
    click s3 "../modules/skill_params.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `resolve_and_validate` | `skill_id: str`, `schema: Any`, `raw: Mapping[str, Any] \| None` | - | - | `(...)` |
| `apply_defaults` | `schema: Any`, `value: Mapping[str, Any] \| None` | - | - | `_apply_defaults_at(...)` |
| `schema_to_json_schema` | `schema: Any` | `Mapping` | `out[...]`, `out[...]` | `dict(...)`, `out` |
| `isinstance (src/core/skill_params.py:schema_to_json_schema)` | - | - | - | - |
| `dict (src/core/skill_params.py:schema_to_json_schema)` | - | - | - | - |
| `getattr` | - | - | - | - |
| `bool` | - | - | - | - |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |
| `hasattr` | - | - | - | - |
| `prop.model_dump` | - | - | - | - |
| `dict (src/core/skill_params.py:schema_to_json_schema)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| resolve_and_validate | apply_defaults | 179 | `apply_defaults(schema, raw)` |
| apply_defaults | schema_to_json_schema | 104 | `schema_to_json_schema(schema)` |
| schema_to_json_schema | isinstance (src/core/skill_params.py:schema_to_json_schema) | 54 | `isinstance(schema, Mapping)` |
| schema_to_json_schema | dict (src/core/skill_params.py:schema_to_json_schema) | 55 | `dict(schema)` |
| schema_to_json_schema | getattr | 57 | `getattr(schema, 'type', None)` |
| schema_to_json_schema | bool | 58 | `bool(getattr(...))` |
| schema_to_json_schema | getattr | 58 | `getattr(schema, 'additionalProperties', False)` |
| schema_to_json_schema | getattr | 60 | `getattr(schema, 'properties', None)` |
| schema_to_json_schema | hasattr | 64 | `hasattr(prop, 'model_dump')` |
| schema_to_json_schema | prop.model_dump | 63 | `prop.model_dump(exclude_unset=True)` |
| schema_to_json_schema | dict (src/core/skill_params.py:schema_to_json_schema) | 64 | `dict(prop)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `schema_to_json_schema` | `isinstance` | 54 |
| external_call | `schema_to_json_schema` | `getattr` | 57 |
| external_call | `schema_to_json_schema` | `getattr` | 58 |
| external_call | `schema_to_json_schema` | `getattr` | 60 |
| external_call | `schema_to_json_schema` | `hasattr` | 64 |
| unresolved_call | `schema_to_json_schema` | `prop.model_dump` | 63 |
| step_limit | `resolve_and_validate` | `first 12 steps` | 0 |

## Behavior

This flow starts at `resolve_and_validate` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
