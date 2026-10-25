# UnenforceableResourceCapabilityError

**Location:** `src/core/process_limits.py:58`
**Kind:** Class
**Bases:** `RuntimeError`
**Module:** [process_limits](../modules/process_limits.md)

## Description

A configured resource cap cannot be enforced on this host (fail-closed).

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["UnenforceableResourceCapabilityError (src/core/process_limits.py)"]
    n1["RuntimeError"]
    n2["src/core/command_runner.py"]
    n3["src/core/plugin_runner.py"]
    n4["rlimit_prefix (src/core/process_limits.py)"]
    n5["tests/test_process_limits.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/process_limits.md"
    click n2 "../modules/command_runner.md"
    click n3 "../modules/plugin_runner.md"
    click n4 "../modules/process_limits.md"
    click n5 "../modules/test_process_limits.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [process_limits](../modules/process_limits.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `RuntimeError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `command_runner` | import | [command_runner](../modules/command_runner.md) | — |
| `plugin_runner` | import | [plugin_runner](../modules/plugin_runner.md) | — |
| `rlimit_prefix` | call | [process_limits](../modules/process_limits.md) | 1 |
| `test_process_limits` | import | [test_process_limits](../modules/test_process_limits.md) | — |
