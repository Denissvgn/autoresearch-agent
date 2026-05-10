# test_prompt_promotion_policy Module

**Path:** `tests/test_prompt_promotion_policy.py`

## Description

_Auto-generated from `tests/test_prompt_promotion_policy.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `anthropic` | `anthropic` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.core` | `orchestrator` |
| `src.core.iteration_context` | `ITERATION_CONTEXT_DIGEST_MARKER` |
| `src.core.orchestrator` | `AgentOrchestrator`, `PROMOTION_HANDOFF_INSTRUCTION`, `ResearchConfig` |
| `sys` | `sys` |
| `types` | `types` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [_FakeAsyncAnthropic](../entities/test_prompt_promotion_policy__FakeAsyncAnthropic.md) | 12 | — | — |
| [_FakeAPIStatusError](../entities/test_prompt_promotion_policy__FakeAPIStatusError.md) | 16 | `Exception` | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_config` | `(model_type: str) -> ResearchConfig` | — | — |
| `test_prompt_sources_do_not_instruct_direct_promote_py` | `()` | — | — |
| `test_fresh_orchestrator_prompts_use_server_owned_setup_mode` | `(monkeypatch)` | — | — |
| `test_resume_prompt_keeps_promotion_server_owned` | `*(async)* (monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_fresh_resume_falls_back_to_generated_resume` | `(monkeypatch, tmp_path)` | — | — |
| `test_fresh_resume_fallback_failure_does_not_abort` | `(monkeypatch, tmp_path)` | — | — |
| `test_structured_hpo_guard_rejects_off_plan_prepare_and_yaml_writes` | `*(async)* ()` | `@pytest.mark.asyncio` | — |
| `test_duplicate_training_guard_rejects_same_identity` | `*(async)* ()` | `@pytest.mark.asyncio` | — |
| `test_iteration_context_digest_appended_after_recorded_attempt` | `*(async)* (monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_iteration_context_digest_not_appended_without_recorded_attempt` | `*(async)* (monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_iteration_context_digest_disabled` | `*(async)* (monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_compaction_retains_latest_iteration_context_digest` | `()` | — | — |
