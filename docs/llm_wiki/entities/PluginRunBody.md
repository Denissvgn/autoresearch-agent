# _PluginRunBody

**Location:** `src/core/plugin_runner.py:357`
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

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["_PluginRunBody (src/core/plugin_runner.py)"]
    n1["PluginRunner._run_sync (src/core/plugin_runner.py)"]
    n2["PluginRunner.run (src/core/plugin_runner.py)"]
    n1 --> n0
    n2 --> n0
    click n0 "../modules/plugin_runner.md"
    click n1 "../modules/plugin_runner.md"
    click n2 "../modules/plugin_runner.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [plugin_runner](../modules/plugin_runner.md) | 0 | `caps`, `cwd`, `input_json`, `kind`, `plugin`, `plugin_path`, `timeout_s` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `PluginRunner._run_sync` | type_reference | [plugin_runner](../modules/plugin_runner.md) | — |
| `PluginRunner.run` | call | [plugin_runner](../modules/plugin_runner.md) | 1 |
