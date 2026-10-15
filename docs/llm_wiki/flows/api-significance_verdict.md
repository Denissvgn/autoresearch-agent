# significance_verdict

**Entry point:** `significance_verdict` (`api`)
**Source:** [significance](../modules/significance.md)
**Modules touched:** [significance](../modules/significance.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as significance_verdict
    participant p1 as len (src/core/significance.py:significance_verdict)
    participant p2 as mean_std
    participant p3 as len (src/core/significance.py:mean_std)
    participant p4 as ValueError
    participant p5 as sum
    p0-->>p1: len (src/core/significance.py:significance_verdict)(candidate)
    p0-->>p1: len (src/core/significance.py:significance_verdict)(reference)
    p0->>p2: mean_std
    p0->>p2: mean_std
    p0-->>p1: len (src/core/significance.py:significance_verdict)(candidate)
    p0-->>p1: len (src/core/significance.py:significance_verdict)(reference)
    p2-->>p3: len (src/core/significance.py:mean_std)(values)
    p2-->>p4: ValueError('mean_std requires at least one value')
    p2-->>p5: sum(values)
    p2-->>p5: sum(...)
```

> Call sequence diagram shows 10 of 10 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 8 of 8 (0 omitted); unresolved 0 of 0 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. significance_verdict"]
    s2["2. len (src/core/significance.py:significance_verdict)"]
    s3["3. len (src/core/significance.py:significance_verdict)"]
    s4["4. mean_std"]
    s5["5. len (src/core/significance.py:mean_std)"]
    s6["6. ValueError"]
    s7["7. sum"]
    s8["8. sum"]
    s9["9. mean_std"]
    s10["10. len (src/core/significance.py:significance_verdict)"]
    s11["11. len (src/core/significance.py:significance_verdict)"]
    s1 -. "len (src/core/significance.py:significance_verdict)(candidate)" .-> s2
    s1 -. "len (src/core/significance.py:significance_verdict)(reference)" .-> s3
    s1 -->|"mean_std(candidate)"| s4
    s4 -. "len (src/core/significance.py:mean_std)(values)" .-> s5
    s4 -. "ValueError('mean_std requires at least one value')" .-> s6
    s4 -. "sum(values)" .-> s7
    s4 -. "sum(...)" .-> s8
    s1 -->|"mean_std(reference)"| s9
    s1 -. "len (src/core/significance.py:significance_verdict)(candidate)" .-> s10
    s1 -. "len (src/core/significance.py:significance_verdict)(reference)" .-> s11
    click s1 "../modules/significance.md"
    click s4 "../modules/significance.md"
    click s9 "../modules/significance.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `significance_verdict` | `candidate: Sequence[float]`, `reference: Sequence[float]`, `direction: str`, `min_sigma: float`, `min_samples: int` | `INCONCLUSIVE`, `SIGNIFICANT`, `REGRESSION`, `INCONCLUSIVE`, `SIGNIFICANT`, `REGRESSION`, `INCONCLUSIVE` | - | `INCONCLUSIVE`, `...`, `SIGNIFICANT`, `REGRESSION`, `INCONCLUSIVE` |
| `len (src/core/significance.py:significance_verdict)` | - | - | - | - |
| `len (src/core/significance.py:significance_verdict)` | - | - | - | - |
| `mean_std` | `values: Sequence[float]` | - | - | `(...)`, `(...)` |
| `len (src/core/significance.py:mean_std)` | - | - | - | - |
| `ValueError` | - | - | - | - |
| `sum` | - | - | - | - |
| `sum` | - | - | - | - |
| `mean_std` | `values: Sequence[float]` | - | - | `(...)`, `(...)` |
| `len (src/core/significance.py:significance_verdict)` | - | - | - | - |
| `len (src/core/significance.py:significance_verdict)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| significance_verdict | len (src/core/significance.py:significance_verdict) | 72 | `len(candidate)` |
| significance_verdict | len (src/core/significance.py:significance_verdict) | 72 | `len(reference)` |
| significance_verdict | mean_std | 74 | `mean_std(candidate)` |
| mean_std | len (src/core/significance.py:mean_std) | 45 | `len(values)` |
| mean_std | ValueError | 47 | `ValueError('mean_std requires at least one value')` |
| mean_std | sum | 48 | `sum(values)` |
| mean_std | sum | 51 | `sum(...)` |
| significance_verdict | mean_std | 75 | `mean_std(reference)` |
| significance_verdict | len (src/core/significance.py:significance_verdict) | 82 | `len(candidate)` |
| significance_verdict | len (src/core/significance.py:significance_verdict) | 82 | `len(reference)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `mean_std` | `ValueError` | 47 |
| external_call | `mean_std` | `sum` | 48 |
| external_call | `mean_std` | `sum` | 51 |

## Behavior

This flow starts at `significance_verdict` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
