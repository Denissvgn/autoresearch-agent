# CommandRunResult

**Location:** `src/core/command_runner.py:254`
**Kind:** Class
**Bases:** —
**Module:** [command_runner](../modules/command_runner.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

_Auto-generated from `CommandRunResult` in `src/core/command_runner.py`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `output` | `str` | *required* | — |
| `decision` | `CommandDecision` | *required* | — |
| `returncode` | `int \| None` | `None` | — |
| `timed_out` | `bool` | `False` | — |
| `log_path` | `str \| None` | `None` | — |
| `log_truncated` | `bool` | `False` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `rejected` | `() -> bool` | `@property` | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["CommandRunResult (src/core/command_runner.py)"]
    n1["GovernedCommandRunner.run (src/core/command_runner.py)"]
    n2["_CapturingRunner.run (tests/test_orchestrator_timeout.py)"]
    n3["_CapturingRunner.run (tests/test_trial_workspace.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    click n0 "../modules/command_runner.md"
    click n1 "../modules/command_runner.md"
    click n2 "../modules/test_orchestrator_timeout.md"
    click n3 "../modules/test_trial_workspace.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [command_runner](../modules/command_runner.md) | 1 | `decision`, `log_path`, `log_truncated`, `output`, `returncode`, `timed_out` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `GovernedCommandRunner.run` | call | [command_runner](../modules/command_runner.md) | 3 |
| `GovernedCommandRunner.run` | type_reference | [command_runner](../modules/command_runner.md) | — |
| `_CapturingRunner.run` | call | [test_orchestrator_timeout](../modules/test_orchestrator_timeout.md) | 1 |
| `_CapturingRunner.run` | type_reference | [test_orchestrator_timeout](../modules/test_orchestrator_timeout.md) | — |
| `_CapturingRunner.run` | call | [test_trial_workspace](../modules/test_trial_workspace.md) | 1 |
