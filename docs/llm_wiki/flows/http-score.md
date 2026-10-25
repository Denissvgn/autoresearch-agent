# score

**Entry point:** `score` (`http`)
**Source:** [test_prompt_evaluation_domain](../modules/test_prompt_evaluation_domain.md)
**Modules touched:** [test_prompt_evaluation_domain](../modules/test_prompt_evaluation_domain.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as score
    participant p1 as scorer.score
    p0-->>p1: scorer.score(request)
```

> Call sequence diagram shows 1 of 1 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 0 of 0 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. score"]
    s2["2. scorer.score"]
    s1 -. "scorer.score(request)" .-> s2
    click s1 "../modules/test_prompt_evaluation_domain.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `score` | `request: dict` | - | - | `scorer.score(...)` |
| `scorer.score` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| score | scorer.score | 133 | `scorer.score(request)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `score` | `scorer.score` | 133 |

## Behavior

This flow starts at `score` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
