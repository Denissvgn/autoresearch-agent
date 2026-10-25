# AttemptResult

**Location:** `src/core/research_kernel.py:76`
**Kind:** Class
**Bases:** —
**Module:** [research_kernel](../modules/research_kernel.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

What a driver reports back for one attempt — stable and harness-free.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `iteration` | `int` | *required* | — |
| `outcome` | `str` | *required* | — |
| `metric` | `Optional[float]` | `None` | — |
| `metrics` | `Mapping[str, Any]` | `field(default_factory=dict)` | — |
| `verdict` | `str` | `''` | — |
| `gate_passed` | `bool` | `False` | — |
| `duplicate_of` | `Optional[int]` | `None` | — |
| `phase_id` | `Optional[str]` | `None` | — |
| `phase_advanced` | `Optional[bool]` | `None` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["AttemptResult (src/core/research_kernel.py)"]
    n1["BuiltinHarnessAdapter.run_attempt (src/core/builtin_harness.py)"]
    n2["KernelDriver.run_attempt (src/core/research_kernel.py)"]
    n3["tests/test_claude_code_harness.py"]
    n4["tests/test_codex_harness.py"]
    n5["DeterministicDriver.run_attempt (tests/test_research_kernel.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/research_kernel.md"
    click n1 "../modules/builtin_harness.md"
    click n2 "../modules/research_kernel.md"
    click n3 "../modules/test_claude_code_harness.md"
    click n4 "../modules/test_codex_harness.md"
    click n5 "../modules/test_research_kernel.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [research_kernel](../modules/research_kernel.md) | 0 | `duplicate_of`, `gate_passed`, `iteration`, `metric`, `metrics`, `outcome`, `phase_advanced`, `phase_id`, `verdict` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `BuiltinHarnessAdapter.run_attempt` | call | [builtin_harness](../modules/builtin_harness.md) | 1 |
| `BuiltinHarnessAdapter.run_attempt` | type_reference | [builtin_harness](../modules/builtin_harness.md) | — |
| `KernelDriver.run_attempt` | type_reference | [research_kernel](../modules/research_kernel.md) | — |
| `test_claude_code_harness` | import | [test_claude_code_harness](../modules/test_claude_code_harness.md) | — |
| `test_codex_harness` | import | [test_codex_harness](../modules/test_codex_harness.md) | — |
| `DeterministicDriver.run_attempt` | call | [test_research_kernel](../modules/test_research_kernel.md) | 1 |
