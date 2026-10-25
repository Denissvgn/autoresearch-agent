# ci_qualification_gates

**Entry point:** `main` (`process`)
**Source:** [ci_qualification_gates](../modules/ci_qualification_gates.md)
**Modules touched:** [builtin_harness](../modules/builtin_harness.md), [ci_qualification_gates](../modules/ci_qualification_gates.md), [claude_code_harness](../modules/claude_code_harness.md), and 5 more

**Complete modules touched:**

- [builtin_harness](../modules/builtin_harness.md)
- [ci_qualification_gates](../modules/ci_qualification_gates.md)
- [claude_code_harness](../modules/claude_code_harness.md)
- [codex_harness](../modules/codex_harness.md)
- [harness_adapter](../modules/harness_adapter.md)
- [harness_contract](../modules/harness_contract.md)
- [harnesses](../modules/harnesses.md)
- [latency_benchmark](../modules/latency_benchmark.md)

**Related modules:** [harness_contract](../modules/harness_contract.md), [harnesses](../modules/harnesses.md), [latency_benchmark](../modules/latency_benchmark.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as evaluate_gate
    participant p2 as collect_current_inputs
    participant p3 as collect_capability_report
    participant p4 as write_evidence
    participant p5 as check_pinned_inputs
    participant p6 as build_default_registry
    participant p7 as build_workload
    participant p8 as HarnessRegistry.register
    participant p9 as GateResult
    participant p10 as _descriptor
    participant p11 as scan_for_secrets
    participant p12 as check_unsupported_report
    participant p13 as redact
    participant p14 as parse_pytest_output
    participant p15 as _file_digest
    participant p16 as check_required_coverage
    participant p17 as check_skip_ownership
    participant p18 as HarnessRegistry
    participant p19 as BuiltinHarnessAdapter
    participant p20 as CodexHarnessAdapter
    participant p21 as ClaudeCodeHarnessAdapter
    participant p22 as Workload
    participant p23 as HarnessVersionError
    participant p24 as HarnessContractError
    participant p25 as argparse.ArgumentParser
    participant p26 as parser.add_argument
    participant p27 as parser.parse_args
    p0->>p1: evaluate_gate
    p0->>p2: collect_current_inputs
    p0->>p3: collect_capability_report
    p0->>p4: write_evidence
    p0->>p5: check_pinned_inputs
    p2->>p6: build_default_registry
    p2->>p7: build_workload
    p6->>p8: HarnessRegistry.register
    p1->>p9: GateResult
    p3->>p10: _descriptor
    p4->>p11: scan_for_secrets
    p3->>p12: check_unsupported_report
    p4->>p13: redact
    p1->>p14: parse_pytest_output
    p2->>p15: _file_digest
    p1->>p16: check_required_coverage
    p1->>p17: check_skip_ownership
    p6->>p18: HarnessRegistry
    p6->>p19: BuiltinHarnessAdapter
    p6->>p20: CodexHarnessAdapter
    p6->>p21: ClaudeCodeHarnessAdapter
    p7->>p22: Workload
    p8->>p23: HarnessVersionError
    p8->>p24: HarnessContractError
    p0-->>p25: argparse.ArgumentParser(description=__doc__)
    p0-->>p26: parser.add_argument('--gate', action='append', default=None)
    p0-->>p26: parser.add_argument('--live', action='store_true')
    p0-->>p26: parser.add_argument('--report-dir', default=None)
    p0-->>p26: parser.add_argument('--dry-run', action='store_true')
    p0-->>p27: parser.parse_args(argv)
```

> Call sequence diagram shows 30 of 175 interactions; 145 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 1 of 58 (57 omitted); unresolved 5 of 86 (81 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `scripts/ci_qualification_gates.py:main` | 1 | - | external | 16 |
| `scripts/ci_qualification_gates.py:evaluate_gate` | 10 | - | unresolved | 7 |
| `scripts/ci_qualification_gates.py:evaluate_gate` | 10 | - | external | 4 |
| `scripts/ci_qualification_gates.py:parse_pytest_output` | 19 | - | unresolved | 4 |
| `scripts/ci_qualification_gates.py:evaluate_gate` | 10 | [scripts/ci_qualification_gates.py](../modules/ci_qualification_gates.md) | internal | 1 |
| `scripts/ci_qualification_gates.py:redact` | 24 | - | unresolved | 2 |
| `scripts/ci_qualification_gates.py:check_required_coverage` | 30 | - | external | 1 |
| `scripts/ci_qualification_gates.py:check_required_coverage` | 30 | - | unresolved | 1 |
> Omission summary shows 8 of 34 groups; 26 further groups are not expanded here. Counts above include all omitted interactions.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. argparse.ArgumentParser"]
    s3["3. parser.add_argument"]
    s4["4. parser.add_argument"]
    s5["5. parser.add_argument"]
    s6["6. parser.add_argument"]
    s7["7. parser.parse_args"]
    s8["8. set (scripts/ci_qualification_gates.py:main)"]
    s9["9. os.environ.get"]
    s10["10. evaluate_gate"]
    s11["11. GateResult"]
    s12["12. result.errors.append"]
    s1 -. "argparse.ArgumentParser(description=__doc__)" .-> s2
    s1 -. "parser.add_argument('--gate', action='append', default=None)" .-> s3
    s1 -. "parser.add_argument('--live', action='store_true')" .-> s4
    s1 -. "parser.add_argument('--report-dir', default=None)" .-> s5
    s1 -. "parser.add_argument('--dry-run', action='store_true')" .-> s6
    s1 -. "parser.parse_args(argv)" .-> s7
    s1 -. "set (scripts/ci_qualification_gates.py:main)(args.gate)" .-> s8
    s1 -. "os.environ.get(name)" .-> s9
    s1 -->|"evaluate_gate(gate, run=run_pytest, live_opt_in=args.live, missing_env=...)"| s10
    s10 -->|"GateResult(name=gate.name, kind=gate.kind, status='pass')"| s11
    s10 -. "result.errors.append(...)" .-> s12
    b0["environment_read os.environ.get"]
    s1 -. "environment_read os.environ.get" .-> b0
    b1["mutation results.append"]
    s1 -. "mutation results.append" .-> b1
    b2["output print"]
    s1 -. "output print" .-> b2
    b3["output print"]
    s1 -. "output print" .-> b3
    b4["filesystem_read PIN_FILE.read_text"]
    s1 -. "filesystem_read PIN_FILE.read_text" .-> b4
    b5["mutation errors.extend"]
    s1 -. "mutation errors.extend" .-> b5
    b6["mutation errors.append"]
    s1 -. "mutation errors.append" .-> b6
    b7["mutation errors.extend"]
    s1 -. "mutation errors.extend" .-> b7
    click s1 "../modules/ci_qualification_gates.md"
    click s10 "../modules/ci_qualification_gates.md"
    click s11 "../modules/ci_qualification_gates.md"
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
| `main` | `argv: Optional[Sequence[str]]` | `GATES`, `run_pytest`, `PIN_FILE`, `REPO_ROOT` | - | `...` |
| `argparse.ArgumentParser` | - | - | - | - |
| `parser.add_argument` | - | - | - | - |
| `parser.add_argument` | - | - | - | - |
| `parser.add_argument` | - | - | - | - |
| `parser.add_argument` | - | - | - | - |
| `parser.parse_args` | - | - | - | - |
| `set (scripts/ci_qualification_gates.py:main)` | - | - | - | - |
| `os.environ.get` | - | - | - | - |
| `evaluate_gate` | `gate: Gate`, `run: Callable[[Sequence[str], int], tuple[int, str]]`, `owners: Sequence[SkipOwner]`, `live_opt_in: bool`, `missing_env: Sequence[str]` | `LIVE_OPT_IN_ENV`, `BUDGET_ENV`, `subprocess` | `result.status`, `result.status`, `result.status`, `result.duration_s`, `result.passed`, `result.failed`, `result.skipped`, `result.log` | `result`, `result`, `result`, `result` |
| `GateResult` | - | - | - | - |
| `result.errors.append` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | argparse.ArgumentParser | 464 | `argparse.ArgumentParser(description=__doc__)` |
| main | parser.add_argument | 465 | `parser.add_argument('--gate', action='append', default=None)` |
| main | parser.add_argument | 466 | `parser.add_argument('--live', action='store_true')` |
| main | parser.add_argument | 467 | `parser.add_argument('--report-dir', default=None)` |
| main | parser.add_argument | 468 | `parser.add_argument('--dry-run', action='store_true')` |
| main | parser.parse_args | 469 | `parser.parse_args(argv)` |
| main | set (scripts/ci_qualification_gates.py:main) | 473 | `set(args.gate)` |
| main | os.environ.get | 478 | `os.environ.get(name)` |
| main | evaluate_gate | 484 | `evaluate_gate(gate, run=run_pytest, live_opt_in=args.live, missing_env=...)` |
| evaluate_gate | GateResult | 400 | `GateResult(name=gate.name, kind=gate.kind, status='pass')` |
| evaluate_gate | result.errors.append | 404 | `result.errors.append(...)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| environment_read | `os.environ.get` | `main` | 478 |
| mutation | `results.append` | `main` | 490 |
| output | `print` | `main` | 494 |
| output | `print` | `main` | 496 |
| filesystem_read | `PIN_FILE.read_text` | `main` | 501 |
| mutation | `errors.extend` | `main` | 503 |
| mutation | `errors.append` | `main` | 505 |
| mutation | `errors.extend` | `main` | 511 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `main` | `argparse.ArgumentParser` | 464 |
| unresolved_call | `main` | `parser.add_argument` | 465 |
| unresolved_call | `main` | `parser.add_argument` | 466 |
| unresolved_call | `main` | `parser.add_argument` | 467 |
| unresolved_call | `main` | `parser.add_argument` | 468 |
| unresolved_call | `main` | `parser.parse_args` | 469 |
| unresolved_call | `evaluate_gate` | `result.errors.append` | 404 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
