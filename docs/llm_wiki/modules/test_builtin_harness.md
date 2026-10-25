# test_builtin_harness Module

**Path:** `tests/test_builtin_harness.py`

## Description

The built-in harness adapter: conformance, kernel routing, instructions,
cleanup, and provider parity.

The rendered prompts here are product assets under test; they do not
control the implementation agent's repository workflow.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `pytest` | `pytest` |
| `src.core` | `orchestrator` |
| `src.core.builtin_harness` | `BUILTIN_WORKSPACE_INSTRUCTION_FILE`, `BuiltinHarnessAdapter` |
| `src.core.harness_adapter` | `HarnessRegistry` |
| `src.core.harness_conformance` | `run_conformance` |
| `src.core.harness_contract` | `ATTACH_MODE_CONTINUATION`, `ATTACH_MODE_NATIVE_RESUME`, `CAPABILITY_PAUSE`, `CAPABILITY_RESUME`, `HarnessContractError` |
| `src.core.instruction_assembly` | `COMMON_RESEARCH_INSTRUCTIONS`, `assemble_instructions`, `harness_tool_instructions`, `render_workspace_instructions` |
| `src.core.llm_provider` | `MockProvider`, `Usage` |
| `src.core.orchestrator` | `AgentOrchestrator`, `AgentOrchestrator` |
| `src.core.research_kernel` | `run_kernel_lifecycle` |
| `src.core.state_store` | `SQLiteStateStore` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/builtin_harness.py"]
    n1["src/core/harness_adapter.py"]
    n2["src/core/harness_conformance.py"]
    n3["src/core/harness_contract.py"]
    n4["src/core/instruction_assembly.py"]
    n5["src/core/llm_provider.py"]
    n6["src/core/orchestrator.py"]
    n7["src/core/research_kernel.py"]
    n8["src/core/state_store.py"]
    n9["tests/test_builtin_harness.py"]
    n0 --> n3
    n0 --> n7
    n1 --> n3
    n2 --> n1
    n2 --> n3
    n6 --> n5
    n6 --> n8
    n9 --> n0
    n9 --> n1
    n9 --> n2
    n9 --> n3
    n9 --> n4
    n9 --> n5
    n9 --> n6
    n9 --> n7
    n9 --> n8
    click n0 "../modules/builtin_harness.md"
    click n1 "../modules/harness_adapter.md"
    click n2 "../modules/harness_conformance.md"
    click n3 "../modules/harness_contract.md"
    click n4 "../modules/instruction_assembly.md"
    click n5 "../modules/llm_provider.md"
    click n6 "../modules/orchestrator.md"
    click n7 "../modules/research_kernel.md"
    click n8 "../modules/state_store.md"
    click n9 "../modules/test_builtin_harness.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [builtin_harness](../modules/builtin_harness.md) |
| Outbound | [harness_adapter](../modules/harness_adapter.md) |
| Outbound | [harness_conformance](../modules/harness_conformance.md) |
| Outbound | [harness_contract](../modules/harness_contract.md) |
| Outbound | [instruction_assembly](../modules/instruction_assembly.md) |
| Outbound | [llm_provider](../modules/llm_provider.md) |
| Outbound | [orchestrator](../modules/orchestrator.md) |
| Outbound | [research_kernel](../modules/research_kernel.md) |
| Outbound | [state_store](../modules/state_store.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [_ClosableProvider](../entities/ClosableProvider.md) | 173 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_scripted_attempt_fn` | `()` | — | — |
| `test_builtin_adapter_conforms_to_the_harness_contract` | `()` | — | — |
| `test_builtin_adapter_is_selected_explicitly_from_the_registry` | `()` | — | — |
| `test_builtin_adapter_completes_the_kernel_lifecycle` | `()` | — | — |
| `test_builtin_proposals_route_through_the_kernel` | `()` | — | — |
| `test_attach_holds_the_honest_mode` | `()` | — | — |
| `test_instruction_snapshot_common_and_harness_are_separate` | `()` | — | — |
| `test_workspace_instruction_file_is_rendered_through_the_adapter` | `()` | — | — |
| `test_core_reads_whatever_instruction_file_the_adapter_names` | `(tmp_path, monkeypatch)` | — | — |
| `test_repeated_session_release_closes_per_session_state` | `(tmp_path)` | — | — |
| `test_adapter_behavior_is_provider_parity` | `()` | — | — |
