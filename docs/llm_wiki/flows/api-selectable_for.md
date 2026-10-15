# selectable_for

**Entry point:** `selectable_for` (`api`)
**Source:** [skill_lifecycle](../modules/skill_lifecycle.md)
**Modules touched:** [skill_lifecycle](../modules/skill_lifecycle.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
*No outbound calls were detected by static analysis.*

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. selectable_for"]
    click s1 "../modules/skill_lifecycle.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `selectable_for` | `state: SkillLifecycleState`, `production: bool` | `SkillLifecycleState`, `SkillLifecycleState` | - | `...`, `...` |

### Call data

*No call data transfers detected.*

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

*No static analysis gaps detected.*

## Behavior

This flow starts at `selectable_for` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
