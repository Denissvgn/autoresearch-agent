# command_runner Module

**Path:** `src/core/command_runner.py`

## Description

Governed subprocess runner for autoresearch agent commands.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `dataclasses` | `dataclass` |
| `os` | `os` |
| `psutil` | `psutil` |
| `re` | `re` |
| `signal` | `signal` |
| `src.core.command_policy` | `CommandDecision`, `evaluate_command_policy` |
| `subprocess` | `subprocess` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [CommandRunResult](../entities/CommandRunResult.md) | 29 | — | — |
| [GovernedCommandRunner](../entities/GovernedCommandRunner.md) | 40 | — | Validate and execute one approved command without invoking a shell. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `redact_sensitive_text` | `(text: str) -> str` | — | Redact token-like values from command text and subprocess output. |
| `_combine_output` | `(stdout: str | bytes | None, stderr: str | bytes | None) -> str` | — | — |
| `_to_text` | `(value: str | bytes) -> str` | — | — |
| `_truncate_output` | `(output: str) -> str` | — | — |
| `_terminate_process_group` | `(proc: subprocess.Popen[str]) -> tuple[str | None, str | None]` | — | Terminate a timed-out process and its descendant tree. |
