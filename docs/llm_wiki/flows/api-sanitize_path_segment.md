# sanitize_path_segment

**Entry point:** `sanitize_path_segment` (`api`)
**Source:** [skill_paths](../modules/skill_paths.md)
**Modules touched:** [skill_paths](../modules/skill_paths.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as sanitize_path_segment
    participant p1 as any
    participant p2 as ValueError
    p0-->>p1: any(...)
    p0-->>p2: ValueError(...)
```

> Call sequence diagram shows 2 of 2 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 2 of 2 (0 omitted); unresolved 0 of 0 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. sanitize_path_segment"]
    s2["2. any"]
    s3["3. ValueError"]
    s1 -. "any(...)" .-> s2
    s1 -. "ValueError(...)" .-> s3
    click s1 "../modules/skill_paths.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `sanitize_path_segment` | `value: str`, `field: str` | `_FORBIDDEN_SEGMENT_VALUES` | - | `value` |
| `any` | - | - | - | - |
| `ValueError` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| sanitize_path_segment | any | 48 | `any(...)` |
| sanitize_path_segment | ValueError | 51 | `ValueError(...)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `sanitize_path_segment` | `any` | 48 |
| external_call | `sanitize_path_segment` | `ValueError` | 51 |

## Behavior

This flow starts at `sanitize_path_segment` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
