# objective_policy_from_skill_metric

**Entry point:** `objective_policy_from_skill_metric` (`api`)
**Source:** [execution_contracts](../modules/execution_contracts.md)
**Modules touched:** [execution_contracts](../modules/execution_contracts.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as objective_policy_from_skill_metric
    participant p1 as ObjectivePolicy
    p0->>p1: ObjectivePolicy
```

> Call sequence diagram shows 1 of 1 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 0 of 0 (0 omitted); unresolved 0 of 0 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. objective_policy_from_skill_metric"]
    s2["2. ObjectivePolicy"]
    s1 -->|"ObjectivePolicy(metric_field=metric_field, direction=..., goal=goal)"| s2
    click s1 "../modules/execution_contracts.md"
    click s2 "../modules/execution_contracts.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `objective_policy_from_skill_metric` | `metric_field: str`, `direction: Literal['higher_is_better', 'lower_is_better']`, `goal: ObjectiveGoal` | - | - | `ObjectivePolicy(...)` |
| `ObjectivePolicy` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| objective_policy_from_skill_metric | ObjectivePolicy | 401 | `ObjectivePolicy(metric_field=metric_field, direction=..., goal=goal)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

*No static analysis gaps detected.*

## Behavior

This flow starts at `objective_policy_from_skill_metric` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
