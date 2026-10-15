# best_config_hash

**Entry point:** `best_config_hash` (`api`)
**Source:** [significance](../modules/significance.md)
**Modules touched:** [significance](../modules/significance.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as best_config_hash
    participant p1 as row.get
    participant p2 as json.loads
    participant p3 as best_row.get
    participant p4 as metrics.get
    p0-->>p1: row.get('primary_metric')
    p0-->>p1: row.get('decision')
    p0-->>p2: json.loads(...)
    p0-->>p3: best_row.get('metrics_json')
    p0-->>p4: metrics.get('canonical_config_hash')
```

> Call sequence diagram shows 5 of 5 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 1 of 1 (0 omitted); unresolved 4 of 4 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. best_config_hash"]
    s2["2. row.get"]
    s3["3. row.get"]
    s4["4. json.loads"]
    s5["5. best_row.get"]
    s6["6. metrics.get"]
    s1 -. "row.get('primary_metric')" .-> s2
    s1 -. "row.get('decision')" .-> s3
    s1 -. "json.loads(...)" .-> s4
    s1 -. "best_row.get('metrics_json')" .-> s5
    s1 -. "metrics.get('canonical_config_hash')" .-> s6
    click s1 "../modules/significance.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `best_config_hash` | `rows: Sequence[dict]`, `direction: str` | - | - | `None`, `None`, `...` |
| `row.get` | - | - | - | - |
| `row.get` | - | - | - | - |
| `json.loads` | - | - | - | - |
| `best_row.get` | - | - | - | - |
| `metrics.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| best_config_hash | row.get | 132 | `row.get('primary_metric')` |
| best_config_hash | row.get | 133 | `row.get('decision')` |
| best_config_hash | json.loads | 150 | `json.loads(...)` |
| best_config_hash | best_row.get | 150 | `best_row.get('metrics_json')` |
| best_config_hash | metrics.get | 153 | `metrics.get('canonical_config_hash')` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `best_config_hash` | `row.get` | 132 |
| unresolved_call | `best_config_hash` | `row.get` | 133 |
| external_call | `best_config_hash` | `json.loads` | 150 |
| unresolved_call | `best_config_hash` | `best_row.get` | 150 |
| unresolved_call | `best_config_hash` | `metrics.get` | 153 |

## Behavior

This flow starts at `best_config_hash` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
