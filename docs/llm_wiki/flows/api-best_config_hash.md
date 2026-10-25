# best_config_hash

**Entry point:** `best_config_hash` (`api`)
**Source:** [significance](../modules/significance.md)
**Modules touched:** [objective_comparator](../modules/objective_comparator.md), [significance](../modules/significance.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as best_config_hash
    participant p1 as ObjectiveComparator
    participant p2 as row.get
    participant p3 as comparator.is_better
    participant p4 as json.loads
    participant p5 as best_row.get
    participant p6 as metrics.get
    p0->>p1: ObjectiveComparator
    p0-->>p2: row.get('primary_metric')
    p0-->>p2: row.get('decision')
    p0-->>p3: comparator.is_better(metric, best_row[...])
    p0-->>p4: json.loads(...)
    p0-->>p5: best_row.get('metrics_json')
    p0-->>p6: metrics.get('canonical_config_hash')
```

> Call sequence diagram shows 7 of 7 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 1 of 1 (0 omitted); unresolved 5 of 5 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. best_config_hash"]
    s2["2. ObjectiveComparator"]
    s3["3. row.get"]
    s4["4. row.get"]
    s5["5. comparator.is_better"]
    s6["6. json.loads"]
    s7["7. best_row.get"]
    s8["8. metrics.get"]
    s1 -->|"ObjectiveComparator(direction=...)"| s2
    s1 -. "row.get('primary_metric')" .-> s3
    s1 -. "row.get('decision')" .-> s4
    s1 -. "comparator.is_better(metric, best_row[...])" .-> s5
    s1 -. "json.loads(...)" .-> s6
    s1 -. "best_row.get('metrics_json')" .-> s7
    s1 -. "metrics.get('canonical_config_hash')" .-> s8
    click s1 "../modules/significance.md"
    click s2 "../modules/objective_comparator.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `best_config_hash` | `rows: Sequence[dict]`, `direction: str` | - | - | `None`, `None`, `...` |
| `ObjectiveComparator` | - | - | - | - |
| `row.get` | - | - | - | - |
| `row.get` | - | - | - | - |
| `comparator.is_better` | - | - | - | - |
| `json.loads` | - | - | - | - |
| `best_row.get` | - | - | - | - |
| `metrics.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| best_config_hash | ObjectiveComparator | 141 | `ObjectiveComparator(direction=...)` |
| best_config_hash | row.get | 146 | `row.get('primary_metric')` |
| best_config_hash | row.get | 147 | `row.get('decision')` |
| best_config_hash | comparator.is_better | 152 | `comparator.is_better(metric, best_row[...])` |
| best_config_hash | json.loads | 159 | `json.loads(...)` |
| best_config_hash | best_row.get | 159 | `best_row.get('metrics_json')` |
| best_config_hash | metrics.get | 162 | `metrics.get('canonical_config_hash')` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `best_config_hash` | `row.get` | 146 |
| unresolved_call | `best_config_hash` | `row.get` | 147 |
| unresolved_call | `best_config_hash` | `comparator.is_better` | 152 |
| external_call | `best_config_hash` | `json.loads` | 159 |
| unresolved_call | `best_config_hash` | `best_row.get` | 159 |
| unresolved_call | `best_config_hash` | `metrics.get` | 162 |

## Behavior

This flow starts at `best_config_hash` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
