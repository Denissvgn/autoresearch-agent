# best_other_config_hash

**Entry point:** `best_other_config_hash` (`api`)
**Source:** [significance](../modules/significance.md)
**Modules touched:** [objective_comparator](../modules/objective_comparator.md), [significance](../modules/significance.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as best_other_config_hash
    participant p1 as json.loads (src/core/significance.py:best_other_config_hash)
    participant p2 as row.get (src/core/significance.py:best_other_config_hash)
    participant p3 as metrics.get (src/core/significance.py:best_other_config_hash)
    participant p4 as others.append
    participant p5 as best_config_hash
    participant p6 as ObjectiveComparator
    participant p7 as row.get (src/core/significance.py:best_config_hash)
    participant p8 as comparator.is_better
    participant p9 as json.loads (src/core/significance.py:best_config_hash)
    participant p10 as best_row.get
    participant p11 as metrics.get (src/core/significance.py:best_config_hash)
    p0-->>p1: json.loads (src/core/significance.py:best_other_config_hash)(...)
    p0-->>p2: row.get (src/core/significance.py:best_other_config_hash)('metrics_json')
    p0-->>p3: metrics.get (src/core/significance.py:best_other_config_hash)('canonical_config_hash')
    p0-->>p4: others.append(row)
    p0->>p5: best_config_hash
    p5->>p6: ObjectiveComparator
    p5-->>p7: row.get (src/core/significance.py:best_config_hash)('primary_metric')
    p5-->>p7: row.get (src/core/significance.py:best_config_hash)('decision')
    p5-->>p8: comparator.is_better(metric, best_row[...])
    p5-->>p9: json.loads (src/core/significance.py:best_config_hash)(...)
    p5-->>p10: best_row.get('metrics_json')
    p5-->>p11: metrics.get (src/core/significance.py:best_config_hash)('canonical_config_hash')
```

> Call sequence diagram shows 12 of 12 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 2 of 2 (0 omitted); unresolved 8 of 8 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. best_other_config_hash"]
    s2["2. json.loads (src/core/significance.py:best_other_config_hash)"]
    s3["3. row.get (src/core/significance.py:best_other_config_hash)"]
    s4["4. metrics.get (src/core/significance.py:best_other_config_hash)"]
    s5["5. others.append"]
    s6["6. best_config_hash"]
    s7["7. ObjectiveComparator"]
    s8["8. row.get (src/core/significance.py:best_config_hash)"]
    s9["9. row.get (src/core/significance.py:best_config_hash)"]
    s10["10. comparator.is_better"]
    s11["11. json.loads (src/core/significance.py:best_config_hash)"]
    s12["12. best_row.get"]
    s1 -. "json.loads (src/core/significance.py:best_other_config_hash)(...)" .-> s2
    s1 -. "row.get (src/core/significance.py:best_other_config_hash)('metrics_json')" .-> s3
    s1 -. "metrics.get (src/core/significance.py:best_other_config_hash)('canonical_config_hash')" .-> s4
    s1 -. "others.append(row)" .-> s5
    s1 -->|"best_config_hash(others, direction=direction)"| s6
    s6 -->|"ObjectiveComparator(direction=...)"| s7
    s6 -. "row.get (src/core/significance.py:best_config_hash)('primary_metric')" .-> s8
    s6 -. "row.get (src/core/significance.py:best_config_hash)('decision')" .-> s9
    s6 -. "comparator.is_better(metric, best_row[...])" .-> s10
    s6 -. "json.loads (src/core/significance.py:best_config_hash)(...)" .-> s11
    s6 -. "best_row.get('metrics_json')" .-> s12
    b0["mutation others.append"]
    s1 -. "mutation others.append" .-> b0
    click s1 "../modules/significance.md"
    click s6 "../modules/significance.md"
    click s7 "../modules/objective_comparator.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `best_other_config_hash` | `rows: Sequence[dict]`, `exclude_hash: Optional[str]`, `direction: str` | - | - | `best_config_hash(...)` |
| `json.loads (src/core/significance.py:best_other_config_hash)` | - | - | - | - |
| `row.get (src/core/significance.py:best_other_config_hash)` | - | - | - | - |
| `metrics.get (src/core/significance.py:best_other_config_hash)` | - | - | - | - |
| `others.append` | - | - | - | - |
| `best_config_hash` | `rows: Sequence[dict]`, `direction: str` | - | - | `None`, `None`, `...` |
| `ObjectiveComparator` | - | - | - | - |
| `row.get (src/core/significance.py:best_config_hash)` | - | - | - | - |
| `row.get (src/core/significance.py:best_config_hash)` | - | - | - | - |
| `comparator.is_better` | - | - | - | - |
| `json.loads (src/core/significance.py:best_config_hash)` | - | - | - | - |
| `best_row.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| best_other_config_hash | json.loads (src/core/significance.py:best_other_config_hash) | 181 | `json.loads(...)` |
| best_other_config_hash | row.get (src/core/significance.py:best_other_config_hash) | 181 | `row.get('metrics_json')` |
| best_other_config_hash | metrics.get (src/core/significance.py:best_other_config_hash) | 184 | `metrics.get('canonical_config_hash')` |
| best_other_config_hash | others.append | 185 | `others.append(row)` |
| best_other_config_hash | best_config_hash | 186 | `best_config_hash(others, direction=direction)` |
| best_config_hash | ObjectiveComparator | 141 | `ObjectiveComparator(direction=...)` |
| best_config_hash | row.get (src/core/significance.py:best_config_hash) | 146 | `row.get('primary_metric')` |
| best_config_hash | row.get (src/core/significance.py:best_config_hash) | 147 | `row.get('decision')` |
| best_config_hash | comparator.is_better | 152 | `comparator.is_better(metric, best_row[...])` |
| best_config_hash | json.loads (src/core/significance.py:best_config_hash) | 159 | `json.loads(...)` |
| best_config_hash | best_row.get | 159 | `best_row.get('metrics_json')` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `others.append` | `best_other_config_hash` | 185 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `best_other_config_hash` | `json.loads` | 181 |
| unresolved_call | `best_other_config_hash` | `row.get` | 181 |
| unresolved_call | `best_other_config_hash` | `metrics.get` | 184 |
| unresolved_call | `best_config_hash` | `row.get` | 146 |
| unresolved_call | `best_config_hash` | `row.get` | 147 |
| unresolved_call | `best_config_hash` | `comparator.is_better` | 152 |
| external_call | `best_config_hash` | `json.loads` | 159 |
| unresolved_call | `best_config_hash` | `best_row.get` | 159 |
| step_limit | `best_other_config_hash` | `first 12 steps` | 0 |

## Behavior

This flow starts at `best_other_config_hash` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
