# CommandRunResult

**Location:** `src/core/command_runner.py:29`
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
| `returncode` | `int | None` | `None` | — |
| `timed_out` | `bool` | `False` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `rejected` | `() -> bool` | `@property` | — |

## Relationships

*No cross-module references detected.*
