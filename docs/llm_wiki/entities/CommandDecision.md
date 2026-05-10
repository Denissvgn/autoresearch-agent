# CommandDecision

**Location:** `src/core/command_policy.py:65`
**Bases:** —
**Module:** [command_policy](../modules/command_policy.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

_Auto-generated from `CommandDecision` in `src/core/command_policy.py`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `allowed` | `bool` | *required* | — |
| `argv` | `list[str]` | `field(...)` | — |
| `normalized_command` | `str` | `''` | — |
| `operation` | `str` | `''` | — |
| `reason` | `str | None` | `None` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

- **imported_by**: [command_runner](../modules/command_runner.md)
