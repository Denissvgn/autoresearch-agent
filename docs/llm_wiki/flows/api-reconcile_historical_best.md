# reconcile_historical_best

**Entry point:** `reconcile_historical_best` (`api`)
**Source:** [objective_comparator](../modules/objective_comparator.md)
**Modules touched:** [compat_legacy_alias](../modules/compat_legacy_alias.md), [execution_contracts](../modules/execution_contracts.md), [objective_comparator](../modules/objective_comparator.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as reconcile_historical_best
    participant p1 as objective_comparator_for_skill_id
    participant p2 as select_best_row
    participant p3 as objective_comparator_for_manifest
    participant p4 as objective_policy_from_skill_metric
    participant p5 as ObjectiveComparator.resolve
    participant p6 as ObjectiveContextError
    participant p7 as _finite
    participant p8 as model_type_to_skill_id
    participant p9 as ObjectivePolicy
    participant p10 as ObjectiveComparator
    participant p11 as sorted
    participant p12 as session.get
    participant p13 as flags.append
    participant p14 as row.get (src/core/objective_compar…:reconcile_historical_best)
    participant p15 as winner.get
    participant p16 as comparator.compare
    participant p17 as row.get (src/core/objective_comparator.py:select_best_row)
    participant p18 as default_registry.get
    participant p19 as get_value
    participant p20 as is_eligible
    participant p21 as getattr (src/core/objective_compar…ve_comparator_for_skill_id)
    p0->>p1: objective_comparator_for_skill_id
    p0->>p2: select_best_row
    p1->>p3: objective_comparator_for_manifest
    p3->>p4: objective_policy_from_skill_metric
    p3->>p5: ObjectiveComparator.resolve
    p1->>p6: ObjectiveContextError
    p2->>p7: _finite
    p1->>p8: model_type_to_skill_id
    p4->>p9: ObjectivePolicy
    p5->>p10: ObjectiveComparator
    p0-->>p11: sorted(iterations, key=...)
    p0-->>p12: session.get('skill_id')
    p0-->>p12: session.get('model_type')
    p0-->>p13: flags.append('objective_direction_unknown')
    p0-->>p12: session.get('best_iteration')
    p0-->>p12: session.get('best_metric')
    p0-->>p12: session.get('id')
    p0-->>p14: row.get (src/core/objective_compar…:reconcile_historical_best)('iteration')
    p0-->>p12: session.get('id')
    p0-->>p15: winner.get('iteration')
    p0-->>p15: winner.get('primary_metric')
    p0-->>p16: comparator.compare(stored[...], recomputed[...])
    p0-->>p13: flags.append('stored_best_differs_from_recomputed')
    p0-->>p12: session.get('id')
    p2-->>p17: row.get (src/core/objective_comparator.py:select_best_row)(comparator.metric_field)
    p1-->>p18: default_registry.get(skill_id)
    p1-->>p18: default_registry.get(model_type_to_skill_id(...))
    p2-->>p19: get_value(row)
    p2-->>p20: is_eligible(row)
    p1-->>p21: getattr (src/core/objective_compar…ve_comparator_for_skill_id)(skill, 'manifest', None)
```

> Call sequence diagram shows 30 of 50 interactions; 20 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 2 of 14 (12 omitted); unresolved 18 of 22 (4 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/compat/legacy_alias.py:model_type_to_skill_id` | 8 | - | unresolved | 1 |
| `src/core/objective_comparator.py:objective_comparator_for_skill_id` | 4 | [src/core/objective_comparator.py](../modules/objective_comparator.md) | internal | 1 |
| `src/core/objective_comparator.py:objective_comparator_for_manifest` | 12 | - | external | 4 |
| `src/core/objective_comparator.py:objective_comparator_for_manifest` | 12 | [src/core/objective_comparator.py](../modules/objective_comparator.md) | internal | 1 |
| `src/core/objective_comparator.py:ObjectiveComparator.resolve` | 20 | - | external | 4 |
| `src/core/objective_comparator.py:ObjectiveComparator.resolve` | 20 | [src/core/objective_comparator.py](../modules/objective_comparator.md) | internal | 2 |
| `src/core/objective_comparator.py:_finite` | 23 | - | external | 4 |
| `src/core/objective_comparator.py:select_best_row` | 38 | - | unresolved | 3 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. reconcile_historical_best"]
    s2["2. session.get"]
    s3["3. session.get"]
    s4["4. objective_comparator_for_skill_id"]
    s5["5. ObjectiveContextError"]
    s6["6. default_registry.get"]
    s7["7. default_registry.get"]
    s8["8. model_type_to_skill_id"]
    s9["9. _MODEL_TYPE_TO_SKILL_ID.get"]
    s10["10. getattr (src/core/objective_compar…ve_comparator_for_skill_id)"]
    s11["11. ObjectiveContextError"]
    s12["12. objective_comparator_for_manifest"]
    s1 -. "session.get('skill_id')" .-> s2
    s1 -. "session.get('model_type')" .-> s3
    s1 -->|"objective_comparator_for_skill_id(skill_id, default=None)"| s4
    s4 -->|"ObjectiveContextError('no skill id to resolve an objective from')"| s5
    s4 -. "default_registry.get(skill_id)" .-> s6
    s4 -. "default_registry.get(model_type_to_skill_id(...))" .-> s7
    s4 -->|"model_type_to_skill_id(skill_id)"| s8
    s8 -. "_MODEL_TYPE_TO_SKILL_ID.get(model_type, model_type)" .-> s9
    s4 -. "getattr (src/core/objective_compar…ve_comparator_for_skill_id)(skill, 'manifest', None)" .-> s10
    s4 -->|"ObjectiveContextError(...)"| s11
    s4 -->|"objective_comparator_for_manifest(manifest, epsilon=epsilon)"| s12
    b0["mutation flags.append"]
    s1 -. "mutation flags.append" .-> b0
    b1["mutation flags.append"]
    s1 -. "mutation flags.append" .-> b1
    click s1 "../modules/objective_comparator.md"
    click s4 "../modules/objective_comparator.md"
    click s5 "../modules/objective_comparator.md"
    click s8 "../modules/compat_legacy_alias.md"
    click s11 "../modules/objective_comparator.md"
    click s12 "../modules/objective_comparator.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `reconcile_historical_best` | `session: Mapping[str, Any]`, `iterations: Sequence[Mapping[str, Any]]`, `comparator: Optional[ObjectiveComparator]` | `ObjectiveContextError` | - | `{...}`, `{...}`, `{...}` |
| `session.get` | - | - | - | - |
| `session.get` | - | - | - | - |
| `objective_comparator_for_skill_id` | `skill_id: Optional[str]`, `epsilon: Optional[float]`, `default: Optional[ObjectiveComparator]` | - | - | `default`, `default`, `objective_comparator_for_manifest(...)` |
| `ObjectiveContextError` | - | - | - | - |
| `default_registry.get` | - | - | - | - |
| `default_registry.get` | - | - | - | - |
| `model_type_to_skill_id` | `model_type: str` | - | - | `''`, `_MODEL_TYPE_TO_SKILL_ID.get(...)` |
| `_MODEL_TYPE_TO_SKILL_ID.get` | - | - | - | - |
| `getattr (src/core/objective_compar…ve_comparator_for_skill_id)` | - | - | - | - |
| `ObjectiveContextError` | - | - | - | - |
| `objective_comparator_for_manifest` | `manifest: Any`, `epsilon: Optional[float]`, `metric_field: str` | - | - | `ObjectiveComparator.resolve(...)` |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| reconcile_historical_best | session.get | 295 | `session.get('skill_id')` |
| reconcile_historical_best | session.get | 295 | `session.get('model_type')` |
| reconcile_historical_best | objective_comparator_for_skill_id | 297 | `objective_comparator_for_skill_id(skill_id, default=None)` |
| objective_comparator_for_skill_id | ObjectiveContextError | 251 | `ObjectiveContextError('no skill id to resolve an objective from')` |
| objective_comparator_for_skill_id | default_registry.get | 255 | `default_registry.get(skill_id)` |
| objective_comparator_for_skill_id | default_registry.get | 264 | `default_registry.get(model_type_to_skill_id(...))` |
| objective_comparator_for_skill_id | model_type_to_skill_id | 264 | `model_type_to_skill_id(skill_id)` |
| model_type_to_skill_id | _MODEL_TYPE_TO_SKILL_ID.get | 45 | `_MODEL_TYPE_TO_SKILL_ID.get(model_type, model_type)` |
| objective_comparator_for_skill_id | getattr (src/core/objective_compar…ve_comparator_for_skill_id) | 267 | `getattr(skill, 'manifest', None)` |
| objective_comparator_for_skill_id | ObjectiveContextError | 271 | `ObjectiveContextError(...)` |
| objective_comparator_for_skill_id | objective_comparator_for_manifest | 274 | `objective_comparator_for_manifest(manifest, epsilon=epsilon)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `flags.append` | `reconcile_historical_best` | 301 |
| mutation | `flags.append` | `reconcile_historical_best` | 347 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `reconcile_historical_best` | `session.get` | 295 |
| unresolved_call | `objective_comparator_for_skill_id` | `default_registry.get` | 255 |
| unresolved_call | `objective_comparator_for_skill_id` | `default_registry.get` | 264 |
| unresolved_call | `model_type_to_skill_id` | `_MODEL_TYPE_TO_SKILL_ID.get` | 45 |
| external_call | `objective_comparator_for_skill_id` | `getattr` | 267 |
| step_limit | `reconcile_historical_best` | `first 12 steps` | 0 |

## Behavior

This flow starts at `reconcile_historical_best` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
