# stage_trial_or_none

**Entry point:** `stage_trial_or_none` (`api`)
**Source:** [trial_workspace](../modules/trial_workspace.md)
**Modules touched:** [trial_workspace](../modules/trial_workspace.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as stage_trial_or_none
    participant p1 as stage_trial_workspace
    participant p2 as logger.warning (src/core/trial_workspace.py:stage_trial_or_none)
    participant p3 as Path
    participant p4 as dst.mkdir
    participant p5 as sorted
    participant p6 as src.iterdir
    participant p7 as entry.is_dir
    participant p8 as shutil.copytree
    participant p9 as entry.is_file
    participant p10 as shutil.copy2
    participant p11 as logger.warning (src/core/trial_workspace.py:stage_trial_workspace)
    p0->>p1: stage_trial_workspace
    p0-->>p2: logger.warning (src/core/trial_workspace.py:stage_trial_or_none)(…)
    p1-->>p3: Path(session_workspace)
    p1-->>p3: Path(trial_dir)
    p1-->>p4: dst.mkdir(parents=True, exist_ok=True)
    p1-->>p5: sorted(src.iterdir(...))
    p1-->>p6: src.iterdir
    p1-->>p7: entry.is_dir
    p1-->>p8: shutil.copytree(entry, ..., dirs_exist_ok=True)
    p1-->>p9: entry.is_file
    p1-->>p10: shutil.copy2(entry, ...)
    p1-->>p11: logger.warning (src/core/trial_workspace.py:stage_trial_workspace)('Trial staging skipped s ( s) the trial may miss this state', entry, exc)
```

> Call sequence diagram shows 12 of 12 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 5 of 5 (0 omitted); unresolved 6 of 6 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. stage_trial_or_none"]
    s2["2. stage_trial_workspace"]
    s3["3. Path"]
    s4["4. Path"]
    s5["5. dst.mkdir"]
    s6["6. sorted"]
    s7["7. src.iterdir"]
    s8["8. entry.is_dir"]
    s9["9. shutil.copytree"]
    s10["10. entry.is_file"]
    s11["11. shutil.copy2"]
    s12["12. logger.warning (src/core/trial_workspace.py:stage_trial_workspace)"]
    s1 -->|"stage_trial_workspace(session_workspace, trial_dir)"| s2
    s2 -. "Path(session_workspace)" .-> s3
    s2 -. "Path(trial_dir)" .-> s4
    s2 -. "dst.mkdir(parents=True, exist_ok=True)" .-> s5
    s2 -. "sorted(src.iterdir(...))" .-> s6
    s2 -. "src.iterdir(data not statically known)" .-> s7
    s2 -. "entry.is_dir(data not statically known)" .-> s8
    s2 -. "shutil.copytree(entry, ..., dirs_exist_ok=True)" .-> s9
    s2 -. "entry.is_file(data not statically known)" .-> s10
    s2 -. "shutil.copy2(entry, ...)" .-> s11
    s2 -. "logger.warning (src/core/trial_workspace.py:stage_trial_workspace)('Trial staging skipped %s (%s); the trial may miss this state', entry, exc)" .-> s12
    b0["filesystem_write shutil.copytree"]
    s2 -. "filesystem_write shutil.copytree" .-> b0
    b1["filesystem_write shutil.copy2"]
    s2 -. "filesystem_write shutil.copy2" .-> b1
    click s1 "../modules/trial_workspace.md"
    click s2 "../modules/trial_workspace.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `stage_trial_or_none` | `session_workspace: str`, `trial_dir: str` | - | - | `trial_dir`, `None` |
| `stage_trial_workspace` | `session_workspace: str`, `trial_dir: str` | `_STAGE_IGNORE` | - | `staged` |
| `Path` | - | - | - | - |
| `Path` | - | - | - | - |
| `dst.mkdir` | - | - | - | - |
| `sorted` | - | - | - | - |
| `src.iterdir` | - | - | - | - |
| `entry.is_dir` | - | - | - | - |
| `shutil.copytree` | - | - | - | - |
| `entry.is_file` | - | - | - | - |
| `shutil.copy2` | - | - | - | - |
| `logger.warning (src/core/trial_workspace.py:stage_trial_workspace)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| stage_trial_or_none | stage_trial_workspace | 144 | `stage_trial_workspace(session_workspace, trial_dir)` |
| stage_trial_workspace | Path | 114 | `Path(session_workspace)` |
| stage_trial_workspace | Path | 115 | `Path(trial_dir)` |
| stage_trial_workspace | dst.mkdir | 116 | `dst.mkdir(parents=True, exist_ok=True)` |
| stage_trial_workspace | sorted | 118 | `sorted(src.iterdir(...))` |
| stage_trial_workspace | src.iterdir | 118 | `src.iterdir(data not statically known)` |
| stage_trial_workspace | entry.is_dir | 122 | `entry.is_dir(data not statically known)` |
| stage_trial_workspace | shutil.copytree | 123 | `shutil.copytree(entry, ..., dirs_exist_ok=True)` |
| stage_trial_workspace | entry.is_file | 124 | `entry.is_file(data not statically known)` |
| stage_trial_workspace | shutil.copy2 | 125 | `shutil.copy2(entry, ...)` |
| stage_trial_workspace | logger.warning (src/core/trial_workspace.py:stage_trial_workspace) | 130 | `logger.warning('Trial staging skipped %s (%s); the trial may miss this state', entry, exc)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_write | `shutil.copytree` | `stage_trial_workspace` | 123 |
| filesystem_write | `shutil.copy2` | `stage_trial_workspace` | 125 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `stage_trial_workspace` | `dst.mkdir` | 116 |
| external_call | `stage_trial_workspace` | `sorted` | 118 |
| unresolved_call | `stage_trial_workspace` | `src.iterdir` | 118 |
| unresolved_call | `stage_trial_workspace` | `entry.is_dir` | 122 |
| unresolved_call | `stage_trial_workspace` | `entry.is_file` | 124 |
| unresolved_call | `stage_trial_workspace` | `logger.warning` | 130 |
| step_limit | `stage_trial_or_none` | `first 12 steps` | 0 |

## Behavior

This flow starts at `stage_trial_or_none` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
