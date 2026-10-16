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
| `src.core.execution_request` | `resolve_execution_request` |
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
    n0["src"]
    n1["src/core/agent_tools.py"]
    n2["tests"]
    n0 --> n1
    n1 --> n0
    n2 --> n1
    click n1 "../modules/agent_tools.md"
```

> Module-level dependencies exceed the generated-diagram limits, so the diagram and table below group them by top-level package. Counts report the number of module neighbors in each package.

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | `src` (1) |
| Inbound | `tests` (6) |
| Outbound | `src` (6) |

> All 13 module neighbor(s) are summarized by package because the module-level view exceeds the 12-node limit.

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ToolExecutionResult](../entities/ToolExecutionResult.md) | 46 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_normalize_command_for_plan` | `(command: str) -> str` | — | — |
| `_config_snapshot_path_from_command` | `(command: str, workspace_root: str, session_workspace: str, base_dir: str \| None = None, config_flag: str = '--config', policy_extension: Mapping[str, Any] \| None = None, access: Any = None) -> Optional[str]` | — | Resolve the config artifact a command references. |
| `_execute_tool` | `(name: str, input_data: Dict[str, Any], access: ToolAccessContext, output_callback: OutputCallback \| None = None, *, command_deadline_mono: float \| None = None, proc_registry: CommandProcessRegistry \| None = None, research_id: str \| None = None, extra_env: Mapping[str, str] \| None = None, policy_extension: Mapping[str, Any] \| None = None, cwd: str \| None = None, resolved: Any = None) -> ToolExecutionResult` | — | Execute a tool call and return the text result. |
| `compute_bash_timeout` | `(input_data: Dict[str, Any], command_deadline_mono: float \| None) -> int` | — | The final per-command timeout: tool input floored and deadline-capped. |
| `_tool_bash` | `(input_data: Dict[str, Any], access: ToolAccessContext, output_callback: OutputCallback \| None = None, *, command_deadline_mono: float \| None = None, proc_registry: CommandProcessRegistry \| None = None, research_id: str \| None = None, extra_env: Mapping[str, str] \| None = None, policy_extension: Mapping[str, Any] \| None = None, cwd: str \| None = None, resolved: Any = None, isolation_policy: Any \| None = None) -> ToolExecutionResult` | — | — |
| `_tool_read_file` | `(input_data: Dict[str, Any], access: ToolAccessContext) -> str` | — | Read at most 100,001 characters, never materializing a whole large file. |
| `_tool_write_file` | `(input_data: Dict[str, Any], access: ToolAccessContext) -> str` | — | — |
| `_tool_glob` | `(input_data: Dict[str, Any], access: ToolAccessContext) -> str` | — | — |
| `_tool_grep` | `(input_data: Dict[str, Any], access: ToolAccessContext) -> str` | — | Incremental grep capture, excluding its own active log. |
| `_load_packaged_skill_md` | `(skill_id: str, primer: str = 'SKILL.md') -> str` | — | Read the packaged ``skills/<skill_id>/<primer>`` domain primer (C2-2). |
| `_nonce_env_for_command` | `(nonce_env: Optional[Mapping[str, str]], command: object, policy_extension: Optional[Mapping[str, Any]]) -> Optional[Mapping[str, str]]` | — | Narrow the W11 nonce env delivery to the skill's declared scripts (C3). |
