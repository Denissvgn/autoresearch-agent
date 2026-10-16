# agent_tools Module

**Path:** `src/core/agent_tools.py`

## Description

Agent tool surface — the 5 sandboxed tools + path safety (P1-1 split).

Extracted from ``orchestrator.py``: the ``ToolExecutionResult`` value type,
the ``AGENT_TOOLS`` definitions handed to the LLM provider, the shared
``ToolAccessContext`` path authorization (one context for every file
operation), the five tool implementations (``bash`` / ``read_file`` /
``write_file`` / ``glob`` / ``grep``), the packaged-skill primer loader, and
the W11 nonce-env narrowing helper. ``orchestrator.py`` re-exports all of
these for back-compat; new code should import from here.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `dataclasses` | `dataclass`, `field` |
| `glob` | `glob_mod` |
| `logging` | `logging` |
| `math` | `math` |
| `os` | `os` |
| `pathlib` | `Path` |
| `re` | `re` |
| `shlex` | `shlex` |
| `src.core` | `fs_safety` |
| `src.core.command_runner` | `CommandProcessRegistry`, `GovernedCommandRunner`, `OutputCallback`, `_build_child_env`, `_collect_process_output`, `_SessionOutputLog` |
| `src.core.llm_provider` | `ToolDef` |
| `src.core.skill_registry` | `DEFAULT_SKILLS_ROOT` |
| `src.core.tool_access` | `ToolAccessContext`, `build_tool_access_context`, `path_within_roots` |
| `subprocess` | `subprocess` |
| `time` | `time` |
| `typing` | `Any`, `Dict`, `Mapping`, `Optional` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/agent_tools.py"]
    n1["src/core/command_runner.py"]
    n2["src/core/fs_safety.py"]
    n3["src/core/llm_provider.py"]
    n4["src/core/orchestrator.py"]
    n5["src/core/skill_registry.py"]
    n6["src/core/tool_access.py"]
    n7["tests/test_async_tool_path.py"]
    n8["tests/test_pinned_evaluators.py"]
    n9["tests/test_tool_access.py"]
    n10["tests/test_trial_workspace.py"]
    n0 --> n1
    n0 --> n2
    n0 --> n3
    n0 --> n5
    n0 --> n6
    n1 --> n6
    n4 --> n0
    n4 --> n1
    n4 --> n2
    n4 --> n3
    n7 --> n0
    n7 --> n1
    n7 --> n4
    n7 --> n6
    n8 --> n0
    n8 --> n1
    n8 --> n4
    n8 --> n5
    n8 --> n6
    n9 --> n0
    n9 --> n5
    n9 --> n6
    n10 --> n0
    n10 --> n1
    n10 --> n6
    click n0 "../modules/agent_tools.md"
    click n1 "../modules/command_runner.md"
    click n2 "../modules/fs_safety.md"
    click n3 "../modules/llm_provider.md"
    click n4 "../modules/orchestrator.md"
    click n5 "../modules/skill_registry.md"
    click n6 "../modules/tool_access.md"
    click n7 "../modules/test_async_tool_path.md"
    click n8 "../modules/test_pinned_evaluators.md"
    click n9 "../modules/test_tool_access.md"
    click n10 "../modules/test_trial_workspace.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [orchestrator](../modules/orchestrator.md) |
| Inbound | [test_async_tool_path](../modules/test_async_tool_path.md) |
| Inbound | [test_pinned_evaluators](../modules/test_pinned_evaluators.md) |
| Inbound | [test_tool_access](../modules/test_tool_access.md) |
| Inbound | [test_trial_workspace](../modules/test_trial_workspace.md) |
| Outbound | [command_runner](../modules/command_runner.md) |
| Outbound | [fs_safety](../modules/fs_safety.md) |
| Outbound | [llm_provider](../modules/llm_provider.md) |
| Outbound | [skill_registry](../modules/skill_registry.md) |
| Outbound | [tool_access](../modules/tool_access.md) |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ToolExecutionResult](../entities/ToolExecutionResult.md) | 46 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_normalize_command_for_plan` | `(command: str) -> str` | — | — |
| `_config_snapshot_path_from_command` | `(command: str, workspace_root: str, session_workspace: str, base_dir: str \| None = None, config_flag: str = '--config') -> Optional[str]` | — | Resolve the config artifact a command references. |
| `_execute_tool` | `(name: str, input_data: Dict[str, Any], access: ToolAccessContext, output_callback: OutputCallback \| None = None, *, command_deadline_mono: float \| None = None, proc_registry: CommandProcessRegistry \| None = None, research_id: str \| None = None, extra_env: Mapping[str, str] \| None = None, policy_extension: Mapping[str, Any] \| None = None, cwd: str \| None = None) -> ToolExecutionResult` | — | Execute a tool call and return the text result. |
| `_tool_bash` | `(input_data: Dict[str, Any], access: ToolAccessContext, output_callback: OutputCallback \| None = None, *, command_deadline_mono: float \| None = None, proc_registry: CommandProcessRegistry \| None = None, research_id: str \| None = None, extra_env: Mapping[str, str] \| None = None, policy_extension: Mapping[str, Any] \| None = None, cwd: str \| None = None) -> ToolExecutionResult` | — | — |
| `_tool_read_file` | `(input_data: Dict[str, Any], access: ToolAccessContext) -> str` | — | Read at most 100,001 characters, never materializing a whole large file. |
| `_tool_write_file` | `(input_data: Dict[str, Any], access: ToolAccessContext) -> str` | — | — |
| `_tool_glob` | `(input_data: Dict[str, Any], access: ToolAccessContext) -> str` | — | — |
| `_tool_grep` | `(input_data: Dict[str, Any], access: ToolAccessContext) -> str` | — | Incremental grep capture, excluding its own active log. |
| `_load_packaged_skill_md` | `(skill_id: str, primer: str = 'SKILL.md') -> str` | — | Read the packaged ``skills/<skill_id>/<primer>`` domain primer (C2-2). |
| `_nonce_env_for_command` | `(nonce_env: Optional[Mapping[str, str]], command: object, policy_extension: Optional[Mapping[str, Any]]) -> Optional[Mapping[str, str]]` | — | Narrow the W11 nonce env delivery to the skill's declared scripts (C3). |
