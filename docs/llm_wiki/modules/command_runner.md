# command_runner Module

**Path:** `src/core/command_runner.py`

## Description

Governed subprocess runner for autoresearch agent commands.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `codecs` | `codecs` |
| `dataclasses` | `dataclass` |
| `fcntl` | `fcntl` |
| `os` | `os` |
| `pathlib` | `Path` |
| `psutil` | `psutil` |
| `re` | `re` |
| `selectors` | `selectors` |
| `signal` | `signal` |
| `src.core.command_policy` | `CommandDecision`, `evaluate_command_policy` |
| `src.core.tool_access` | `ToolAccessContext` |
| `stat` | `stat` |
| `subprocess` | `subprocess` |
| `threading` | `threading` |
| `time` | `time` |
| `types` | `MappingProxyType` |
| `typing` | `Any`, `Callable`, `Literal`, `Mapping` |
| `uuid` | `uuid` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/agent_tools.py"]
    n1["src/core/command_policy.py"]
    n2["src/core/command_runner.py"]
    n3["src/core/orchestrator.py"]
    n4["src/core/plugin_runner.py"]
    n5["src/core/tool_access.py"]
    n6["tests/test_async_tool_path.py"]
    n7["tests/test_command_policy.py"]
    n8["tests/test_execution_request.py"]
    n9["tests/test_orchestrator_timeout.py"]
    n10["tests/test_pinned_evaluators.py"]
    n11["tests/test_trial_workspace.py"]
    n0 --> n2
    n0 --> n5
    n1 --> n5
    n2 --> n1
    n2 --> n5
    n3 --> n0
    n3 --> n2
    n4 --> n2
    n6 --> n0
    n6 --> n2
    n6 --> n3
    n6 --> n5
    n7 --> n1
    n7 --> n2
    n7 --> n3
    n7 --> n5
    n8 --> n0
    n8 --> n1
    n8 --> n2
    n8 --> n5
    n9 --> n2
    n9 --> n3
    n9 --> n5
    n10 --> n0
    n10 --> n1
    n10 --> n2
    n10 --> n3
    n10 --> n5
    n11 --> n0
    n11 --> n2
    n11 --> n5
    click n0 "../modules/agent_tools.md"
    click n1 "../modules/command_policy.md"
    click n2 "../modules/command_runner.md"
    click n3 "../modules/orchestrator.md"
    click n4 "../modules/plugin_runner.md"
    click n5 "../modules/tool_access.md"
    click n6 "../modules/test_async_tool_path.md"
    click n7 "../modules/test_command_policy.md"
    click n8 "../modules/test_execution_request.md"
    click n9 "../modules/test_orchestrator_timeout.md"
    click n10 "../modules/test_pinned_evaluators.md"
    click n11 "../modules/test_trial_workspace.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [agent_tools](../modules/agent_tools.md) |
| Inbound | [orchestrator](../modules/orchestrator.md) |
| Inbound | [plugin_runner](../modules/plugin_runner.md) |
| Inbound | [test_async_tool_path](../modules/test_async_tool_path.md) |
| Inbound | [test_command_policy](../modules/test_command_policy.md) |
| Inbound | [test_execution_request](../modules/test_execution_request.md) |
| Inbound | [test_orchestrator_timeout](../modules/test_orchestrator_timeout.md) |
| Inbound | [test_pinned_evaluators](../modules/test_pinned_evaluators.md) |
| Inbound | [test_trial_workspace](../modules/test_trial_workspace.md) |
| Outbound | [command_policy](../modules/command_policy.md) |
| Outbound | [tool_access](../modules/tool_access.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [_HeadTailBuffer](../entities/HeadTailBuffer.md) | Class | 36 | — | Retain a fixed-size head and rolling tail, including for newline-free data. |
| [_SessionOutputLog](../entities/SessionOutputLog.md) | Class | 70 | — | Append child output under a shared session logs byte quota. |
| [OutputStream](../entities/OutputStream.md) | Type alias | 249 | `Literal['stdout', 'stderr']` | — |
| [OutputCallback](../entities/OutputCallback.md) | Type alias | 250 | `Callable[[OutputStream, str], None]` | — |
| [CommandRunResult](../entities/CommandRunResult.md) | Class | 254 | — | — |
| [CommandProcessRegistry](../entities/CommandProcessRegistry.md) | Class | 267 | — | Thread-safe registry of in-flight governed subprocesses, keyed by session. |
| [GovernedCommandRunner](../entities/GovernedCommandRunner.md) | Class | 323 | — | Validate and execute one approved command without invoking a shell. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_build_child_env` | `(environ: Mapping[str, str] \| None = None) -> dict[str, str]` | — | Build the env dict handed to a governed subprocess (ARC-011 P0-023). |
| `redact_sensitive_text` | `(text: str) -> str` | — | Redact token-like values from command text and subprocess output. |
| `_combine_output` | `(stdout: str \| bytes \| None, stderr: str \| bytes \| None) -> str` | — | — |
| `_to_text` | `(value: str \| bytes) -> str` | — | — |
| `_collect_process_output` | `(proc: subprocess.Popen, *, timeout_s: float, workspace: str, output_callback: OutputCallback \| None = None, log: _SessionOutputLog \| None = None) -> tuple[str, str, bool, str \| None, bool]` | — | Drain both pipes incrementally, without communicate(), threads or queues. |
| `_truncate_output` | `(output: str) -> str` | — | — |
| `_terminate_process_group_without_communicate` | `(proc: subprocess.Popen[str]) -> None` | — | Terminate a timed-out process tree without accumulating pipe output. |
