# builtin_harness Module

**Path:** `src/core/builtin_harness.py`

## Description

The built-in provider/tool loop as a harness adapter.

``BuiltinHarnessAdapter`` wraps the corrected built-in loop behind the
harness contract: it is selectable by name through the registry, executes
attempts through the existing tool/output-parser machinery, and routes its
proposals through the research kernel. Its workspace instruction
convention (``CLAUDE.md``) is harness-owned data — core behavior never
depends on the filename or on any provider's tool-block shape.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `src.core.harness_contract` | `ATTACH_MODE_CONTINUATION`, `ATTACH_MODE_NATIVE_RESUME`, `CAPABILITY_PAUSE`, `CAPABILITY_RESUME`, `HARNESS_CONTRACT_VERSION`, `HarnessContractError`, `HarnessIdentity`, `HarnessLifecycleError`, `HarnessProposal` |
| `src.core.research_kernel` | `AttemptPlan`, `AttemptResult`, `ObjectiveDecision`, `decide_objective` |
| `typing` | `Any`, `Callable`, `Iterator`, `Mapping`, `Optional` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/api/harnesses.py"]
    n1["src/core/builtin_harness.py"]
    n2["src/core/harness_contract.py"]
    n3["src/core/research_kernel.py"]
    n4["tests/test_builtin_harness.py"]
    n5["tests/test_harness_contracts_g4.py"]
    n0 --> n1
    n0 --> n2
    n1 --> n2
    n1 --> n3
    n4 --> n1
    n4 --> n2
    n4 --> n3
    n5 --> n1
    n5 --> n3
    click n0 "../modules/harnesses.md"
    click n1 "../modules/builtin_harness.md"
    click n2 "../modules/harness_contract.md"
    click n3 "../modules/research_kernel.md"
    click n4 "../modules/test_builtin_harness.md"
    click n5 "../modules/test_harness_contracts_g4.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [harnesses](../modules/harnesses.md) |
| Inbound | [test_builtin_harness](../modules/test_builtin_harness.md) |
| Inbound | [test_harness_contracts_g4](../modules/test_harness_contracts_g4.md) |
| Outbound | [harness_contract](../modules/harness_contract.md) |
| Outbound | [research_kernel](../modules/research_kernel.md) |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [AttemptFn](../entities/AttemptFn.md) | Type alias | 35 | `Callable[[Mapping[str, Any], int], Mapping[str, Any]]` | — |
| [BuiltinHarnessAdapter](../entities/BuiltinHarnessAdapter.md) | Class | 38 | — | The built-in loop behind the harness contract and kernel driver. |
