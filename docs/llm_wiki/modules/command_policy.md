# command_policy Module

**Path:** `src/core/command_policy.py`

## Description

Command policy for the autoresearch agent's compatibility bash tool.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `dataclasses` | `dataclass`, `field`, `replace` |
| `hashlib` | `hashlib` |
| `os` | `os` |
| `pathlib` | `Path` |
| `shlex` | `shlex` |
| `src.core.execution_request` | `DISALLOWED_EXECUTABLES`, `FORBIDDEN_SUBSTRINGS`, `FORBIDDEN_TOKENS`, `PYTHON_BINDINGS`, `ExecutionRequest`, `resolve_execution_request`, `SECRET_MARKERS` |
| `src.core.fs_safety` | `FilesystemSafetyError`, `sha256_regular_file` |
| `src.core.tool_access` | `ToolAccessContext`, `build_tool_access_context` |
| `typing` | `Any`, `Iterable`, `Mapping`, `Optional` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/command_policy.py"]
    n1["src/core/command_runner.py"]
    n2["src/core/execution_request.py"]
    n3["src/core/fs_safety.py"]
    n4["src/core/tool_access.py"]
    n5["tests/parity/_engine.py"]
    n6["tests/test_command_policy.py"]
    n7["tests/test_execution_request.py"]
    n8["tests/test_manifest_runtime_production_path.py"]
    n9["tests/test_pinned_evaluators.py"]
    n10["tests/test_tool_access.py"]
    n0 --> n2
    n0 --> n3
    n0 --> n4
    n1 --> n0
    n1 --> n4
    n5 --> n0
    n6 --> n0
    n6 --> n1
    n6 --> n4
    n7 --> n0
    n7 --> n1
    n7 --> n2
    n7 --> n4
    n8 --> n0
    n9 --> n0
    n9 --> n1
    n9 --> n4
    n10 --> n0
    n10 --> n4
    click n0 "../modules/command_policy.md"
    click n1 "../modules/command_runner.md"
    click n2 "../modules/execution_request.md"
    click n3 "../modules/fs_safety.md"
    click n4 "../modules/tool_access.md"
    click n5 "../modules/_engine.md"
    click n6 "../modules/test_command_policy.md"
    click n7 "../modules/test_execution_request.md"
    click n8 "../modules/test_manifest_runtime_production_path.md"
    click n9 "../modules/test_pinned_evaluators.md"
    click n10 "../modules/test_tool_access.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [command_runner](../modules/command_runner.md) |
| Inbound | [_engine](../modules/_engine.md) |
| Inbound | [test_command_policy](../modules/test_command_policy.md) |
| Inbound | [test_execution_request](../modules/test_execution_request.md) |
| Inbound | [test_manifest_runtime_production_path](../modules/test_manifest_runtime_production_path.md) |
| Inbound | [test_pinned_evaluators](../modules/test_pinned_evaluators.md) |
| Inbound | [test_tool_access](../modules/test_tool_access.md) |
| Outbound | [execution_request](../modules/execution_request.md) |
| Outbound | [fs_safety](../modules/fs_safety.md) |
| Outbound | [tool_access](../modules/tool_access.md) |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [CommandDecision](../entities/CommandDecision.md) | 45 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `evaluate_command_policy` | `(command: str, *, workspace_root: str, session_workspace: str \| None = None, policy_extension: Mapping[str, Iterable[str]] \| None = None, access: ToolAccessContext \| None = None, workdir: str \| None = None, timeout_s: int \| None = None) -> CommandDecision` | — | Resolve one command into an ExecutionRequest, then authorize it. |
| `_reject` | `(reason: str) -> CommandDecision` | — | — |
| `_allow` | `(argv: list[str], *, operation: str, execution_identity: dict[str, Any] \| None = None, request: ExecutionRequest \| None = None) -> CommandDecision` | — | — |
| `_pinned_interpreter` | `(workspace_root: str) -> str \| None` | — | Canonical absolute path of the sanctioned interpreter. |
| `_evaluation_data_digests` | `(names: Iterable[str], session_workspace: str \| None) -> dict[str, str]` | — | Digest the skill-declared evaluation data a launch will consume. |
| `_authorize_python_request` | `(request: ExecutionRequest, *, ext: Mapping[str, Any], workspace_root: str, session_workspace: str \| None, copyable_files: set[str], access: ToolAccessContext) -> CommandDecision` | — | Authorize a resolved python request and pin its execution identity. |
