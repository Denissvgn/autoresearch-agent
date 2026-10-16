# GovernedCommandRunner

**Location:** `src/core/command_runner.py:323`
**Kind:** Class
**Bases:** —
**Module:** [command_runner](../modules/command_runner.md)

## Description

Validate and execute one approved command without invoking a shell.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(*, workspace_root: str, session_workspace: str \| None = None, policy_extension: Mapping[str, Any] \| None = None, access: ToolAccessContext \| None = None) -> None` | — | — |
| `run` | `(command: str, *, timeout_s: int, output_callback: OutputCallback \| None = None, proc_registry: CommandProcessRegistry \| None = None, research_id: str \| None = None, extra_env: Mapping[str, str] \| None = None, cwd: str \| None = None, resolved: CommandDecision \| None = None) -> CommandRunResult` | — | Validate and execute one approved command without invoking a shell. |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["GovernedCommandRunner (src/core/command_runner.py)"]
    n1["_tool_bash (src/core/agent_tools.py)"]
    n2["src/core/orchestrator.py"]
    n3["test_governed_runner_executes_without_shell_and_redacts_output (tests/test_command_policy.py)"]
    n4["test_governed_runner_extra_env_delivers_nonce (tests/test_command_policy.py)"]
    n5["test_governed_runner_streams_redacted_output_chunks (tests/test_command_policy.py)"]
    n6["test_governed_runner_strips_control_plane_secrets_from_child_env (tests/test_command_policy.py)"]
    n7["test_governed_runner_timeout_cleans_process_group (tests/test_command_policy.py)"]
    n8["test_governed_runner_without_extra_env_has_no_nonce (tests/test_command_policy.py)"]
    n9["test_sequential_and_parallel_requests_stay_at_parity (tests/test_execution_request.py)"]
    n10["test_registry_kill_all_reaps_in_flight_subprocess (tests/test_orchestrator_timeout.py)"]
    n11["test_import_and_search_path_shadowing_cannot_change_evaluator_imports (tests/test_pinned_evaluators.py)"]
    n12["test_planted_interpreter_under_candidate_tree_is_never_launched (tests/test_pinned_evaluators.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    n10 --> n0
    n11 --> n0
    n12 --> n0
    click n0 "../modules/command_runner.md"
    click n1 "../modules/agent_tools.md"
    click n2 "../modules/orchestrator.md"
    click n3 "../modules/test_command_policy.md"
    click n4 "../modules/test_command_policy.md"
    click n5 "../modules/test_command_policy.md"
    click n6 "../modules/test_command_policy.md"
    click n7 "../modules/test_command_policy.md"
    click n8 "../modules/test_command_policy.md"
    click n9 "../modules/test_execution_request.md"
    click n10 "../modules/test_orchestrator_timeout.md"
    click n11 "../modules/test_pinned_evaluators.md"
    click n12 "../modules/test_pinned_evaluators.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [command_runner](../modules/command_runner.md) | 2 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_tool_bash` | call | [agent_tools](../modules/agent_tools.md) | 1 |
| `orchestrator` | import | [orchestrator](../modules/orchestrator.md) | — |
| `test_governed_runner_executes_without_shell_and_redacts_output` | call | [test_command_policy](../modules/test_command_policy.md) | 1 |
| `test_governed_runner_extra_env_delivers_nonce` | call | [test_command_policy](../modules/test_command_policy.md) | 1 |
| `test_governed_runner_streams_redacted_output_chunks` | call | [test_command_policy](../modules/test_command_policy.md) | 1 |
| `test_governed_runner_strips_control_plane_secrets_from_child_env` | call | [test_command_policy](../modules/test_command_policy.md) | 1 |
| `test_governed_runner_timeout_cleans_process_group` | call | [test_command_policy](../modules/test_command_policy.md) | 1 |
| `test_governed_runner_without_extra_env_has_no_nonce` | call | [test_command_policy](../modules/test_command_policy.md) | 1 |
| `test_sequential_and_parallel_requests_stay_at_parity` | call | [test_execution_request](../modules/test_execution_request.md) | 1 |
| `test_registry_kill_all_reaps_in_flight_subprocess` | call | [test_orchestrator_timeout](../modules/test_orchestrator_timeout.md) | 1 |
| `test_import_and_search_path_shadowing_cannot_change_evaluator_imports` | call | [test_pinned_evaluators](../modules/test_pinned_evaluators.md) | 1 |
| `test_planted_interpreter_under_candidate_tree_is_never_launched` | call | [test_pinned_evaluators](../modules/test_pinned_evaluators.md) | 1 |
