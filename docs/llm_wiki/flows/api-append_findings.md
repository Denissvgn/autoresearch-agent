# append_findings

**Entry point:** `append_findings` (`api`)
**Source:** [insights_feedback](../modules/insights_feedback.md)
**Modules touched:** [insights_feedback](../modules/insights_feedback.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as append_findings
    participant p1 as prior_findings_path
    participant p2 as path.parent.mkdir
    participant p3 as render_findings_markdown
    participant p4 as path.write_text
    participant p5 as _safe_filename_component
    participant p6 as datetime.now(…).isoformat
    participant p7 as datetime.now
    participant p8 as lines.append
    participant p9 as Path
    participant p10 as sorted
    participant p11 as extra.items
    participant p12 as insight_summary.strip
    participant p13 as '\n'.join
    participant p14 as re.sub
    p0->>p1: prior_findings_path
    p0-->>p2: path.parent.mkdir(parents=True, exist_ok=True)
    p0->>p3: render_findings_markdown
    p0-->>p4: path.write_text(body, encoding='utf-8')
    p1->>p5: _safe_filename_component
    p3-->>p6: datetime.now(…).isoformat
    p1->>p5: _safe_filename_component
    p3-->>p7: datetime.now(timezone.utc)
    p1->>p5: _safe_filename_component
    p3-->>p8: lines.append(...)
    p1-->>p9: Path(skill_dir)
    p3-->>p8: lines.append(...)
    p3-->>p10: sorted(extra.items(...))
    p3-->>p11: extra.items
    p3-->>p8: lines.append(...)
    p3-->>p8: lines.append('---')
    p3-->>p8: lines.append('')
    p3-->>p8: lines.append(...)
    p3-->>p8: lines.append('')
    p3-->>p8: lines.append(...)
    p3-->>p8: lines.append('')
    p3-->>p8: lines.append(insight_summary.strip(...))
    p3-->>p12: insight_summary.strip
    p3-->>p8: lines.append('')
    p3-->>p13: '\n'.join(lines)
    p5-->>p14: re.sub('[^A-Za-z0-9._-]', '_', value)
```

> Call sequence diagram shows 26 of 26 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 4 of 4 (0 omitted); unresolved 17 of 17 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. append_findings"]
    s2["2. prior_findings_path"]
    s3["3. _safe_filename_component"]
    s4["4. re.sub"]
    s5["5. _safe_filename_component"]
    s6["6. _safe_filename_component"]
    s7["7. Path"]
    s8["8. path.parent.mkdir"]
    s9["9. render_findings_markdown"]
    s10["10. datetime.now(…).isoformat"]
    s11["11. datetime.now"]
    s12["12. lines.append"]
    s1 -->|"prior_findings_path(skill_dir, subject_id=subject_id, variant=variant, research_id=research_id)"| s2
    s2 -->|"_safe_filename_component(subject_id)"| s3
    s3 -. "re.sub('[^A-Za-z0-9._-]', '_', value)" .-> s4
    s2 -->|"_safe_filename_component(variant)"| s5
    s2 -->|"_safe_filename_component(research_id)"| s6
    s2 -. "Path(skill_dir)" .-> s7
    s1 -. "path.parent.mkdir(parents=True, exist_ok=True)" .-> s8
    s1 -->|"render_findings_markdown(…)"| s9
    s9 -. "datetime.now(…).isoformat(data not statically known)" .-> s10
    s9 -. "datetime.now(timezone.utc)" .-> s11
    s9 -. "lines.append(...)" .-> s12
    b0["filesystem_write path.write_text"]
    s1 -. "filesystem_write path.write_text" .-> b0
    b1["mutation lines.append"]
    s9 -. "mutation lines.append" .-> b1
    b2["mutation lines.append"]
    s9 -. "mutation lines.append" .-> b2
    b3["mutation lines.append"]
    s9 -. "mutation lines.append" .-> b3
    b4["mutation lines.append"]
    s9 -. "mutation lines.append" .-> b4
    b5["mutation lines.append"]
    s9 -. "mutation lines.append" .-> b5
    b6["mutation lines.append"]
    s9 -. "mutation lines.append" .-> b6
    b7["mutation lines.append"]
    s9 -. "mutation lines.append" .-> b7
    click s1 "../modules/insights_feedback.md"
    click s2 "../modules/insights_feedback.md"
    click s3 "../modules/insights_feedback.md"
    click s5 "../modules/insights_feedback.md"
    click s6 "../modules/insights_feedback.md"
    click s9 "../modules/insights_feedback.md"
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
| `append_findings` | `skill_dir: Path`, `skill_id: str`, `subject_id: str`, `variant: str`, `research_id: str`, `insight_summary: str`, `primary_metric: Optional[float]`, `metric_name: Optional[str]` | - | - | `path` |
| `prior_findings_path` | `skill_dir: Path`, `subject_id: str`, `variant: str`, `research_id: str` | - | - | `...` |
| `_safe_filename_component` | `value: str` | - | - | `...` |
| `re.sub` | - | - | - | - |
| `_safe_filename_component` | `value: str` | - | - | `...` |
| `_safe_filename_component` | `value: str` | - | - | `...` |
| `Path` | - | - | - | - |
| `path.parent.mkdir` | - | - | - | - |
| `render_findings_markdown` | `skill_id: str`, `subject_id: str`, `variant: str`, `research_id: str`, `insight_summary: str`, `primary_metric: Optional[float]`, `metric_name: Optional[str]`, `iterations: int` | - | - | `...` |
| `datetime.now(…).isoformat` | - | - | - | - |
| `datetime.now` | - | - | - | - |
| `lines.append` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| append_findings | prior_findings_path | 126 | `prior_findings_path(skill_dir, subject_id=subject_id, variant=variant, research_id=research_id)` |
| prior_findings_path | _safe_filename_component | 47 | `_safe_filename_component(subject_id)` |
| _safe_filename_component | re.sub | 32 | `re.sub('[^A-Za-z0-9._-]', '_', value)` |
| prior_findings_path | _safe_filename_component | 48 | `_safe_filename_component(variant)` |
| prior_findings_path | _safe_filename_component | 49 | `_safe_filename_component(research_id)` |
| prior_findings_path | Path | 51 | `Path(skill_dir)` |
| append_findings | path.parent.mkdir | 129 | `path.parent.mkdir(parents=True, exist_ok=True)` |
| append_findings | render_findings_markdown | 130 | `render_findings_markdown(skill_id=skill_id, subject_id=subject_id, variant=variant, research_id=research_id, insight_summary=insight_summary, primary_metric=primary_metric, metric_name=metric_name, iterations=iterations, completed_at=completed_at, extra=extra)` |
| render_findings_markdown | datetime.now(…).isoformat | 78 | `datetime.now(timezone.utc).isoformat(data not statically known)` |
| render_findings_markdown | datetime.now | 78 | `datetime.now(timezone.utc)` |
| render_findings_markdown | lines.append | 89 | `lines.append(...)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_write | `path.write_text` | `append_findings` | 142 |
| mutation | `lines.append` | `render_findings_markdown` | 89 |
| mutation | `lines.append` | `render_findings_markdown` | 91 |
| mutation | `lines.append` | `render_findings_markdown` | 94 |
| mutation | `lines.append` | `render_findings_markdown` | 95 |
| mutation | `lines.append` | `render_findings_markdown` | 96 |
| mutation | `lines.append` | `render_findings_markdown` | 97 |
| mutation | `lines.append` | `render_findings_markdown` | 98 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `_safe_filename_component` | `re.sub` | 32 |
| unresolved_call | `append_findings` | `path.parent.mkdir` | 129 |
| unresolved_call | `render_findings_markdown` | `datetime.now(timezone.utc).isoformat` | 78 |
| external_call | `render_findings_markdown` | `datetime.now` | 78 |
| step_limit | `append_findings` | `first 12 steps` | 0 |

## Behavior

This flow starts at `append_findings` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
