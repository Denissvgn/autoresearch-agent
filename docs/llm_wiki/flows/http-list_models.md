# list_models

**Entry point:** `list_models` (`http`)
**Source:** [research](../modules/research.md)
**Modules touched:** [research](../modules/research.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as list_models
    participant p1 as default_registry.available
    p0-->>p1: default_registry.available
```

> Call sequence diagram shows 1 of 1 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 0 of 0 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. list_models"]
    s2["2. default_registry.available"]
    s1 -. "default_registry.available(data not statically known)" .-> s2
    click s1 "../modules/research.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `list_models` | - | - | - | `...` |
| `default_registry.available` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| list_models | default_registry.available | 1073 | `default_registry.available(data not statically known)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `list_models` | `default_registry.available` | 1073 |

## Behavior

This flow starts at `list_models` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
