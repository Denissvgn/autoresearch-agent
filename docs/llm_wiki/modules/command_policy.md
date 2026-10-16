# command_policy Module

**Path:** `src/core/command_policy.py`

## Description

Command policy for the autoresearch agent's compatibility bash tool.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `dataclasses` | `dataclass`, `field` |
| `hashlib` | `hashlib` |
| `os` | `os` |
| `pathlib` | `Path` |
| `shlex` | `shlex` |
| `src.core.fs_safety` | `FilesystemSafetyError`, `sha256_regular_file` |
| `src.core.tool_access` | `ToolAccessContext`, `build_tool_access_context` |
| `typing` | `Any`, `Iterable`, `Mapping`, `Optional` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/command_policy.py"]
    n1["src/core/command_runner.py"]
    n2["src/core/fs_safety.py"]
    n3["src/core/tool_access.py"]
    n4["tests/parity/_engine.py"]
    n5["tests/test_command_policy.py"]
    n6["tests/test_manifest_runtime_production_path.py"]
    n7["tests/test_pinned_evaluators.py"]
    n8["tests/test_tool_access.py"]
    n0 --> n2
    n0 --> n3
    n1 --> n0
    n1 --> n3
    n4 --> n0
    n5 --> n0
    n5 --> n1
    n5 --> n3
    n6 --> n0
    n7 --> n0
    n7 --> n1
    n7 --> n3
    n8 --> n0
    n8 --> n3
    click n0 "../modules/command_policy.md"
    click n1 "../modules/command_runner.md"
    click n2 "../modules/fs_safety.md"
    click n3 "../modules/tool_access.md"
    click n4 "../modules/_engine.md"
    click n5 "../modules/test_command_policy.md"
    click n6 "../modules/test_manifest_runtime_production_path.md"
    click n7 "../modules/test_pinned_evaluators.md"
    click n8 "../modules/test_tool_access.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [command_runner](../modules/command_runner.md) |
| Inbound | [_engine](../modules/_engine.md) |
| Inbound | [test_command_policy](../modules/test_command_policy.md) |
| Inbound | [test_manifest_runtime_production_path](../modules/test_manifest_runtime_production_path.md) |
| Inbound | [test_pinned_evaluators](../modules/test_pinned_evaluators.md) |
| Inbound | [test_tool_access](../modules/test_tool_access.md) |
| Outbound | [fs_safety](../modules/fs_safety.md) |
| Outbound | [tool_access](../modules/tool_access.md) |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [CommandDecision](../entities/CommandDecision.md) | 56 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `evaluate_command_policy` | `(command: str, *, workspace_root: str, session_workspace: str \| None = None, policy_extension: Mapping[str, Iterable[str]] \| None = None, access: ToolAccessContext \| None = None) -> CommandDecision` | — | Parse and validate a single agent command before execution. |
| `_reject` | `(reason: str) -> CommandDecision` | — | — |
| `_allow` | `(argv: list[str], *, operation: str, execution_identity: dict[str, Any] \| None = None) -> CommandDecision` | — | — |
| `_strip_legacy_workspace_cd` | `(argv: list[str], workspace_root: str) -> list[str]` | — | — |
| `_shell_syntax_reason` | `(command: str, argv: Iterable[str]) -> str \| None` | — | — |
| `_secret_reference` | `(argv: Iterable[str]) -> str \| None` | — | — |
| `_is_allowed_python` | `(executable: str, workspace_root: str) -> bool` | — | — |
| `_pinned_interpreter` | `(workspace_root: str) -> str \| None` | — | Canonical absolute path of the sanctioned interpreter. |
| `_evaluation_data_digests` | `(names: Iterable[str], session_workspace: str \| None) -> dict[str, str]` | — | Digest the skill-declared evaluation data a launch will consume. |
| `_evaluate_python` | `(argv: list[str], workspace_root: str, session_workspace: str \| None, *, allowed_scripts: set[str] \| None = None, copyable_files: set[str] \| None = None, script_paths: Mapping[str, str] \| None = None, script_digests: Mapping[str, str] \| None = None, write_protected_files: set[str] \| None = None, config_flag: str = '--config', access: ToolAccessContext \| None = None) -> CommandDecision` | — | — |
| `_validate_prepare_config` | `(argv: list[str], script: str, workspace_root: str, session_workspace: str \| None, *, copyable_files: set[str] \| None = None, config_flag: str = '--config', access: ToolAccessContext \| None = None) -> str \| None` | — | Confine a script's config-artifact argument to the session workspace. |
| `_evaluate_cp` | `(argv: list[str], workspace_root: str, session_workspace: str \| None, *, copyable_files: set[str] \| None = None, access: ToolAccessContext \| None = None) -> CommandDecision` | — | — |
| `_evaluate_cat` | `(argv: list[str], workspace_root: str, session_workspace: str \| None, *, readable_files: set[str] \| None = None, access: ToolAccessContext \| None = None) -> CommandDecision` | — | — |
| `_workspace_relative` | `(path: str, workspace_root: str) -> str` | — | — |
| `_resolve_workspace_file` | `(raw: str, *, workspace_root: str, session_workspace: str \| None) -> str` | — | — |
