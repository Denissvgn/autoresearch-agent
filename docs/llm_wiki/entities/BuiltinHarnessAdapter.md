# BuiltinHarnessAdapter

**Location:** `src/core/builtin_harness.py:38`
**Kind:** Class
**Bases:** —
**Module:** [builtin_harness](../modules/builtin_harness.md)

## Description

The built-in loop behind the harness contract and kernel driver.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(*, orchestrator: Any = None, attempt_fn: Optional[AttemptFn] = None, name: str = BUILTIN_HARNESS_NAME, version: str = '1.0.0') -> None` | — | — |
| `preflight` | `() -> dict[str, Any]` | — | Diagnostics for capability/preflight surfaces (no authority). |
| `identity` | `() -> HarnessIdentity` | — | — |
| `capabilities` | `() -> frozenset[str]` | — | — |
| `start` | `(request: Mapping[str, Any]) -> Mapping[str, Any]` | — | — |
| `attach` | `(request: Mapping[str, Any]) -> Mapping[str, Any]` | — | — |
| `events` | `(handle: str) -> Iterator[Mapping[str, Any]]` | — | — |
| `cancel` | `(handle: str) -> None` | — | — |
| `pause` | `(handle: str) -> None` | — | — |
| `resume` | `(handle: str) -> None` | — | — |
| `close` | `(handle: str) -> None` | — | — |
| `run_attempt` | `(plan: AttemptPlan, *, attempt_index: int, context: Mapping[str, Any]) -> AttemptResult` | — | Execute one attempt through the built-in loop and report back. |
| `route_proposal` | `(proposal: HarnessProposal, *, metric: Optional[float] = None, best_metric: Optional[float] = None, direction: str = 'maximize') -> ObjectiveDecision` | — | Route a harness proposal through the kernel's decisions. |
| `_new_handle` | `(research_id: str, request: Mapping[str, Any]) -> str` | — | — |
| `_require_open` | `(handle: str, op: str) -> dict[str, Any]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["BuiltinHarnessAdapter (src/core/builtin_harness.py)"]
    n1["build_default_registry (src/api/harnesses.py)"]
    n2["test_adapter_behavior_is_provider_parity (tests/test_builtin_harness.py)"]
    n3["test_attach_holds_the_honest_mode (tests/test_builtin_harness.py)"]
    n4["test_builtin_adapter_completes_the_kernel_lifecycle (tests/test_builtin_harness.py)"]
    n5["test_builtin_adapter_conforms_to_the_harness_contract (tests/test_builtin_harness.py)"]
    n6["test_builtin_adapter_is_selected_explicitly_from_the_registry (tests/test_builtin_harness.py)"]
    n7["test_builtin_proposals_route_through_the_kernel (tests/test_builtin_harness.py)"]
    n8["test_core_reads_whatever_instruction_file_the_adapter_names (tests/test_builtin_harness.py)"]
    n9["test_shared_contract_across_managed_and_attached_surfaces (tests/test_harness_contracts_g4.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    click n0 "../modules/builtin_harness.md"
    click n1 "../modules/harnesses.md"
    click n2 "../modules/test_builtin_harness.md"
    click n3 "../modules/test_builtin_harness.md"
    click n4 "../modules/test_builtin_harness.md"
    click n5 "../modules/test_builtin_harness.md"
    click n6 "../modules/test_builtin_harness.md"
    click n7 "../modules/test_builtin_harness.md"
    click n8 "../modules/test_builtin_harness.md"
    click n9 "../modules/test_harness_contracts_g4.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [builtin_harness](../modules/builtin_harness.md) | 15 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `build_default_registry` | call | [harnesses](../modules/harnesses.md) | 1 |
| `test_adapter_behavior_is_provider_parity` | call | [test_builtin_harness](../modules/test_builtin_harness.md) | 2 |
| `test_attach_holds_the_honest_mode` | call | [test_builtin_harness](../modules/test_builtin_harness.md) | 1 |
| `test_builtin_adapter_completes_the_kernel_lifecycle` | call | [test_builtin_harness](../modules/test_builtin_harness.md) | 1 |
| `test_builtin_adapter_conforms_to_the_harness_contract` | call | [test_builtin_harness](../modules/test_builtin_harness.md) | 1 |
| `test_builtin_adapter_is_selected_explicitly_from_the_registry` | call | [test_builtin_harness](../modules/test_builtin_harness.md) | 1 |
| `test_builtin_proposals_route_through_the_kernel` | call | [test_builtin_harness](../modules/test_builtin_harness.md) | 1 |
| `test_core_reads_whatever_instruction_file_the_adapter_names` | call | [test_builtin_harness](../modules/test_builtin_harness.md) | 1 |
| `test_shared_contract_across_managed_and_attached_surfaces` | call | [test_harness_contracts_g4](../modules/test_harness_contracts_g4.md) | 1 |
