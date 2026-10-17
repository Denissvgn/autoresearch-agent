# apply_defaults

**Entry point:** `apply_defaults` (`api`)
**Source:** [skill_params](../modules/skill_params.md)
**Modules touched:** [skill_params](../modules/skill_params.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as apply_defaults
    participant p1 as schema_to_json_schema
    participant p2 as _apply_defaults_at
    participant p3 as dict (src/core/skill_params.py:apply_defaults)
    participant p4 as isinstance (src/core/skill_params.py:schema_to_json_schema)
    participant p5 as dict (src/core/skill_params.py:_apply_defaults_at)
    participant p6 as dict (src/core/skill_params.py:schema_to_json_schema)
    participant p7 as node.get
    participant p8 as getattr
    participant p9 as properties.items (src/core/skill_params.py:_apply_defaults_at)
    participant p10 as bool
    participant p11 as isinstance (src/core/skill_params.py:_apply_defaults_at)
    participant p12 as prop.get
    participant p13 as hasattr
    participant p14 as prop.model_dump
    participant p15 as properties.items (src/core/skill_params.py:schema_to_json_schema)
    participant p16 as list
    participant p17 as (…).items
    participant p18 as out.setdefault
    p0->>p1: schema_to_json_schema
    p0->>p2: _apply_defaults_at
    p0-->>p3: dict (src/core/skill_params.py:apply_defaults)(...)
    p1-->>p4: isinstance (src/core/skill_params.py:schema_to_json_schema)(schema, Mapping)
    p2-->>p5: dict (src/core/skill_params.py:_apply_defaults_at)(value)
    p1-->>p6: dict (src/core/skill_params.py:schema_to_json_schema)(schema)
    p2-->>p7: node.get('properties')
    p1-->>p8: getattr(schema, 'type', None)
    p2-->>p9: properties.items (src/core/skill_params.py:_apply_defaults_at)
    p1-->>p10: bool(getattr(...))
    p2-->>p11: isinstance (src/core/skill_params.py:_apply_defaults_at)(prop, Mapping)
    p1-->>p8: getattr(schema, 'additionalProperties', False)
    p2-->>p11: isinstance (src/core/skill_params.py:_apply_defaults_at)(default, Mapping)
    p1-->>p8: getattr(schema, 'properties', None)
    p2-->>p12: prop.get('type')
    p1-->>p13: hasattr(prop, 'model_dump')
    p2->>p2: _apply_defaults_at
    p1-->>p14: prop.model_dump(exclude_unset=True)
    p2-->>p5: dict (src/core/skill_params.py:_apply_defaults_at)(default)
    p1-->>p6: dict (src/core/skill_params.py:schema_to_json_schema)(prop)
    p2-->>p11: isinstance (src/core/skill_params.py:_apply_defaults_at)(current, Mapping)
    p1-->>p15: properties.items (src/core/skill_params.py:schema_to_json_schema)
    p2-->>p12: prop.get('type')
    p1-->>p8: getattr(schema, 'required', None)
    p2->>p2: _apply_defaults_at
    p1-->>p16: list(required)
    p2-->>p5: dict (src/core/skill_params.py:_apply_defaults_at)(current)
    p1-->>p17: (…).items
    p1-->>p8: getattr(schema, 'model_extra', None)
    p1-->>p18: out.setdefault(key, value)
```

> Call sequence diagram shows 30 of 30 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 18 of 18 (0 omitted); unresolved 8 of 8 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. apply_defaults"]
    s2["2. schema_to_json_schema"]
    s3["3. isinstance (src/core/skill_params.py:schema_to_json_schema)"]
    s4["4. dict (src/core/skill_params.py:schema_to_json_schema)"]
    s5["5. getattr"]
    s6["6. bool"]
    s7["7. getattr"]
    s8["8. getattr"]
    s9["9. hasattr"]
    s10["10. prop.model_dump"]
    s11["11. dict (src/core/skill_params.py:schema_to_json_schema)"]
    s12["12. properties.items (src/core/skill_params.py:schema_to_json_schema)"]
    s1 -->|"schema_to_json_schema(schema)"| s2
    s2 -. "isinstance (src/core/skill_params.py:schema_to_json_schema)(schema, Mapping)" .-> s3
    s2 -. "dict (src/core/skill_params.py:schema_to_json_schema)(schema)" .-> s4
    s2 -. "getattr(schema, 'type', None)" .-> s5
    s2 -. "bool(getattr(...))" .-> s6
    s2 -. "getattr(schema, 'additionalProperties', False)" .-> s7
    s2 -. "getattr(schema, 'properties', None)" .-> s8
    s2 -. "hasattr(prop, 'model_dump')" .-> s9
    s2 -. "prop.model_dump(exclude_unset=True)" .-> s10
    s2 -. "dict (src/core/skill_params.py:schema_to_json_schema)(prop)" .-> s11
    s2 -. "properties.items (src/core/skill_params.py:schema_to_json_schema)(data not statically known)" .-> s12
    click s1 "../modules/skill_params.md"
    click s2 "../modules/skill_params.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
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
| `properties.items (src/core/skill_params.py:schema_to_json_schema)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
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
| schema_to_json_schema | properties.items (src/core/skill_params.py:schema_to_json_schema) | 65 | `properties.items(data not statically known)` |

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
| unresolved_call | `schema_to_json_schema` | `properties.items` | 65 |
| step_limit | `apply_defaults` | `first 12 steps` | 0 |

## Behavior

This flow starts at `apply_defaults` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
