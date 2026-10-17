# schema_to_json_schema

**Entry point:** `schema_to_json_schema` (`api`)
**Source:** [skill_params](../modules/skill_params.md)
**Modules touched:** [skill_params](../modules/skill_params.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as schema_to_json_schema
    participant p1 as isinstance
    participant p2 as dict
    participant p3 as getattr
    participant p4 as bool
    participant p5 as hasattr
    participant p6 as prop.model_dump
    participant p7 as properties.items
    participant p8 as list
    participant p9 as (…).items
    participant p10 as out.setdefault
    p0-->>p1: isinstance(schema, Mapping)
    p0-->>p2: dict(schema)
    p0-->>p3: getattr(schema, 'type', None)
    p0-->>p4: bool(getattr(...))
    p0-->>p3: getattr(schema, 'additionalProperties', False)
    p0-->>p3: getattr(schema, 'properties', None)
    p0-->>p5: hasattr(prop, 'model_dump')
    p0-->>p6: prop.model_dump(exclude_unset=True)
    p0-->>p2: dict(prop)
    p0-->>p7: properties.items
    p0-->>p3: getattr(schema, 'required', None)
    p0-->>p8: list(required)
    p0-->>p9: (…).items
    p0-->>p3: getattr(schema, 'model_extra', None)
    p0-->>p10: out.setdefault(key, value)
```

> Call sequence diagram shows 15 of 15 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 11 of 11 (0 omitted); unresolved 4 of 4 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. schema_to_json_schema"]
    s2["2. isinstance"]
    s3["3. dict"]
    s4["4. getattr"]
    s5["5. bool"]
    s6["6. getattr"]
    s7["7. getattr"]
    s8["8. hasattr"]
    s9["9. prop.model_dump"]
    s10["10. dict"]
    s11["11. properties.items"]
    s12["12. getattr"]
    s1 -. "isinstance(schema, Mapping)" .-> s2
    s1 -. "dict(schema)" .-> s3
    s1 -. "getattr(schema, 'type', None)" .-> s4
    s1 -. "bool(getattr(...))" .-> s5
    s1 -. "getattr(schema, 'additionalProperties', False)" .-> s6
    s1 -. "getattr(schema, 'properties', None)" .-> s7
    s1 -. "hasattr(prop, 'model_dump')" .-> s8
    s1 -. "prop.model_dump(exclude_unset=True)" .-> s9
    s1 -. "dict(prop)" .-> s10
    s1 -. "properties.items(data not statically known)" .-> s11
    s1 -. "getattr(schema, 'required', None)" .-> s12
    click s1 "../modules/skill_params.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `schema_to_json_schema` | `schema: Any` | `Mapping` | `out[...]`, `out[...]` | `dict(...)`, `out` |
| `isinstance` | - | - | - | - |
| `dict` | - | - | - | - |
| `getattr` | - | - | - | - |
| `bool` | - | - | - | - |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |
| `hasattr` | - | - | - | - |
| `prop.model_dump` | - | - | - | - |
| `dict` | - | - | - | - |
| `properties.items` | - | - | - | - |
| `getattr` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| schema_to_json_schema | isinstance | 54 | `isinstance(schema, Mapping)` |
| schema_to_json_schema | dict | 55 | `dict(schema)` |
| schema_to_json_schema | getattr | 57 | `getattr(schema, 'type', None)` |
| schema_to_json_schema | bool | 58 | `bool(getattr(...))` |
| schema_to_json_schema | getattr | 58 | `getattr(schema, 'additionalProperties', False)` |
| schema_to_json_schema | getattr | 60 | `getattr(schema, 'properties', None)` |
| schema_to_json_schema | hasattr | 64 | `hasattr(prop, 'model_dump')` |
| schema_to_json_schema | prop.model_dump | 63 | `prop.model_dump(exclude_unset=True)` |
| schema_to_json_schema | dict | 64 | `dict(prop)` |
| schema_to_json_schema | properties.items | 65 | `properties.items(data not statically known)` |
| schema_to_json_schema | getattr | 67 | `getattr(schema, 'required', None)` |

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
| external_call | `schema_to_json_schema` | `getattr` | 67 |
| step_limit | `schema_to_json_schema` | `first 12 steps` | 0 |

## Behavior

This flow starts at `schema_to_json_schema` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
