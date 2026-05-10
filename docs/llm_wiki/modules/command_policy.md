# command_policy Module

**Path:** `src/core/command_policy.py`

## Description

Command policy for the autoresearch agent's compatibility bash tool.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `dataclasses` | `dataclass`, `field` |
| `os` | `os` |
| `pathlib` | `Path` |
| `shlex` | `shlex` |
| `typing` | `Iterable` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [CommandDecision](../entities/CommandDecision.md) | 65 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `evaluate_command_policy` | `(command: str) -> CommandDecision` | — | Parse and validate a single agent command before execution. |
| `_reject` | `(reason: str) -> CommandDecision` | — | — |
| `_allow` | `(argv: list[str]) -> CommandDecision` | — | — |
| `_strip_legacy_workspace_cd` | `(argv: list[str], workspace_root: str) -> list[str]` | — | — |
| `_shell_syntax_reason` | `(command: str, argv: Iterable[str]) -> str | None` | — | — |
| `_secret_reference` | `(argv: Iterable[str]) -> str | None` | — | — |
| `_is_allowed_python` | `(executable: str, workspace_root: str) -> bool` | — | — |
| `_evaluate_python` | `(argv: list[str], workspace_root: str, session_workspace: str | None) -> CommandDecision` | — | — |
| `_validate_prepare_config` | `(argv: list[str], script: str, workspace_root: str, session_workspace: str | None) -> str | None` | — | — |
| `_evaluate_cp` | `(argv: list[str], workspace_root: str, session_workspace: str | None) -> CommandDecision` | — | — |
| `_evaluate_cat` | `(argv: list[str], workspace_root: str, session_workspace: str | None) -> CommandDecision` | — | — |
| `_workspace_relative` | `(path: str, workspace_root: str) -> str` | — | — |
| `_resolve_workspace_file` | `(raw: str) -> str` | — | — |
| `_is_within` | `(path: str, directory: str) -> bool` | — | — |
