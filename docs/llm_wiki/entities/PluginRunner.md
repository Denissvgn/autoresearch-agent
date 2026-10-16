# PluginRunner

**Location:** `src/core/plugin_runner.py:227`
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
| `_isolation_plan` | `(*, skill_dir: Path, caps: PluginCaps, cwd: str, base_argv: list[str], input_json: dict[str, Any]) -> tuple[str, list[str], Optional[str]]` | — | Decide the execution boundary for one plugin run. |
| `_run_sync` | `(body: '_PluginRunBody') -> PluginResult` | — | — |
| `_run_sync_inner` | `(body: '_PluginRunBody') -> PluginResult` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["PluginRunner (src/core/plugin_runner.py)"]
    n1["_preview_bootstrap (src/cli.py)"]
    n2["BootstrapRunner.__init__ (src/core/bootstrap_runner.py)"]
    n3["test_plugin_runner_enforced_mode_sandboxed (tests/test_execution_isolation.py)"]
    n4["test_plugin_runner_host_prereq_failure_fails_closed (tests/test_execution_isolation.py)"]
    n5["test_plugin_runner_refuses_allowlist_request (tests/test_execution_isolation.py)"]
    n6["test_trusted_local_code_mode_labeled_not_sandboxed (tests/test_execution_isolation.py)"]
    n7["TestPluginCannotForgeVerifiedMetric.test_plugin_output_is_untrusted_data (tests/test_plugin_runner.py)"]
    n8["TestPluginFailClosed.test_invalid_json_fails_closed (tests/test_plugin_runner.py)"]
    n9["TestPluginFailClosed.test_missing_plugin_file (tests/test_plugin_runner.py)"]
    n10["TestPluginFailClosed.test_non_object_json_fails_closed (tests/test_plugin_runner.py)"]
    n11["TestPluginFailClosed.test_non_zero_exit_fails_closed (tests/test_plugin_runner.py)"]
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
    click n3 "../modules/test_execution_isolation.md"
    click n4 "../modules/test_execution_isolation.md"
    click n5 "../modules/test_execution_isolation.md"
    click n6 "../modules/test_execution_isolation.md"
    click n7 "../modules/test_plugin_runner.md"
    click n8 "../modules/test_plugin_runner.md"
    click n9 "../modules/test_plugin_runner.md"
    click n10 "../modules/test_plugin_runner.md"
    click n11 "../modules/test_plugin_runner.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [plugin_runner](../modules/plugin_runner.md) | 5 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_preview_bootstrap` | call | [cli](../modules/cli.md) | 1 |
| `BootstrapRunner.__init__` | call | [bootstrap_runner](../modules/bootstrap_runner.md) | 1 |
| `BootstrapRunner.__init__` | type_reference | [bootstrap_runner](../modules/bootstrap_runner.md) | — |
| `test_plugin_runner_enforced_mode_sandboxed` | call | [test_execution_isolation](../modules/test_execution_isolation.md) | 1 |
| `test_plugin_runner_host_prereq_failure_fails_closed` | call | [test_execution_isolation](../modules/test_execution_isolation.md) | 1 |
| `test_plugin_runner_refuses_allowlist_request` | call | [test_execution_isolation](../modules/test_execution_isolation.md) | 1 |
| `test_trusted_local_code_mode_labeled_not_sandboxed` | call | [test_execution_isolation](../modules/test_execution_isolation.md) | 1 |
| `TestPluginCannotForgeVerifiedMetric.test_plugin_output_is_untrusted_data` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginFailClosed.test_invalid_json_fails_closed` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginFailClosed.test_missing_plugin_file` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginFailClosed.test_non_object_json_fails_closed` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |
| `TestPluginFailClosed.test_non_zero_exit_fails_closed` | call | [test_plugin_runner](../modules/test_plugin_runner.md) | 1 |

> References: showing 12 of 18 logical references; 6 omitted by the 12-row generated summary limit.
