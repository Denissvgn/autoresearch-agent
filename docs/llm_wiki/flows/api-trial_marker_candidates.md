# trial_marker_candidates

**Entry point:** `trial_marker_candidates` (`api`)
**Source:** [trial_workspace](../modules/trial_workspace.md)
**Modules touched:** [trial_workspace](../modules/trial_workspace.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as trial_marker_candidates
    participant p1 as Path
    participant p2 as list
    p0-->>p1: Path(trial_dir)
    p0-->>p2: list(marker_paths)
```

> Call sequence diagram shows 2 of 2 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 2 of 2 (0 omitted); unresolved 0 of 0 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. trial_marker_candidates"]
    s2["2. Path"]
    s3["3. list"]
    s1 -. "Path(trial_dir)" .-> s2
    s1 -. "list(marker_paths)" .-> s3
    click s1 "../modules/trial_workspace.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `trial_marker_candidates` | `trial_dir: str`, `marker_paths: Iterable[Path]` | - | - | `...` |
| `Path` | - | - | - | - |
| `list` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| trial_marker_candidates | Path | 162 | `Path(trial_dir)` |
| trial_marker_candidates | list | 163 | `list(marker_paths)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

*No static analysis gaps detected.*

## Behavior

This flow starts at `trial_marker_candidates` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
