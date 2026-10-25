# scope_requirements

**Entry point:** `scope_requirements` (`api`)
**Source:** [promotion_policy](../modules/promotion_policy.md)
**Modules touched:** [promotion_policy](../modules/promotion_policy.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as scope_requirements
    participant p1 as graph.get
    p0-->>p1: graph.get(scope)
```

> Call sequence diagram shows 1 of 1 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 0 of 0 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. scope_requirements"]
    s2["2. graph.get"]
    s1 -. "graph.get(scope)" .-> s2
    click s1 "../modules/promotion_policy.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `scope_requirements` | `graph: Mapping[str, ScopeNode]`, `scope: str` | - | - | `graph.get(...)` |
| `graph.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| scope_requirements | graph.get | 113 | `graph.get(scope)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `scope_requirements` | `graph.get` | 113 |

## Behavior

This flow starts at `scope_requirements` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
