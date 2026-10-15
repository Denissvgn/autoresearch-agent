# build_generation_prompt

**Entry point:** `build_generation_prompt` (`api`)
**Source:** [skill_generator](../modules/skill_generator.md)
**Modules touched:** [skill_generator](../modules/skill_generator.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as build_generation_prompt
    participant p1 as json.dumps
    p0-->>p1: json.dumps(schema, indent=2)
```

> Call sequence diagram shows 1 of 1 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 1 of 1 (0 omitted); unresolved 0 of 0 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. build_generation_prompt"]
    s2["2. json.dumps"]
    s1 -. "json.dumps(schema, indent=2)" .-> s2
    click s1 "../modules/skill_generator.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `build_generation_prompt` | `description: str` | - | - | `(...)` |
| `json.dumps` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| build_generation_prompt | json.dumps | 178 | `json.dumps(schema, indent=2)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `build_generation_prompt` | `json.dumps` | 178 |

## Behavior

This flow starts at `build_generation_prompt` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
