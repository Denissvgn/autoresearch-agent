# _CapturingRunner

**Location:** `tests/test_orchestrator_timeout.py:272`
**Kind:** Class
**Bases:** —
**Module:** [test_orchestrator_timeout](../modules/test_orchestrator_timeout.md)

## Description

Stand-in for GovernedCommandRunner that records the resolved timeout_s.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `captures` | `list[dict[str, object]]` | `[]` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(**_: object) -> None` | — | — |
| `run` | `(command: str, *, timeout_s: int, output_callback: object = None, proc_registry: object = None, research_id: object = None, extra_env: object = None, cwd: object = None) -> CommandRunResult` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_orchestrator_timeout](../modules/test_orchestrator_timeout.md) | 2 | `captures` |
