# PluginRunner

**Location:** `src/core/plugin_runner.py:189`
**Kind:** Class
**Bases:** —
**Module:** [plugin_runner](../modules/plugin_runner.md)

## Description

Execute one skill plugin in a confined governed subprocess (X-004 §6).

Parameters
----------
skills_root:
    Read-only skills directory (``PluginRunner`` never writes here; D4).

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(*, skills_root: Optional[Path] = None) -> None` | — | — |
| `run` | *(async)* `(*, skill_dir: Path, plugin: str, kind: PluginKind, input_json: dict[str, Any], caps: PluginCaps, workspace: Optional[Path] = None, timeout_s: Optional[float] = None) -> PluginResult` | — | Run one plugin. See module docstring for the contract. |
| `_run_sync` | `(body: '_PluginRunBody') -> PluginResult` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["PluginRunner (src/core/plugin_runner.py)"]
    n1["_preview_bootstrap (src/cli.py)"]
    n2["BootstrapRunner.__init__ (src/core/bootstrap_runner.py)"]
    n3["TestPluginCannotForgeVerifiedMetric.test_plugin_output_is_untrusted_data (tests/test_plugin_runner.py)"]
    n4["TestPluginFailClosed.test_invalid_json_fails_closed (tests/test_plugin_runner.py)"]
    n5["TestPluginFailClosed.test_missing_plugin_file (tests/test_plugin_runner.py)"]
    n6["TestPluginFailClosed.test_non_object_json_fails_closed (tests/test_plugin_runner.py)"]
    n7["TestPluginFailClosed.test_non_zero_exit_fails_closed (tests/test_plugin_runner.py)"]
    n8["TestPluginFailClosed.test_timeout_fails_closed (tests/test_plugin_runner.py)"]
    n9["TestPluginHappyPath.test_json_in_json_out (tests/test_plugin_runner.py)"]
    n10["TestPluginHappyPath.test_result_carries_resolved_caps (tests/test_plugin_runner.py)"]
    n11["TestPluginPathConfinement.test_plugin_path_must_stay_in_skill_dir (tests/test_plugin_runner.py)"]
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
    click n0 "../modules/plugin_runner.md"
    click n1 "../modules/cli.md"
    click n2 "../modules/bootstrap_runner.md"
    click n3 "../modules/test_plugin_runner.md"
    click n4 "../modules/test_plugin_runner.md"
    click n5 "../modules/test_plugin_runner.md"
    click n6 "../modules/test_plugin_runner.md"
    click n7 "../modules/test_plugin_runner.md"
    click n8 "../modules/test_plugin_runner.md"
    click n9 "../modules/test_plugin_runner.md"
    click n10 "../modules/test_plugin_runner.md"
    click n11 "../modules/test_plugin_runner.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [plugin_runner](../modules/plugin_runner.md) | 3 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_preview_bootstrap` | call | [cli](../modules/cli.md) | 1 |
| `BootstrapRunner.__init__` | call | [bootstrap_runner](../modules/bootstrap_runner.md) | 1 |
| `BootstrapRunner.__init__` | type_reference | [bootstrap_runner](../modules/bootstrap_runner.md) | — |
| `TestPluginCannotForgeVerifiedMetric.test_plugin_output_is_untrusted_data` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginFailClosed.test_invalid_json_fails_closed` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginFailClosed.test_missing_plugin_file` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginFailClosed.test_non_object_json_fails_closed` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginFailClosed.test_non_zero_exit_fails_closed` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginFailClosed.test_timeout_fails_closed` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginHappyPath.test_json_in_json_out` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginHappyPath.test_result_carries_resolved_caps` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginPathConfinement.test_plugin_path_must_stay_in_skill_dir` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |

> References: showing 12 of 14 logical references; 2 omitted by the 12-row generated summary limit.
