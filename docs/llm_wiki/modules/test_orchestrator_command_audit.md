# test_orchestrator_command_audit Module

**Path:** `tests/test_orchestrator_command_audit.py`

## Description

_Auto-generated from `tests/test_orchestrator_command_audit.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `anthropic` | `anthropic` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.core.orchestrator` | `AgentOrchestrator`, `ResearchConfig` |
| `src.core.results_store` | `ResultsStore` |
| `sys` | `sys` |
| `types` | `types` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [_FakeAsyncAnthropic](../entities/test_orchestrator_command_audit__FakeAsyncAnthropic.md) | 12 | — | — |
| [_FakeAPIStatusError](../entities/test_orchestrator_command_audit__FakeAPIStatusError.md) | 16 | `Exception` | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `test_orchestrator_records_command_policy_rejection_audit` | `*(async)* (tmp_path: Path)` | `@pytest.mark.asyncio` | — |
