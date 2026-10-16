# _PluginRunBody

**Location:** `src/core/plugin_runner.py:512`
**Kind:** Class
**Bases:** —
**Module:** [plugin_runner](../modules/plugin_runner.md)

**Decorators:** `@dataclass`

## Description

Inputs bundled for the worker-thread sync body.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `plugin_path` | `Path` | *required* | — |
| `kind` | `PluginKind` | *required* | — |
| `plugin` | `str` | *required* | — |
| `input_json` | `dict[str, Any]` | *required* | — |
| `caps` | `PluginCaps` | *required* | — |
| `cwd` | `str` | *required* | — |
| `timeout_s` | `float` | *required* | — |
| `spawn_argv` | `list[str]` | *required* | — |
| `isolation` | `str` | *required* | — |
| `resource_caps` | `ProcessResourceCaps` | *required* | — |
| `proc_registry` | `Any` | `None` | — |
| `research_id` | `Optional[str]` | `None` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["_PluginRunBody (src/core/plugin_runner.py)"]
    n1["_violation_result (src/core/plugin_runner.py)"]
    n2["PluginRunner._run_sync (src/core/plugin_runner.py)"]
    n3["PluginRunner._run_sync_inner (src/core/plugin_runner.py)"]
    n4["PluginRunner.run (src/core/plugin_runner.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/plugin_runner.md"
    click n1 "../modules/plugin_runner.md"
    click n2 "../modules/plugin_runner.md"
    click n3 "../modules/plugin_runner.md"
    click n4 "../modules/plugin_runner.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [plugin_runner](../modules/plugin_runner.md) | 0 | `caps`, `cwd`, `input_json`, `isolation`, `kind`, `plugin`, `plugin_path`, `proc_registry`, `research_id`, `resource_caps`, `spawn_argv`, `timeout_s` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_violation_result` | type_reference | [plugin_runner](../modules/plugin_runner.md) | — |
| `PluginRunner._run_sync` | type_reference | [plugin_runner](../modules/plugin_runner.md) | — |
| `PluginRunner._run_sync_inner` | type_reference | [plugin_runner](../modules/plugin_runner.md) | — |
| `PluginRunner.run` | call | [plugin_runner](../modules/plugin_runner.md) | 1 |
