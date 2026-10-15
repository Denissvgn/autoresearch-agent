# tool_access Module

**Path:** `src/core/tool_access.py`

## Description

Shared file-tool authorization: one context for every file operation.

Every path a tool call exposes — read, write, glob, grep, copy, and any
path-bearing tool argument — resolves through the same authorization
context. The context is derived server-side from run/attempt ownership
(the run's session workspace) plus skill declarations; tool-supplied paths,
candidate files, and workspace instructions never grant additional access.

Authorization model:

* ``readable_roots`` / ``writable_roots`` are explicit roots. A resolved
  path outside every root of the requested kind is rejected — sibling
  sessions, evaluator packages, interpreter environments, control-plane
  storage, and shared evaluation assets are excluded by construction
  because they live outside the owning session's workspace.
* ``protected_paths`` / ``protected_names`` carve server-owned state out of
  the writable roots: private evidence, command logs, trial staging, the
  bootstrap and session manifests, and skill-declared evaluation data are
  never candidate-writable even though they live inside the workspace.
* Relative tool paths resolve against the session workspace; the legacy
  shared-root path style is still accepted when it lands inside the
  authorized roots. Absolute paths are accepted only when they land inside
  an authorized root.

The shared workspace root is carried for command-policy plumbing (the
governed interpreter and legacy ``cd`` normalization live there); it is
never an authorization root for file access.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `dataclasses` | `dataclass`, `field` |
| `fnmatch` | `fnmatch` |
| `os` | `os` |
| `pathlib` | `Path` |
| `stat` | `stat` |
| `typing` | `Iterable`, `Optional`, `Sequence` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/agent_tools.py"]
    n1["src/core/command_policy.py"]
    n2["src/core/command_runner.py"]
    n3["src/core/tool_access.py"]
    n4["tests/test_async_tool_path.py"]
    n5["tests/test_command_policy.py"]
    n6["tests/test_fs_safety.py"]
    n7["tests/test_orchestrator_timeout.py"]
    n8["tests/test_tool_access.py"]
    n9["tests/test_trial_workspace.py"]
    n0 --> n2
    n0 --> n3
    n1 --> n3
    n2 --> n1
    n2 --> n3
    n4 --> n0
    n4 --> n2
    n4 --> n3
    n5 --> n1
    n5 --> n2
    n5 --> n3
    n6 --> n3
    n7 --> n2
    n7 --> n3
    n8 --> n0
    n8 --> n1
    n8 --> n3
    n9 --> n0
    n9 --> n2
    n9 --> n3
    click n0 "../modules/agent_tools.md"
    click n1 "../modules/command_policy.md"
    click n2 "../modules/command_runner.md"
    click n3 "../modules/tool_access.md"
    click n4 "../modules/test_async_tool_path.md"
    click n5 "../modules/test_command_policy.md"
    click n6 "../modules/test_fs_safety.md"
    click n7 "../modules/test_orchestrator_timeout.md"
    click n8 "../modules/test_tool_access.md"
    click n9 "../modules/test_trial_workspace.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [agent_tools](../modules/agent_tools.md) |
| Inbound | [command_policy](../modules/command_policy.md) |
| Inbound | [command_runner](../modules/command_runner.md) |
| Inbound | [test_async_tool_path](../modules/test_async_tool_path.md) |
| Inbound | [test_command_policy](../modules/test_command_policy.md) |
| Inbound | [test_fs_safety](../modules/test_fs_safety.md) |
| Inbound | [test_orchestrator_timeout](../modules/test_orchestrator_timeout.md) |
| Inbound | [test_tool_access](../modules/test_tool_access.md) |
| Inbound | [test_trial_workspace](../modules/test_trial_workspace.md) |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ToolAccessContext](../entities/ToolAccessContext.md) | 107 | — | Server-derived file authorization for one run/attempt's tool calls. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_resolved` | `(path: str \| os.PathLike[str]) -> str` | — | — |
| `path_within_roots` | `(path: str, roots: Sequence[str], *, follow_leaf: bool = True) -> bool` | — | Whether ``path`` resolves inside one of ``roots``. |
| `matches_protected_name` | `(relative: str, patterns: Sequence[str]) -> bool` | — | Whether a workspace-relative path matches a protected name/pattern. |
| `_multi_link_reason` | `(path: str) -> Optional[str]` | — | Reason a leaf is an ambiguous shared-file alias, or ``None``. |
| `build_tool_access_context` | `(session_workspace: str, *, workspace_root: Optional[str] = None, extra_protected_names: Optional[Iterable[str]] = None) -> ToolAccessContext` | — | Derive the file authorization for one run/attempt, server-side. |
