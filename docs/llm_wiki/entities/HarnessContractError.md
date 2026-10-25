# HarnessContractError

**Location:** `src/core/harness_contract.py:74`
**Kind:** Class
**Bases:** `Exception`
**Module:** [harness_contract](../modules/harness_contract.md)

## Description

The harness contract was violated or cannot be honored.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["HarnessContractError (src/core/harness_contract.py)"]
    n1["Exception"]
    n2["DriverProtocolError (src/core/driver_host.py)"]
    n3["HarnessLifecycleError (src/core/harness_contract.py)"]
    n4["HarnessRequirementError (src/core/harness_contract.py)"]
    n5["HarnessVersionError (src/core/harness_contract.py)"]
    n6["UnsupportedCapabilityError (src/core/harness_contract.py)"]
    n7["BuiltinHarnessAdapter.attach (src/core/builtin_harness.py)"]
    n8["BuiltinHarnessAdapter.run_attempt (src/core/builtin_harness.py)"]
    n9["ClaudeCodeHarnessAdapter._launch (src/core/claude_code_harness.py)"]
    n10["ClaudeCodeHarnessAdapter.attach (src/core/claude_code_harness.py)"]
    n11["ClaudeCodeHarnessAdapter.resume (src/core/claude_code_harness.py)"]
    n12["ClaudeCodeHarnessAdapter.start (src/core/claude_code_harness.py)"]
    n13["CodexHarnessAdapter._launch (src/core/codex_harness.py)"]
    n14["CodexHarnessAdapter.attach (src/core/codex_harness.py)"]
    n15["CodexHarnessAdapter.start (src/core/codex_harness.py)"]
    n16["DriverHost.start (src/core/driver_host.py)"]
    n17["HarnessRegistry.register (src/core/harness_adapter.py)"]
    n18["HarnessRegistry.resolve (src/core/harness_adapter.py)"]
    n0 --> n1
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
    n13 --> n0
    n14 --> n0
    n15 --> n0
    n16 --> n0
    n17 --> n0
    n18 --> n0
    click n0 "../modules/harness_contract.md"
    click n2 "../modules/driver_host.md"
    click n3 "../modules/harness_contract.md"
    click n4 "../modules/harness_contract.md"
    click n5 "../modules/harness_contract.md"
    click n6 "../modules/harness_contract.md"
    click n7 "../modules/builtin_harness.md"
    click n8 "../modules/builtin_harness.md"
    click n9 "../modules/claude_code_harness.md"
    click n10 "../modules/claude_code_harness.md"
    click n11 "../modules/claude_code_harness.md"
    click n12 "../modules/claude_code_harness.md"
    click n13 "../modules/codex_harness.md"
    click n14 "../modules/codex_harness.md"
    click n15 "../modules/codex_harness.md"
    click n16 "../modules/driver_host.md"
    click n17 "../modules/harness_adapter.md"
    click n18 "../modules/harness_adapter.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [harness_contract](../modules/harness_contract.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Exception` | — |
| Subclass | `DriverProtocolError` | [driver_host](../modules/driver_host.md) |
| Subclass | `HarnessLifecycleError` | [harness_contract](../modules/harness_contract.md) |
| Subclass | `HarnessRequirementError` | [harness_contract](../modules/harness_contract.md) |
| Subclass | `HarnessVersionError` | [harness_contract](../modules/harness_contract.md) |
| Subclass | `UnsupportedCapabilityError` | [harness_contract](../modules/harness_contract.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `BuiltinHarnessAdapter.attach` | call | [builtin_harness](../modules/builtin_harness.md) | 1 |
| `BuiltinHarnessAdapter.run_attempt` | call | [builtin_harness](../modules/builtin_harness.md) | 1 |
| `ClaudeCodeHarnessAdapter._launch` | call | [claude_code_harness](../modules/claude_code_harness.md) | 1 |
| `ClaudeCodeHarnessAdapter.attach` | call | [claude_code_harness](../modules/claude_code_harness.md) | 1 |
| `ClaudeCodeHarnessAdapter.resume` | call | [claude_code_harness](../modules/claude_code_harness.md) | 1 |
| `ClaudeCodeHarnessAdapter.start` | call | [claude_code_harness](../modules/claude_code_harness.md) | 1 |
| `CodexHarnessAdapter._launch` | call | [codex_harness](../modules/codex_harness.md) | 1 |
| `CodexHarnessAdapter.attach` | call | [codex_harness](../modules/codex_harness.md) | 1 |
| `CodexHarnessAdapter.start` | call | [codex_harness](../modules/codex_harness.md) | 1 |
| `DriverHost.start` | call | [driver_host](../modules/driver_host.md) | 1 |
| `HarnessRegistry.register` | call | [harness_adapter](../modules/harness_adapter.md) | 3 |
| `HarnessRegistry.resolve` | call | [harness_adapter](../modules/harness_adapter.md) | 1 |

> References: showing 12 of 19 logical references; 7 omitted by the 12-row generated summary limit.
