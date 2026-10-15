# stage_trial_workspace

**Entry point:** `stage_trial_workspace` (`api`)
**Source:** [trial_workspace](../modules/trial_workspace.md)
**Modules touched:** [fs_safety](../modules/fs_safety.md), [trial_workspace](../modules/trial_workspace.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as stage_trial_workspace
    participant p1 as copy_tree_regular_files
    participant p2 as _open_root
    participant p3 as _copy_entry_at
    participant p4 as _copy_dir_at
    participant p5 as _write_at
    participant p6 as FilesystemSafetyError
    participant p7 as _leaf_denial_reason
    participant p8 as _unlink_quiet
    participant p9 as Path
    participant p10 as dst.mkdir
    participant p11 as str (src/core/trial_workspace.py:stage_trial_workspace)
    participant p12 as os.makedirs
    participant p13 as sorted (src/core/fs_safety.py:copy_tree_regular_files)
    participant p14 as os.listdir (src/core/fs_safety.py:copy_tree_regular_files)
    participant p15 as on_skip (src/core/fs_safety.py:copy_tree_regular_files)
    participant p16 as str (src/core/fs_safety.py:copy_tree_regular_files)
    participant p17 as os.close (src/core/fs_safety.py:copy_tree_regular_files)
    participant p18 as os.open (src/core/fs_safety.py:_open_root)
    participant p19 as os.stat (src/core/fs_safety.py:_copy_entry_at)
    participant p20 as stat_mod.S_ISLNK (src/core/fs_safety.py:_copy_entry_at)
    participant p21 as stat_mod.S_ISDIR
    participant p22 as os.mkdir
    participant p23 as os.open (src/core/fs_safety.py:_copy_entry_at)
    participant p24 as os.close (src/core/fs_safety.py:_copy_entry_at)
    p0->>p1: copy_tree_regular_files
    p1->>p2: _open_root
    p1->>p3: _copy_entry_at
    p3->>p4: _copy_dir_at
    p3->>p5: _write_at
    p2->>p6: FilesystemSafetyError
    p5->>p7: _leaf_denial_reason
    p5->>p8: _unlink_quiet
    p0-->>p9: Path(session_workspace)
    p0-->>p10: dst.mkdir(parents=True, exist_ok=True)
    p0-->>p9: Path(trial_dir)
    p0-->>p11: str (src/core/trial_workspace.py:stage_trial_workspace)(src)
    p0-->>p11: str (src/core/trial_workspace.py:stage_trial_workspace)(dst)
    p1-->>p12: os.makedirs(dst_root, exist_ok=True)
    p1-->>p13: sorted (src/core/fs_safety.py:copy_tree_regular_files)(os.listdir(...))
    p1-->>p14: os.listdir (src/core/fs_safety.py:copy_tree_regular_files)(src_fd)
    p1-->>p15: on_skip (src/core/fs_safety.py:copy_tree_regular_files)(name, exc.reason)
    p1-->>p15: on_skip (src/core/fs_safety.py:copy_tree_regular_files)(name, ...)
    p1-->>p16: str (src/core/fs_safety.py:copy_tree_regular_files)(exc)
    p1-->>p17: os.close (src/core/fs_safety.py:copy_tree_regular_files)(dst_fd)
    p1-->>p17: os.close (src/core/fs_safety.py:copy_tree_regular_files)(src_fd)
    p2-->>p18: os.open (src/core/fs_safety.py:_open_root)(root, ...)
    p3-->>p19: os.stat (src/core/fs_safety.py:_copy_entry_at)(name, dir_fd=src_fd, follow_symlinks=False)
    p3-->>p20: stat_mod.S_ISLNK (src/core/fs_safety.py:_copy_entry_at)(st.st_mode)
    p3-->>p21: stat_mod.S_ISDIR(st.st_mode)
    p3-->>p22: os.mkdir(name, 493, dir_fd=dst_fd)
    p3-->>p23: os.open (src/core/fs_safety.py:_copy_entry_at)(name, _DIR_OPEN_FLAGS, dir_fd=src_fd)
    p3-->>p23: os.open (src/core/fs_safety.py:_copy_entry_at)(name, _DIR_OPEN_FLAGS, dir_fd=dst_fd)
    p3-->>p24: os.close (src/core/fs_safety.py:_copy_entry_at)(child_src)
    p3-->>p24: os.close (src/core/fs_safety.py:_copy_entry_at)(child_src)
```

> Call sequence diagram shows 30 of 58 interactions; 28 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 19 of 34 (15 omitted); unresolved 3 of 7 (4 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/fs_safety.py:copy_tree_regular_files` | 5 | [src/core/fs_safety.py](../modules/fs_safety.md) | internal | 1 |
| `src/core/fs_safety.py:_copy_entry_at` | 13 | [src/core/fs_safety.py](../modules/fs_safety.md) | internal | 3 |
| `src/core/fs_safety.py:_copy_dir_at` | 22 | - | external | 3 |
| `src/core/fs_safety.py:_copy_dir_at` | 22 | [src/core/fs_safety.py](../modules/fs_safety.md) | internal | 1 |
| `src/core/fs_safety.py:_copy_dir_at` | 22 | - | unresolved | 2 |
| `src/core/fs_safety.py:_copy_entry_at` | 13 | - | external | 4 |
| `src/core/fs_safety.py:_copy_entry_at` | 13 | - | unresolved | 1 |
| `src/core/fs_safety.py:_write_at` | 36 | - | external | 5 |
> Omission summary shows 8 of 12 groups; 4 further groups are not expanded here. Counts above include all omitted interactions.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. stage_trial_workspace"]
    s2["2. Path"]
    s3["3. Path"]
    s4["4. dst.mkdir"]
    s5["5. copy_tree_regular_files"]
    s6["6. os.makedirs"]
    s7["7. _open_root"]
    s8["8. os.open (src/core/fs_safety.py:_open_root)"]
    s9["9. FilesystemSafetyError"]
    s10["10. _open_root"]
    s11["11. sorted (src/core/fs_safety.py:copy_tree_regular_files)"]
    s12["12. os.listdir (src/core/fs_safety.py:copy_tree_regular_files)"]
    s1 -. "Path(session_workspace)" .-> s2
    s1 -. "Path(trial_dir)" .-> s3
    s1 -. "dst.mkdir(parents=True, exist_ok=True)" .-> s4
    s1 -->|"copy_tree_regular_files(str(...), str(...), ignore=_STAGE_IGNORE, on_skip=_on_skip)"| s5
    s5 -. "os.makedirs(dst_root, exist_ok=True)" .-> s6
    s5 -->|"_open_root(src_root, 'copy')"| s7
    s7 -. "os.open (src/core/fs_safety.py:_open_root)(root, ...)" .-> s8
    s7 -->|"FilesystemSafetyError(operation, root, ...)"| s9
    s5 -->|"_open_root(dst_root, 'copy')"| s10
    s5 -. "sorted (src/core/fs_safety.py:copy_tree_regular_files)(os.listdir(...))" .-> s11
    s5 -. "os.listdir (src/core/fs_safety.py:copy_tree_regular_files)(src_fd)" .-> s12
    click s1 "../modules/trial_workspace.md"
    click s5 "../modules/fs_safety.md"
    click s7 "../modules/fs_safety.md"
    click s9 "../modules/fs_safety.md"
    click s10 "../modules/fs_safety.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `stage_trial_workspace` | `session_workspace: str`, `trial_dir: str` | `_STAGE_IGNORE` | - | `fs_safety.copy_tree_regular_files(...)` |
| `Path` | - | - | - | - |
| `Path` | - | - | - | - |
| `dst.mkdir` | - | - | - | - |
| `copy_tree_regular_files` | `src_root: str`, `dst_root: str`, `ignore: Container[str]`, `on_skip: Optional[SkipCallback]` | `FilesystemSafetyError` | - | `copied` |
| `os.makedirs` | - | - | - | - |
| `_open_root` | `root: str`, `operation: str` | `os` | - | `os.open(...)` |
| `os.open (src/core/fs_safety.py:_open_root)` | - | - | - | - |
| `FilesystemSafetyError` | - | - | - | - |
| `_open_root` | `root: str`, `operation: str` | `os` | - | `os.open(...)` |
| `sorted (src/core/fs_safety.py:copy_tree_regular_files)` | - | - | - | - |
| `os.listdir (src/core/fs_safety.py:copy_tree_regular_files)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| stage_trial_workspace | Path | 118 | `Path(session_workspace)` |
| stage_trial_workspace | Path | 119 | `Path(trial_dir)` |
| stage_trial_workspace | dst.mkdir | 120 | `dst.mkdir(parents=True, exist_ok=True)` |
| stage_trial_workspace | copy_tree_regular_files | 128 | `fs_safety.copy_tree_regular_files(str(...), str(...), ignore=_STAGE_IGNORE, on_skip=_on_skip)` |
| copy_tree_regular_files | os.makedirs | 378 | `os.makedirs(dst_root, exist_ok=True)` |
| copy_tree_regular_files | _open_root | 379 | `_open_root(src_root, 'copy')` |
| _open_root | os.open (src/core/fs_safety.py:_open_root) | 80 | `os.open(root, ...)` |
| _open_root | FilesystemSafetyError | 82 | `FilesystemSafetyError(operation, root, ...)` |
| copy_tree_regular_files | _open_root | 381 | `_open_root(dst_root, 'copy')` |
| copy_tree_regular_files | sorted (src/core/fs_safety.py:copy_tree_regular_files) | 384 | `sorted(os.listdir(...))` |
| copy_tree_regular_files | os.listdir (src/core/fs_safety.py:copy_tree_regular_files) | 384 | `os.listdir(src_fd)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `stage_trial_workspace` | `dst.mkdir` | 120 |
| external_call | `copy_tree_regular_files` | `os.makedirs` | 378 |
| external_call | `_open_root` | `os.open` | 80 |
| external_call | `copy_tree_regular_files` | `sorted` | 384 |
| external_call | `copy_tree_regular_files` | `os.listdir` | 384 |
| step_limit | `stage_trial_workspace` | `first 12 steps` | 0 |

## Behavior

This flow starts at `stage_trial_workspace` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
