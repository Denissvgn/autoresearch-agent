# ClaudeCodeHarnessAdapter

**Location:** `src/core/claude_code_harness.py:181`
**Kind:** Class
**Bases:** —
**Module:** [claude_code_harness](../modules/claude_code_harness.md)

## Description

The Claude Code harness behind the common contracts.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(*, name: str = 'claude-code', version: str = '1.0.0') -> None` | — | — |
| `preflight` | `() -> dict[str, Any]` | — | Diagnostics for capability/preflight surfaces (no authority). |
| `identity` | `() -> HarnessIdentity` | — | — |
| `capabilities` | `() -> frozenset[str]` | — | — |
| `resume` | `(handle: str, *, session_id: Optional[str] = None) -> str` | — | Qualified native resume: same harness, same config directory. |
| `start` | `(request: Mapping[str, Any]) -> Mapping[str, Any]` | — | — |
| `attach` | `(request: Mapping[str, Any]) -> Mapping[str, Any]` | — | — |
| `events` | `(handle: str) -> Iterator[Mapping[str, Any]]` | — | — |
| `cancel` | `(handle: str) -> None` | — | — |
| `close` | `(handle: str) -> None` | — | — |
| `session_id` | `(handle: str) -> Optional[str]` | — | — |
| `proposals` | `(handle: str) -> list[dict[str, Any]]` | — | — |
| `usage` | `(handle: str) -> list[dict[str, Any]]` | — | — |
| `attempt_outcome` | `(handle: str) -> str` | — | The run's outcome in the kernel's vocabulary. |
| `_launch` | `(state: dict[str, Any]) -> None` | — | — |
| `_read_stream` | `(process: Any, state: dict[str, Any]) -> None` | — | — |
| `_handle_line` | `(line: bytes, state: dict[str, Any], config: ClaudeRunConfig) -> None` | — | — |
| `_kill_group` | `(process: Any, deadline_s: float) -> None` | — | — |
| `_require_open` | `(handle: str, op: str) -> dict[str, Any]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ClaudeCodeHarnessAdapter (src/core/claude_code_harness.py)"]
    n1["build_default_registry (src/api/harnesses.py)"]
    n2["_run_fixture (tests/test_claude_code_harness.py)"]
    n3["test_attach_is_honest_about_native_resume (tests/test_claude_code_harness.py)"]
    n4["test_capability_profile_is_qualified (tests/test_claude_code_harness.py)"]
    n5["test_interruption_cleans_up_child_processes (tests/test_claude_code_harness.py)"]
    n6["test_live_smoke_is_bounded_and_opt_in (tests/test_claude_code_harness.py)"]
    n7["test_native_resume_requires_a_recorded_session (tests/test_claude_code_harness.py)"]
    n8["test_shared_contract_across_managed_and_attached_surfaces (tests/test_harness_contracts_g4.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    click n0 "../modules/claude_code_harness.md"
    click n1 "../modules/harnesses.md"
    click n2 "../modules/test_claude_code_harness.md"
    click n3 "../modules/test_claude_code_harness.md"
    click n4 "../modules/test_claude_code_harness.md"
    click n5 "../modules/test_claude_code_harness.md"
    click n6 "../modules/test_claude_code_harness.md"
    click n7 "../modules/test_claude_code_harness.md"
    click n8 "../modules/test_harness_contracts_g4.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [claude_code_harness](../modules/claude_code_harness.md) | 19 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `build_default_registry` | call | [harnesses](../modules/harnesses.md) | 1 |
| `_run_fixture` | call | [test_claude_code_harness](../modules/test_claude_code_harness.md) | 1 |
| `test_attach_is_honest_about_native_resume` | call | [test_claude_code_harness](../modules/test_claude_code_harness.md) | 1 |
| `test_capability_profile_is_qualified` | call | [test_claude_code_harness](../modules/test_claude_code_harness.md) | 1 |
| `test_interruption_cleans_up_child_processes` | call | [test_claude_code_harness](../modules/test_claude_code_harness.md) | 1 |
| `test_live_smoke_is_bounded_and_opt_in` | call | [test_claude_code_harness](../modules/test_claude_code_harness.md) | 1 |
| `test_native_resume_requires_a_recorded_session` | call | [test_claude_code_harness](../modules/test_claude_code_harness.md) | 1 |
| `test_shared_contract_across_managed_and_attached_surfaces` | call | [test_harness_contracts_g4](../modules/test_harness_contracts_g4.md) | 1 |
