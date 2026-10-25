# is_secret_param_name

**Entry point:** `is_secret_param_name` (`api`)
**Source:** [run_spec](../modules/run_spec.md)
**Modules touched:** [run_spec](../modules/run_spec.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as is_secret_param_name
    participant p1 as str(…).lower
    participant p2 as str
    participant p3 as any
    p0-->>p1: str(…).lower
    p0-->>p2: str(name)
    p0-->>p3: any(...)
```

> Call sequence diagram shows 3 of 3 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 2 of 2 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. is_secret_param_name"]
    s2["2. str(…).lower"]
    s3["3. str"]
    s4["4. any"]
    s1 -. "str(…).lower(data not statically known)" .-> s2
    s1 -. "str(name)" .-> s3
    s1 -. "any(...)" .-> s4
    click s1 "../modules/run_spec.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `is_secret_param_name` | `name: str` | `SECRET_NAME_MARKERS` | - | `any(...)` |
| `str(…).lower` | - | - | - | - |
| `str` | - | - | - | - |
| `any` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| is_secret_param_name | str(…).lower | 49 | `str(name).lower(data not statically known)` |
| is_secret_param_name | str | 49 | `str(name)` |
| is_secret_param_name | any | 50 | `any(...)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `is_secret_param_name` | `str(name).lower` | 49 |
| external_call | `is_secret_param_name` | `any` | 50 |

## Behavior

This flow starts at `is_secret_param_name` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
