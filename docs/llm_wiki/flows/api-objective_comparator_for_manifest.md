# objective_comparator_for_manifest

**Entry point:** `objective_comparator_for_manifest` (`api`)
**Source:** [objective_comparator](../modules/objective_comparator.md)
**Modules touched:** [execution_contracts](../modules/execution_contracts.md), [objective_comparator](../modules/objective_comparator.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as objective_comparator_for_manifest
    participant p1 as getattr (src/core/objective_compar…ve_comparator_for_manifest)
    participant p2 as ObjectiveContextError
    participant p3 as objective_policy_from_skill_metric
    participant p4 as ObjectiveComparator.resolve
    participant p5 as ObjectivePolicy
    participant p6 as getattr (src/core/objective_compar…bjectiveComparator.resolve)
    participant p7 as _finite
    participant p8 as float (src/core/objective_compar…bjectiveComparator.resolve)
    participant p9 as ObjectiveComparator
    participant p10 as isinstance
    participant p11 as float (src/core/objective_comparator.py:_finite)
    participant p12 as math.isfinite
    p0-->>p1: getattr (src/core/objective_compar…ve_comparator_for_manifest)(manifest, 'metric_schema', None)
    p0-->>p1: getattr (src/core/objective_compar…ve_comparator_for_manifest)(metric_schema, 'primary', None)
    p0-->>p1: getattr (src/core/objective_compar…ve_comparator_for_manifest)(primary, 'direction', None)
    p0->>p2: ObjectiveContextError
    p0->>p3: objective_policy_from_skill_metric
    p0-->>p1: getattr (src/core/objective_compar…ve_comparator_for_manifest)(primary, 'field', None)
    p0->>p4: ObjectiveComparator.resolve
    p3->>p5: ObjectivePolicy
    p4-->>p6: getattr (src/core/objective_compar…bjectiveComparator.resolve)(policy, 'direction', None)
    p4->>p2: ObjectiveContextError
    p4->>p7: _finite
    p4-->>p6: getattr (src/core/objective_compar…bjectiveComparator.resolve)(policy, 'tie_tolerance', None)
    p4-->>p8: float (src/core/objective_compar…bjectiveComparator.resolve)(epsilon)
    p4->>p9: ObjectiveComparator
    p4-->>p6: getattr (src/core/objective_compar…bjectiveComparator.resolve)(policy, 'metric_field', None)
    p7-->>p10: isinstance(value, bool)
    p7-->>p10: isinstance(value, (...))
    p7-->>p11: float (src/core/objective_comparator.py:_finite)(value)
    p7-->>p12: math.isfinite(number)
```

> Call sequence diagram shows 19 of 19 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 12 of 12 (0 omitted); unresolved 0 of 0 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. objective_comparator_for_manifest"]
    s2["2. getattr (src/core/objective_compar…ve_comparator_for_manifest)"]
    s3["3. getattr (src/core/objective_compar…ve_comparator_for_manifest)"]
    s4["4. getattr (src/core/objective_compar…ve_comparator_for_manifest)"]
    s5["5. ObjectiveContextError"]
    s6["6. objective_policy_from_skill_metric"]
    s7["7. ObjectivePolicy"]
    s8["8. getattr (src/core/objective_compar…ve_comparator_for_manifest)"]
    s9["9. ObjectiveComparator.resolve"]
    s10["10. getattr (src/core/objective_compar…bjectiveComparator.resolve)"]
    s11["11. ObjectiveContextError"]
    s12["12. _finite"]
    s1 -. "getattr (src/core/objective_compar…ve_comparator_for_manifest)(manifest, 'metric_schema', None)" .-> s2
    s1 -. "getattr (src/core/objective_compar…ve_comparator_for_manifest)(metric_schema, 'primary', None)" .-> s3
    s1 -. "getattr (src/core/objective_compar…ve_comparator_for_manifest)(primary, 'direction', None)" .-> s4
    s1 -->|"ObjectiveContextError('skill manifest declares no usable metric_schema.primary.direction')"| s5
    s1 -->|"objective_policy_from_skill_metric(metric_field=..., direction=direction)"| s6
    s6 -->|"ObjectivePolicy(metric_field=metric_field, direction=..., goal=goal)"| s7
    s1 -. "getattr (src/core/objective_compar…ve_comparator_for_manifest)(primary, 'field', None)" .-> s8
    s1 -->|"ObjectiveComparator.resolve(policy=policy, epsilon=epsilon)"| s9
    s9 -. "getattr (src/core/objective_compar…bjectiveComparator.resolve)(policy, 'direction', None)" .-> s10
    s9 -->|"ObjectiveContextError(...)"| s11
    s9 -->|"_finite(getattr(...))"| s12
    click s1 "../modules/objective_comparator.md"
    click s5 "../modules/objective_comparator.md"
    click s6 "../modules/execution_contracts.md"
    click s7 "../modules/execution_contracts.md"
    click s9 "../modules/objective_comparator.md"
    click s11 "../modules/objective_comparator.md"
    click s12 "../modules/objective_comparator.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `objective_comparator_for_manifest` | `manifest: Any`, `epsilon: Optional[float]`, `metric_field: str` | - | - | `ObjectiveComparator.resolve(...)` |
| `getattr (src/core/objective_compar…ve_comparator_for_manifest)` | - | - | - | - |
| `getattr (src/core/objective_compar…ve_comparator_for_manifest)` | - | - | - | - |
| `getattr (src/core/objective_compar…ve_comparator_for_manifest)` | - | - | - | - |
| `ObjectiveContextError` | - | - | - | - |
| `objective_policy_from_skill_metric` | `metric_field: str`, `direction: Literal['higher_is_better', 'lower_is_better']`, `goal: ObjectiveGoal` | - | - | `ObjectivePolicy(...)` |
| `ObjectivePolicy` | - | - | - | - |
| `getattr (src/core/objective_compar…ve_comparator_for_manifest)` | - | - | - | - |
| `ObjectiveComparator.resolve` | `policy: Any`, `direction: Optional[str]`, `epsilon: Optional[float]`, `metric_field: str` | - | - | `cls(...)` |
| `getattr (src/core/objective_compar…bjectiveComparator.resolve)` | - | - | - | - |
| `ObjectiveContextError` | - | - | - | - |
| `_finite` | `value: Any` | - | - | `None`, `...` |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| objective_comparator_for_manifest | getattr (src/core/objective_compar…ve_comparator_for_manifest) | 223 | `getattr(manifest, 'metric_schema', None)` |
| objective_comparator_for_manifest | getattr (src/core/objective_compar…ve_comparator_for_manifest) | 224 | `getattr(metric_schema, 'primary', None)` |
| objective_comparator_for_manifest | getattr (src/core/objective_compar…ve_comparator_for_manifest) | 225 | `getattr(primary, 'direction', None)` |
| objective_comparator_for_manifest | ObjectiveContextError | 227 | `ObjectiveContextError('skill manifest declares no usable metric_schema.primary.direction')` |
| objective_comparator_for_manifest | objective_policy_from_skill_metric | 230 | `objective_policy_from_skill_metric(metric_field=..., direction=direction)` |
| objective_policy_from_skill_metric | ObjectivePolicy | 403 | `ObjectivePolicy(metric_field=metric_field, direction=..., goal=goal)` |
| objective_comparator_for_manifest | getattr (src/core/objective_compar…ve_comparator_for_manifest) | 231 | `getattr(primary, 'field', None)` |
| objective_comparator_for_manifest | ObjectiveComparator.resolve | 234 | `ObjectiveComparator.resolve(policy=policy, epsilon=epsilon)` |
| ObjectiveComparator.resolve | getattr (src/core/objective_compar…bjectiveComparator.resolve) | 105 | `getattr(policy, 'direction', None)` |
| ObjectiveComparator.resolve | ObjectiveContextError | 107 | `ObjectiveContextError(...)` |
| ObjectiveComparator.resolve | _finite | 111 | `_finite(getattr(...))` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `objective_comparator_for_manifest` | `getattr` | 223 |
| external_call | `objective_comparator_for_manifest` | `getattr` | 224 |
| external_call | `objective_comparator_for_manifest` | `getattr` | 225 |
| external_call | `objective_comparator_for_manifest` | `getattr` | 231 |
| external_call | `ObjectiveComparator.resolve` | `getattr` | 105 |
| step_limit | `objective_comparator_for_manifest` | `first 12 steps` | 0 |

## Behavior

This flow starts at `objective_comparator_for_manifest` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
