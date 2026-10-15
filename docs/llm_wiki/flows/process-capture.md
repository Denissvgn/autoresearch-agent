# capture

**Entry point:** `main` (`process`)
**Source:** [capture](../modules/capture.md)
**Modules touched:** [capture](../modules/capture.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as argparse.ArgumentParser
    participant p2 as ap.add_argument
    participant p3 as ap.parse_args
    participant p4 as _git
    participant p5 as sys.stderr.write
    participant p6 as discover_cases
    participant p7 as print
    participant p8 as len
    participant p9 as tempfile.TemporaryDirectory
    participant p10 as Path
    participant p11 as load_case
    participant p12 as case_id.replace
    participant p13 as workspace.mkdir
    participant p14 as host_configs.mkdir
    participant p15 as invoke
    participant p16 as str (tests/parity/capture.py:main)
    participant p17 as normalize
    participant p18 as case_path.write_text
    participant p19 as json.dumps
    participant p20 as subprocess.check_output(…).strip
    participant p21 as subprocess.check_output
    participant p22 as str (tests/parity/capture.py:_git)
    p0-->>p1: argparse.ArgumentParser(description=__doc__)
    p0-->>p2: ap.add_argument('--force', action='store_true', help='allow capture even when the git tree is dirty')
    p0-->>p3: ap.parse_args
    p0->>p4: _git
    p0-->>p5: sys.stderr.write(...)
    p0->>p4: _git
    p0->>p4: _git
    p0-->>p6: discover_cases(PARITY_DIR)
    p0-->>p7: print(...)
    p0-->>p8: len(cases)
    p0-->>p9: tempfile.TemporaryDirectory(prefix='arc011-parity-')
    p0-->>p10: Path(tmp)
    p0-->>p11: load_case(case_path)
    p0-->>p12: case_id.replace('/', '_')
    p0-->>p12: case_id.replace('/', '_')
    p0-->>p13: workspace.mkdir(parents=True)
    p0-->>p14: host_configs.mkdir(parents=True)
    p0-->>p15: invoke(case, workspace, host_configs, ...)
    p0-->>p12: case_id.replace('/', '_')
    p0-->>p16: str (tests/parity/capture.py:main)(workspace)
    p0-->>p16: str (tests/parity/capture.py:main)(host_configs)
    p0-->>p17: normalize(result, mapping)
    p0-->>p18: case_path.write_text(..., encoding='utf-8')
    p0-->>p19: json.dumps(case, indent=2)
    p0-->>p7: print(...)
    p0-->>p7: print('done.')
    p4-->>p20: subprocess.check_output(…).strip
    p4-->>p21: subprocess.check_output([...], text=True)
    p4-->>p22: str (tests/parity/capture.py:_git)(REPO_ROOT)
```

> Call sequence diagram shows 29 of 29 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 17 of 17 (0 omitted); unresolved 9 of 9 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. argparse.ArgumentParser"]
    s3["3. ap.add_argument"]
    s4["4. ap.parse_args"]
    s5["5. _git"]
    s6["6. subprocess.check_output(…).strip"]
    s7["7. subprocess.check_output"]
    s8["8. str (tests/parity/capture.py:_git)"]
    s9["9. sys.stderr.write"]
    s10["10. _git"]
    s11["11. _git"]
    s12["12. discover_cases"]
    s1 -. "argparse.ArgumentParser(description=__doc__)" .-> s2
    s1 -. "ap.add_argument('--force', action='store_true', help='allow capture even when the git tree is dirty')" .-> s3
    s1 -. "ap.parse_args(data not statically known)" .-> s4
    s1 -->|"_git([...])"| s5
    s5 -. "subprocess.check_output(…).strip(data not statically known)" .-> s6
    s5 -. "subprocess.check_output([...], text=True)" .-> s7
    s5 -. "str (tests/parity/capture.py:_git)(REPO_ROOT)" .-> s8
    s1 -. "sys.stderr.write(...)" .-> s9
    s1 -->|"_git([...])"| s10
    s1 -->|"_git([...])"| s11
    s1 -. "discover_cases(PARITY_DIR)" .-> s12
    b0["output sys.stderr.write"]
    s1 -. "output sys.stderr.write" .-> b0
    b1["output print"]
    s1 -. "output print" .-> b1
    b2["filesystem_write case_path.write_text"]
    s1 -. "filesystem_write case_path.write_text" .-> b2
    b3["output print"]
    s1 -. "output print" .-> b3
    b4["output print"]
    s1 -. "output print" .-> b4
    click s1 "../modules/capture.md"
    click s5 "../modules/capture.md"
    click s10 "../modules/capture.md"
    click s11 "../modules/capture.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
    class b2 boundary
    class b3 boundary
    class b4 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | - | `PARITY_DIR`, `WORKSPACE_TOKEN`, `HOST_CONFIGS_TOKEN` | `case[...]`, `case[...]` | `2`, `0` |
| `argparse.ArgumentParser` | - | - | - | - |
| `ap.add_argument` | - | - | - | - |
| `ap.parse_args` | - | - | - | - |
| `_git` | `args: list[str]` | - | - | `...` |
| `subprocess.check_output(…).strip` | - | - | - | - |
| `subprocess.check_output` | - | - | - | - |
| `str (tests/parity/capture.py:_git)` | - | - | - | - |
| `sys.stderr.write` | - | - | - | - |
| `_git` | `args: list[str]` | - | - | `...` |
| `_git` | `args: list[str]` | - | - | `...` |
| `discover_cases` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | argparse.ArgumentParser | 48 | `argparse.ArgumentParser(description=__doc__)` |
| main | ap.add_argument | 49 | `ap.add_argument('--force', action='store_true', help='allow capture even when the git tree is dirty')` |
| main | ap.parse_args | 54 | `ap.parse_args(data not statically known)` |
| main | _git | 56 | `_git([...])` |
| _git | subprocess.check_output(…).strip | 42 | `subprocess.check_output(['git', '-C', str(REPO_ROOT), *args], text=True).strip(data not statically known)` |
| _git | subprocess.check_output | 42 | `subprocess.check_output([...], text=True)` |
| _git | str (tests/parity/capture.py:_git) | 43 | `str(REPO_ROOT)` |
| main | sys.stderr.write | 58 | `sys.stderr.write(...)` |
| main | _git | 65 | `_git([...])` |
| main | _git | 66 | `_git([...])` |
| main | discover_cases | 67 | `discover_cases(PARITY_DIR)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| output | `sys.stderr.write` | `main` | 58 |
| output | `print` | `main` | 68 |
| filesystem_write | `case_path.write_text` | `main` | 86 |
| output | `print` | `main` | 87 |
| output | `print` | `main` | 89 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `main` | `argparse.ArgumentParser` | 48 |
| unresolved_call | `main` | `ap.add_argument` | 49 |
| unresolved_call | `main` | `ap.parse_args` | 54 |
| unresolved_call | `_git` | `subprocess.check_output(['git', '-C', str(REPO_ROOT), *args], text=True).strip` | 42 |
| external_call | `_git` | `subprocess.check_output` | 42 |
| external_call | `main` | `discover_cases` | 67 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
