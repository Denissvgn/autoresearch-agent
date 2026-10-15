# CommandDecision

**Location:** `src/core/command_policy.py:52`
**Kind:** Class
**Bases:** —
**Module:** [command_policy](../modules/command_policy.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

_Auto-generated from `CommandDecision` in `src/core/command_policy.py`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `allowed` | `bool` | *required* | — |
| `argv` | `list[str]` | `field(default_factory=list)` | — |
| `normalized_command` | `str` | `''` | — |
| `operation` | `str` | `''` | — |
| `reason` | `str \| None` | `None` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["CommandDecision (src/core/command_policy.py)"]
    n1["_allow (src/core/command_policy.py)"]
    n2["_evaluate_cat (src/core/command_policy.py)"]
    n3["_evaluate_cp (src/core/command_policy.py)"]
    n4["_evaluate_python (src/core/command_policy.py)"]
    n5["_reject (src/core/command_policy.py)"]
    n6["evaluate_command_policy (src/core/command_policy.py)"]
    n7["src/core/command_runner.py"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    click n0 "../modules/command_policy.md"
    click n1 "../modules/command_policy.md"
    click n2 "../modules/command_policy.md"
    click n3 "../modules/command_policy.md"
    click n4 "../modules/command_policy.md"
    click n5 "../modules/command_policy.md"
    click n6 "../modules/command_policy.md"
    click n7 "../modules/command_runner.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [command_policy](../modules/command_policy.md) | 0 | `allowed`, `argv`, `normalized_command`, `operation`, `reason` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_allow` | call | [command_policy](../modules/command_policy.md) | 1 |
| `_allow` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `_evaluate_cat` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `_evaluate_cp` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `_evaluate_python` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `_reject` | call | [command_policy](../modules/command_policy.md) | 1 |
| `_reject` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `evaluate_command_policy` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `command_runner` | import | [command_runner](../modules/command_runner.md) | — |
