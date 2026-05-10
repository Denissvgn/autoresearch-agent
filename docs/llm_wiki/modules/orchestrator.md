# orchestrator Module

**Path:** `src/core/orchestrator.py`

## Description

Agent orchestrator — drives Claude via the Anthropic SDK with tool use.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `anthropic` | `anthropic` |
| `asyncio` | `asyncio` |
| `dataclasses` | `dataclass`, `field` |
| `datetime` | `datetime`, `timezone` |
| `glob` | `glob_mod` |
| `httpx` | `httpx` |
| `json` | `json` |
| `logging` | `logging` |
| `os` | `os` |
| `pathlib` | `Path` |
| `shlex` | `shlex` |
| `src.config` | `secret_value`, `settings` |
| `src.core.command_runner` | `GovernedCommandRunner`, `redact_sensitive_text` |
| `src.core.consistency_validator` | `build_consistency_report`, `consistency_report_json` |
| `src.core.experiment_parser` | `is_hpo_study_output`, `parse_hpo_study_output`, `parse_iteration_marker`, `parse_prepare_output` |
| `src.core.iteration_context` | `ITERATION_CONTEXT_DIGEST_MARKER`, `build_iteration_context_digest` |
| `src.core.iteration_snapshot` | `build_iteration_attempt_snapshot`, `build_trial_identity`, `canonical_config_hash`, `trial_identity_hash`, `write_iteration_attempt_snapshot` |
| `src.core.log_writer` | `AgentLogWriter` |
| `src.core.research_phase_plan` | `build_phase_state`, `phase_state_json` |
| `src.core.results_store` | `ResultsStore` |
| `src.core.structured_hpo` | `materialize_planned_trials` |
| `src.ws.events` | `broadcaster` |
| `subprocess` | `subprocess` |
| `time` | `time` |
| `typing` | `Any`, `AsyncGenerator`, `Dict`, `List`, `Optional` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ResearchConfig](../entities/ResearchConfig.md) | 69 | — | — |
| [ToolExecutionResult](../entities/ToolExecutionResult.md) | 96 | — | — |
| [AgentOrchestrator](../entities/AgentOrchestrator.md) | 414 | — | Runs a Claude agent session for autonomous ML experiment tuning. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_safe_path` | `(raw: str, workspace: str) -> str` | — | Resolve a path and ensure it stays within the workspace. |
| `_safe_write_path` | `(raw: str, workspace: str) -> str` | — | Resolve a writable path and ensure existing parents stay in workspace. |
| `_normalize_command_for_plan` | `(command: str) -> str` | — | — |
| `_is_setup_command` | `(command: str) -> bool` | — | — |
| `_config_snapshot_path_from_command` | `(command: str, workspace_root: str, session_workspace: str) -> Optional[str]` | — | — |
| `_execute_tool` | `(name: str, input_data: Dict[str, Any], workspace: str, session_workspace: str | None = None) -> ToolExecutionResult` | — | Execute a tool call and return the text result. |
| `_tool_bash` | `(input_data: Dict[str, Any], workspace: str, session_workspace: str | None = None) -> ToolExecutionResult` | — | — |
| `_tool_read_file` | `(input_data: Dict[str, Any], workspace: str) -> str` | — | — |
| `_tool_write_file` | `(input_data: Dict[str, Any], workspace: str) -> str` | — | — |
| `_tool_glob` | `(input_data: Dict[str, Any], workspace: str) -> str` | — | — |
| `_tool_grep` | `(input_data: Dict[str, Any], workspace: str) -> str` | — | — |
