# threshold_evidence

**Entry point:** `threshold_evidence` (`api`)
**Source:** [goal_semantics](../modules/goal_semantics.md)
**Modules touched:** [goal_semantics](../modules/goal_semantics.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as threshold_evidence
    participant p1 as isinstance
    p0-->>p1: isinstance(metrics, Mapping)
```

> Call sequence diagram shows 1 of 1 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 1 of 1 (0 omitted); unresolved 0 of 0 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. threshold_evidence"]
    s2["2. isinstance"]
    s1 -. "isinstance(metrics, Mapping)" .-> s2
    click s1 "../modules/goal_semantics.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `threshold_evidence` | `metrics: Any`, `threshold_field: Optional[str]` | `Mapping` | - | `base`, `base`, `{...}` |
| `isinstance` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| threshold_evidence | isinstance | 58 | `isinstance(metrics, Mapping)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `threshold_evidence` | `isinstance` | 58 |

## Behavior

This flow starts at `threshold_evidence` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
