# select_best_row

**Entry point:** `select_best_row` (`api`)
**Source:** [objective_comparator](../modules/objective_comparator.md)
**Modules touched:** [objective_comparator](../modules/objective_comparator.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as select_best_row
    participant p1 as row.get
    participant p2 as _finite
    participant p3 as get_value
    participant p4 as is_eligible
    participant p5 as comparator.is_better
    participant p6 as isinstance
    participant p7 as float
    participant p8 as math.isfinite
    p0-->>p1: row.get(comparator.metric_field)
    p0->>p2: _finite
    p0-->>p3: get_value(row)
    p0-->>p4: is_eligible(row)
    p0-->>p5: comparator.is_better(get_value(...), get_value(...))
    p0-->>p3: get_value(row)
    p0-->>p3: get_value(winner)
    p2-->>p6: isinstance(value, bool)
    p2-->>p6: isinstance(value, (...))
    p2-->>p7: float(value)
    p2-->>p8: math.isfinite(number)
```

> Call sequence diagram shows 11 of 11 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 4 of 4 (0 omitted); unresolved 6 of 6 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. select_best_row"]
    s2["2. row.get"]
    s3["3. _finite"]
    s4["4. isinstance"]
    s5["5. isinstance"]
    s6["6. float"]
    s7["7. math.isfinite"]
    s8["8. get_value"]
    s9["9. is_eligible"]
    s10["10. comparator.is_better"]
    s11["11. get_value"]
    s12["12. get_value"]
    s1 -. "row.get(comparator.metric_field)" .-> s2
    s1 -->|"_finite(get_value(...))"| s3
    s3 -. "isinstance(value, bool)" .-> s4
    s3 -. "isinstance(value, (...))" .-> s5
    s3 -. "float(value)" .-> s6
    s3 -. "math.isfinite(number)" .-> s7
    s1 -. "get_value(row)" .-> s8
    s1 -. "is_eligible(row)" .-> s9
    s1 -. "comparator.is_better(get_value(...), get_value(...))" .-> s10
    s1 -. "get_value(row)" .-> s11
    s1 -. "get_value(winner)" .-> s12
    click s1 "../modules/objective_comparator.md"
    click s3 "../modules/objective_comparator.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `select_best_row` | `rows: Iterable[Mapping[str, Any]]`, `comparator: ObjectiveComparator`, `value: Optional[Callable[[Mapping[str, Any]], Any]]`, `eligible: Optional[Callable[[Mapping[str, Any]], bool]]` | - | - | `winner` |
| `row.get` | - | - | - | - |
| `_finite` | `value: Any` | - | - | `None`, `...` |
| `isinstance` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `float` | - | - | - | - |
| `math.isfinite` | - | - | - | - |
| `get_value` | - | - | - | - |
| `is_eligible` | - | - | - | - |
| `comparator.is_better` | - | - | - | - |
| `get_value` | - | - | - | - |
| `get_value` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| select_best_row | row.get | 170 | `row.get(comparator.metric_field)` |
| select_best_row | _finite | 171 | `_finite(get_value(...))` |
| _finite | isinstance | 58 | `isinstance(value, bool)` |
| _finite | isinstance | 58 | `isinstance(value, (...))` |
| _finite | float | 60 | `float(value)` |
| _finite | math.isfinite | 61 | `math.isfinite(number)` |
| select_best_row | get_value | 171 | `get_value(row)` |
| select_best_row | is_eligible | 174 | `is_eligible(row)` |
| select_best_row | comparator.is_better | 179 | `comparator.is_better(get_value(...), get_value(...))` |
| select_best_row | get_value | 179 | `get_value(row)` |
| select_best_row | get_value | 179 | `get_value(winner)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `select_best_row` | `row.get` | 170 |
| external_call | `_finite` | `isinstance` | 58 |
| external_call | `_finite` | `math.isfinite` | 61 |
| unresolved_call | `select_best_row` | `get_value` | 171 |
| unresolved_call | `select_best_row` | `is_eligible` | 174 |
| unresolved_call | `select_best_row` | `comparator.is_better` | 179 |
| unresolved_call | `select_best_row` | `get_value` | 179 |

## Behavior

This flow starts at `select_best_row` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
