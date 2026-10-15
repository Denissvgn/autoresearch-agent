# ToolAccessContext

**Location:** `src/core/tool_access.py:107`
**Kind:** Class
**Bases:** —
**Module:** [tool_access](../modules/tool_access.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

Server-derived file authorization for one run/attempt's tool calls.

Built once per run from the owning session workspace and the skill's
declarations; tool arguments never construct or extend it.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `session_workspace` | `str` | *required* | — |
| `workspace_root` | `str` | *required* | — |
| `readable_roots` | `tuple[str, ...]` | `field(default_factory=tuple)` | — |
| `writable_roots` | `tuple[str, ...]` | `field(default_factory=tuple)` | — |
| `protected_paths` | `tuple[str, ...]` | `field(default_factory=tuple)` | — |
| `protected_names` | `tuple[str, ...]` | `field(default_factory=tuple)` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `resolve_candidates` | `(raw: str, *, write: bool = False) -> list[str]` | — | Resolve a tool-supplied path to its authorized candidates. |
| `resolve` | `(raw: str) -> str` | — | Resolve ``raw`` to the authorized target path. |
| `_select` | `(raw: str, *, write: bool) -> tuple[Optional[str], str]` | — | Return ``(denial_reason, resolved)`` for one tool-supplied path. |
| `authorize_read` | `(raw: str) -> str` | — | Resolve ``raw`` and require it to land inside a readable root. |
| `authorize_write` | `(raw: str) -> str` | — | Resolve ``raw`` and require an authorized, unprotected target. |
| `authorize_import` | `(raw: str) -> str` | — | Resolve ``raw`` as a copy-in source with strict leaf rules. |
| `writable_root_and_relative` | `(resolved: str) -> tuple[str, str]` | — | Split an authorized write target into ``(root, relative_path)``. |
| `is_write_protected` | `(resolved: str) -> bool` | — | Whether a resolved path is server-owned/evaluation state. |
| `filter_readable` | `(candidates: Iterable[str]) -> list[str]` | — | Keep only candidates that resolve inside a readable root. |
| `with_extra_protected` | `(names: Optional[Iterable[str]]) -> 'ToolAccessContext'` | — | Return a copy with additional protected names merged in. |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ToolAccessContext (src/core/tool_access.py)"]
    n1["_execute_tool (src/core/agent_tools.py)"]
    n2["_tool_bash (src/core/agent_tools.py)"]
    n3["_tool_glob (src/core/agent_tools.py)"]
    n4["_tool_grep (src/core/agent_tools.py)"]
    n5["_tool_read_file (src/core/agent_tools.py)"]
    n6["_tool_write_file (src/core/agent_tools.py)"]
    n7["_evaluate_cat (src/core/command_policy.py)"]
    n8["_evaluate_cp (src/core/command_policy.py)"]
    n9["_evaluate_python (src/core/command_policy.py)"]
    n10["_validate_prepare_config (src/core/command_policy.py)"]
    n11["evaluate_command_policy (src/core/command_policy.py)"]
    n12["GovernedCommandRunner.__init__ (src/core/command_runner.py)"]
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
    click n0 "../modules/tool_access.md"
    click n1 "../modules/agent_tools.md"
    click n2 "../modules/agent_tools.md"
    click n3 "../modules/agent_tools.md"
    click n4 "../modules/agent_tools.md"
    click n5 "../modules/agent_tools.md"
    click n6 "../modules/agent_tools.md"
    click n7 "../modules/command_policy.md"
    click n8 "../modules/command_policy.md"
    click n9 "../modules/command_policy.md"
    click n10 "../modules/command_policy.md"
    click n11 "../modules/command_policy.md"
    click n12 "../modules/command_runner.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [tool_access](../modules/tool_access.md) | 10 | `protected_names`, `protected_paths`, `readable_roots`, `session_workspace`, `workspace_root`, `writable_roots` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_execute_tool` | type_reference | [agent_tools](../modules/agent_tools.md) | — |
| `_tool_bash` | type_reference | [agent_tools](../modules/agent_tools.md) | — |
| `_tool_glob` | type_reference | [agent_tools](../modules/agent_tools.md) | — |
| `_tool_grep` | type_reference | [agent_tools](../modules/agent_tools.md) | — |
| `_tool_read_file` | type_reference | [agent_tools](../modules/agent_tools.md) | — |
| `_tool_write_file` | type_reference | [agent_tools](../modules/agent_tools.md) | — |
| `_evaluate_cat` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `_evaluate_cp` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `_evaluate_python` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `_validate_prepare_config` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `evaluate_command_policy` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `GovernedCommandRunner.__init__` | type_reference | [command_runner](../modules/command_runner.md) | — |

> References: showing 12 of 18 logical references; 6 omitted by the 12-row generated summary limit.
