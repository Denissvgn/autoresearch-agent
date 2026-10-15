# is_secret_reference

**Entry point:** `is_secret_reference` (`api`)
**Source:** [execution_contracts](../modules/execution_contracts.md)
**Modules touched:** [execution_contracts](../modules/execution_contracts.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as is_secret_reference
    participant p1 as isinstance
    participant p2 as value.startswith
    p0-->>p1: isinstance(value, str)
    p0-->>p2: value.startswith(SECRET_WIRE_PREFIX)
```

> Call sequence diagram shows 2 of 2 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 1 of 1 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. is_secret_reference"]
    s2["2. isinstance"]
    s3["3. value.startswith"]
    s1 -. "isinstance(value, str)" .-> s2
    s1 -. "value.startswith(SECRET_WIRE_PREFIX)" .-> s3
    click s1 "../modules/execution_contracts.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `is_secret_reference` | `value: Any` | `SECRET_WIRE_PREFIX` | - | `...` |
| `isinstance` | - | - | - | - |
| `value.startswith` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| is_secret_reference | isinstance | 182 | `isinstance(value, str)` |
| is_secret_reference | value.startswith | 182 | `value.startswith(SECRET_WIRE_PREFIX)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `is_secret_reference` | `isinstance` | 182 |
| unresolved_call | `is_secret_reference` | `value.startswith` | 182 |

## Behavior

This flow starts at `is_secret_reference` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
