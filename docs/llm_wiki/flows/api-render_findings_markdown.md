# render_findings_markdown

**Entry point:** `render_findings_markdown` (`api`)
**Source:** [insights_feedback](../modules/insights_feedback.md)
**Modules touched:** [insights_feedback](../modules/insights_feedback.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as render_findings_markdown
    participant p1 as datetime.now(…).isoformat
    participant p2 as datetime.now
    participant p3 as lines.append
    participant p4 as sorted
    participant p5 as extra.items
    participant p6 as insight_summary.strip
    participant p7 as '\n'.join
    p0-->>p1: datetime.now(…).isoformat
    p0-->>p2: datetime.now(timezone.utc)
    p0-->>p3: lines.append(...)
    p0-->>p3: lines.append(...)
    p0-->>p4: sorted(extra.items(...))
    p0-->>p5: extra.items
    p0-->>p3: lines.append(...)
    p0-->>p3: lines.append('---')
    p0-->>p3: lines.append('')
    p0-->>p3: lines.append(...)
    p0-->>p3: lines.append('')
    p0-->>p3: lines.append(...)
    p0-->>p3: lines.append('')
    p0-->>p3: lines.append(insight_summary.strip(...))
    p0-->>p6: insight_summary.strip
    p0-->>p3: lines.append('')
    p0-->>p7: '\n'.join(lines)
```

> Call sequence diagram shows 17 of 17 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 2 of 2 (0 omitted); unresolved 15 of 15 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. render_findings_markdown"]
    s2["2. datetime.now(…).isoformat"]
    s3["3. datetime.now"]
    s4["4. lines.append"]
    s5["5. lines.append"]
    s6["6. sorted"]
    s7["7. extra.items"]
    s8["8. lines.append"]
    s9["9. lines.append"]
    s10["10. lines.append"]
    s11["11. lines.append"]
    s12["12. lines.append"]
    s1 -. "datetime.now(…).isoformat(data not statically known)" .-> s2
    s1 -. "datetime.now(timezone.utc)" .-> s3
    s1 -. "lines.append(...)" .-> s4
    s1 -. "lines.append(...)" .-> s5
    s1 -. "sorted(extra.items(...))" .-> s6
    s1 -. "extra.items(data not statically known)" .-> s7
    s1 -. "lines.append(...)" .-> s8
    s1 -. "lines.append('---')" .-> s9
    s1 -. "lines.append('')" .-> s10
    s1 -. "lines.append(...)" .-> s11
    s1 -. "lines.append('')" .-> s12
    b0["mutation lines.append"]
    s1 -. "mutation lines.append" .-> b0
    b1["mutation lines.append"]
    s1 -. "mutation lines.append" .-> b1
    b2["mutation lines.append"]
    s1 -. "mutation lines.append" .-> b2
    b3["mutation lines.append"]
    s1 -. "mutation lines.append" .-> b3
    b4["mutation lines.append"]
    s1 -. "mutation lines.append" .-> b4
    b5["mutation lines.append"]
    s1 -. "mutation lines.append" .-> b5
    b6["mutation lines.append"]
    s1 -. "mutation lines.append" .-> b6
    b7["mutation lines.append"]
    s1 -. "mutation lines.append" .-> b7
    click s1 "../modules/insights_feedback.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
    class b2 boundary
    class b3 boundary
    class b4 boundary
    class b5 boundary
    class b6 boundary
    class b7 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `render_findings_markdown` | `skill_id: str`, `subject_id: str`, `variant: str`, `research_id: str`, `insight_summary: str`, `primary_metric: Optional[float]`, `metric_name: Optional[str]`, `iterations: int` | - | - | `...` |
| `datetime.now(…).isoformat` | - | - | - | - |
| `datetime.now` | - | - | - | - |
| `lines.append` | - | - | - | - |
| `lines.append` | - | - | - | - |
| `sorted` | - | - | - | - |
| `extra.items` | - | - | - | - |
| `lines.append` | - | - | - | - |
| `lines.append` | - | - | - | - |
| `lines.append` | - | - | - | - |
| `lines.append` | - | - | - | - |
| `lines.append` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| render_findings_markdown | datetime.now(…).isoformat | 78 | `datetime.now(timezone.utc).isoformat(data not statically known)` |
| render_findings_markdown | datetime.now | 78 | `datetime.now(timezone.utc)` |
| render_findings_markdown | lines.append | 89 | `lines.append(...)` |
| render_findings_markdown | lines.append | 91 | `lines.append(...)` |
| render_findings_markdown | sorted | 93 | `sorted(extra.items(...))` |
| render_findings_markdown | extra.items | 93 | `extra.items(data not statically known)` |
| render_findings_markdown | lines.append | 94 | `lines.append(...)` |
| render_findings_markdown | lines.append | 95 | `lines.append('---')` |
| render_findings_markdown | lines.append | 96 | `lines.append('')` |
| render_findings_markdown | lines.append | 97 | `lines.append(...)` |
| render_findings_markdown | lines.append | 98 | `lines.append('')` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `lines.append` | `render_findings_markdown` | 89 |
| mutation | `lines.append` | `render_findings_markdown` | 91 |
| mutation | `lines.append` | `render_findings_markdown` | 94 |
| mutation | `lines.append` | `render_findings_markdown` | 95 |
| mutation | `lines.append` | `render_findings_markdown` | 96 |
| mutation | `lines.append` | `render_findings_markdown` | 97 |
| mutation | `lines.append` | `render_findings_markdown` | 98 |
| mutation | `lines.append` | `render_findings_markdown` | 99 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `render_findings_markdown` | `datetime.now(timezone.utc).isoformat` | 78 |
| external_call | `render_findings_markdown` | `datetime.now` | 78 |
| external_call | `render_findings_markdown` | `sorted` | 93 |
| unresolved_call | `render_findings_markdown` | `extra.items` | 93 |
| step_limit | `render_findings_markdown` | `first 12 steps` | 0 |

## Behavior

This flow starts at `render_findings_markdown` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
