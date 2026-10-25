# HarnessLifecycleError

**Location:** `src/core/harness_contract.py:108`
**Kind:** Class
**Bases:** `HarnessContractError`
**Module:** [harness_contract](../modules/harness_contract.md)

## Description

A lifecycle operation was called out of order or after teardown.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["HarnessLifecycleError (src/core/harness_contract.py)"]
    n1["HarnessContractError (src/core/harness_contract.py)"]
    n2["BuiltinHarnessAdapter._require_open (src/core/builtin_harness.py)"]
    n3["BuiltinHarnessAdapter.events (src/core/builtin_harness.py)"]
    n4["ClaudeCodeHarnessAdapter._require_open (src/core/claude_code_harness.py)"]
    n5["ClaudeCodeHarnessAdapter.events (src/core/claude_code_harness.py)"]
    n6["CodexHarnessAdapter._require_open (src/core/codex_harness.py)"]
    n7["CodexHarnessAdapter.events (src/core/codex_harness.py)"]
    n8["FakeHarnessAdapter._require_open (src/core/harness_conformance.py)"]
    n9["FakeHarnessAdapter.events (src/core/harness_conformance.py)"]
    n10["tests/test_claude_code_harness.py"]
    n11["tests/test_codex_harness.py"]
    n12["tests/test_harness_sdk.py"]
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
    click n0 "../modules/harness_contract.md"
    click n1 "../modules/harness_contract.md"
    click n2 "../modules/builtin_harness.md"
    click n3 "../modules/builtin_harness.md"
    click n4 "../modules/claude_code_harness.md"
    click n5 "../modules/claude_code_harness.md"
    click n6 "../modules/codex_harness.md"
    click n7 "../modules/codex_harness.md"
    click n8 "../modules/harness_conformance.md"
    click n9 "../modules/harness_conformance.md"
    click n10 "../modules/test_claude_code_harness.md"
    click n11 "../modules/test_codex_harness.md"
    click n12 "../modules/test_harness_sdk.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [harness_contract](../modules/harness_contract.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `HarnessContractError` | [harness_contract](../modules/harness_contract.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `BuiltinHarnessAdapter._require_open` | call | [builtin_harness](../modules/builtin_harness.md) | 1 |
| `BuiltinHarnessAdapter.events` | call | [builtin_harness](../modules/builtin_harness.md) | 1 |
| `ClaudeCodeHarnessAdapter._require_open` | call | [claude_code_harness](../modules/claude_code_harness.md) | 1 |
| `ClaudeCodeHarnessAdapter.events` | call | [claude_code_harness](../modules/claude_code_harness.md) | 1 |
| `CodexHarnessAdapter._require_open` | call | [codex_harness](../modules/codex_harness.md) | 1 |
| `CodexHarnessAdapter.events` | call | [codex_harness](../modules/codex_harness.md) | 1 |
| `FakeHarnessAdapter._require_open` | call | [harness_conformance](../modules/harness_conformance.md) | 1 |
| `FakeHarnessAdapter.events` | call | [harness_conformance](../modules/harness_conformance.md) | 1 |
| `test_claude_code_harness` | import | [test_claude_code_harness](../modules/test_claude_code_harness.md) | — |
| `test_codex_harness` | import | [test_codex_harness](../modules/test_codex_harness.md) | — |
| `test_harness_sdk` | import | [test_harness_sdk](../modules/test_harness_sdk.md) | — |
