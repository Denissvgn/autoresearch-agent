# unsupported_schema_keywords

**Entry point:** `unsupported_schema_keywords` (`api`)
**Source:** [skill_params](../modules/skill_params.md)
**Modules touched:** [skill_params](../modules/skill_params.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as unsupported_schema_keywords
    participant p1 as schema_to_json_schema
    participant p2 as set
    participant p3 as walk
    participant p4 as frozenset
    participant p5 as isinstance
    participant p6 as dict
    participant p7 as getattr
    participant p8 as bool
    participant p9 as hasattr
    participant p10 as prop.model_dump
    participant p11 as properties.items
    participant p12 as list
    participant p13 as (…).items
    participant p14 as out.setdefault
    p0->>p1: schema_to_json_schema
    p0-->>p2: set
    p0-->>p3: walk(document)
    p0-->>p4: frozenset(found)
    p1-->>p5: isinstance(schema, Mapping)
    p1-->>p6: dict(schema)
    p1-->>p7: getattr(schema, 'type', None)
    p1-->>p8: bool(getattr(...))
    p1-->>p7: getattr(schema, 'additionalProperties', False)
    p1-->>p7: getattr(schema, 'properties', None)
    p1-->>p9: hasattr(prop, 'model_dump')
    p1-->>p10: prop.model_dump(exclude_unset=True)
    p1-->>p6: dict(prop)
    p1-->>p11: properties.items
    p1-->>p7: getattr(schema, 'required', None)
    p1-->>p12: list(required)
    p1-->>p13: (…).items
    p1-->>p7: getattr(schema, 'model_extra', None)
    p1-->>p14: out.setdefault(key, value)
```

> Call sequence diagram shows 19 of 19 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 13 of 13 (0 omitted); unresolved 5 of 5 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. unsupported_schema_keywords"]
    s2["2. schema_to_json_schema"]
    s3["3. isinstance"]
    s4["4. dict"]
    s5["5. getattr"]
    s6["6. bool"]
    s7["7. getattr"]
    s8["8. getattr"]
    s9["9. hasattr"]
    s10["10. prop.model_dump"]
    s11["11. dict"]
    s12["12. properties.items"]
    s1 -->|"schema_to_json_schema(schema)"| s2
    s2 -. "isinstance(schema, Mapping)" .-> s3
    s2 -. "dict(schema)" .-> s4
    s2 -. "getattr(schema, 'type', None)" .-> s5
    s2 -. "bool(getattr(...))" .-> s6
    s2 -. "getattr(schema, 'additionalProperties', False)" .-> s7
    s2 -. "getattr(schema, 'properties', None)" .-> s8
    s2 -. "hasattr(prop, 'model_dump')" .-> s9
    s2 -. "prop.model_dump(exclude_unset=True)" .-> s10
    s2 -. "dict(prop)" .-> s11
    s2 -. "properties.items(data not statically known)" .-> s12
    click s1 "../modules/skill_params.md"
    click s2 "../modules/skill_params.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `unsupported_schema_keywords` | `schema: Any` | - | - | `frozenset(...)` |
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

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| unsupported_schema_keywords | schema_to_json_schema | 77 | `schema_to_json_schema(schema)` |
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
| step_limit | `unsupported_schema_keywords` | `first 12 steps` | 0 |

## Behavior

This flow starts at `unsupported_schema_keywords` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
