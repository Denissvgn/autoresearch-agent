# rank_rows

**Entry point:** `rank_rows` (`api`)
**Source:** [objective_comparator](../modules/objective_comparator.md)
**Modules touched:** [objective_comparator](../modules/objective_comparator.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as rank_rows
    participant p1 as row.get
    participant p2 as _finite
    participant p3 as get_value
    participant p4 as is_eligible
    participant p5 as sorted
    participant p6 as cmp_to_key
    participant p7 as isinstance
    participant p8 as float
    participant p9 as math.isfinite
    p0-->>p1: row.get(comparator.metric_field)
    p0->>p2: _finite
    p0-->>p3: get_value(row)
    p0-->>p4: is_eligible(row)
    p0-->>p4: is_eligible(row)
    p0-->>p5: sorted(scored, key=cmp_to_key(...))
    p0-->>p6: cmp_to_key(_cmp)
    p2-->>p7: isinstance(value, bool)
    p2-->>p7: isinstance(value, (...))
    p2-->>p8: float(value)
    p2-->>p9: math.isfinite(number)
```

> Call sequence diagram shows 11 of 11 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 6 of 6 (0 omitted); unresolved 4 of 4 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. rank_rows"]
    s2["2. row.get"]
    s3["3. _finite"]
    s4["4. isinstance"]
    s5["5. isinstance"]
    s6["6. float"]
    s7["7. math.isfinite"]
    s8["8. get_value"]
    s9["9. is_eligible"]
    s10["10. is_eligible"]
    s11["11. sorted"]
    s12["12. cmp_to_key"]
    s1 -. "row.get(comparator.metric_field)" .-> s2
    s1 -->|"_finite(get_value(...))"| s3
    s3 -. "isinstance(value, bool)" .-> s4
    s3 -. "isinstance(value, (...))" .-> s5
    s3 -. "float(value)" .-> s6
    s3 -. "math.isfinite(number)" .-> s7
    s1 -. "get_value(row)" .-> s8
    s1 -. "is_eligible(row)" .-> s9
    s1 -. "is_eligible(row)" .-> s10
    s1 -. "sorted(scored, key=cmp_to_key(...))" .-> s11
    s1 -. "cmp_to_key(_cmp)" .-> s12
    click s1 "../modules/objective_comparator.md"
    click s3 "../modules/objective_comparator.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `rank_rows` | `rows: Iterable[Mapping[str, Any]]`, `comparator: ObjectiveComparator`, `value: Optional[Callable[[Mapping[str, Any]], Any]]`, `eligible: Optional[Callable[[Mapping[str, Any]], bool]]` | - | - | `...` |
| `row.get` | - | - | - | - |
| `_finite` | `value: Any` | - | - | `None`, `...` |
| `isinstance` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `float` | - | - | - | - |
| `math.isfinite` | - | - | - | - |
| `get_value` | - | - | - | - |
| `is_eligible` | - | - | - | - |
| `is_eligible` | - | - | - | - |
| `sorted` | - | - | - | - |
| `cmp_to_key` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| rank_rows | row.get | 192 | `row.get(comparator.metric_field)` |
| rank_rows | _finite | 193 | `_finite(get_value(...))` |
| _finite | isinstance | 58 | `isinstance(value, bool)` |
| _finite | isinstance | 58 | `isinstance(value, (...))` |
| _finite | float | 60 | `float(value)` |
| _finite | math.isfinite | 61 | `math.isfinite(number)` |
| rank_rows | get_value | 193 | `get_value(row)` |
| rank_rows | is_eligible | 194 | `is_eligible(row)` |
| rank_rows | is_eligible | 195 | `is_eligible(row)` |
| rank_rows | sorted | 207 | `sorted(scored, key=cmp_to_key(...))` |
| rank_rows | cmp_to_key | 207 | `cmp_to_key(_cmp)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `rank_rows` | `row.get` | 192 |
| external_call | `_finite` | `isinstance` | 58 |
| external_call | `_finite` | `math.isfinite` | 61 |
| unresolved_call | `rank_rows` | `get_value` | 193 |
| unresolved_call | `rank_rows` | `is_eligible` | 194 |
| unresolved_call | `rank_rows` | `is_eligible` | 195 |
| external_call | `rank_rows` | `sorted` | 207 |
| external_call | `rank_rows` | `cmp_to_key` | 207 |

## Behavior

This flow starts at `rank_rows` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
