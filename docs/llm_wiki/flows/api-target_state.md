# target_state

**Entry point:** `target_state` (`api`)
**Source:** [skill_lifecycle](../modules/skill_lifecycle.md)
**Modules touched:** [skill_lifecycle](../modules/skill_lifecycle.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as target_state
    participant p1 as _TRANSITIONS.get
    p0-->>p1: _TRANSITIONS.get((...))
```

> Call sequence diagram shows 1 of 1 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 0 of 0 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. target_state"]
    s2["2. _TRANSITIONS.get"]
    s1 -. "_TRANSITIONS.get((...))" .-> s2
    click s1 "../modules/skill_lifecycle.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `target_state` | `from_state: SkillLifecycleState`, `event: SkillLifecycleEvent` | - | - | `_TRANSITIONS.get(...)` |
| `_TRANSITIONS.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| target_state | _TRANSITIONS.get | 130 | `_TRANSITIONS.get((...))` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `target_state` | `_TRANSITIONS.get` | 130 |

## Behavior

This flow starts at `target_state` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
