# TestBuildProvider

**Location:** `tests/test_llm_provider_openai.py:246`
**Kind:** Class
**Bases:** —
**Module:** [test_llm_provider_openai](../modules/test_llm_provider_openai.md)

## Description

_Auto-generated from `TestBuildProvider` in `tests/test_llm_provider_openai.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `test_unknown_raises` | `()` | — | — |
| `test_openai_construction` | `()` | — | — |
| `test_local_and_openai_compatible_providers_without_anthropic_env` | `(provider_id, expected_name, expected_zero_cost)` | `@pytest.mark.parametrize(('provider_id', 'expected_name', 'expected_zero_cost'), [('ollama', 'ollama', True), ('vllm', 'vllm', True), ('lmstudio', 'lmstudio', True), ('llamacpp', 'llamacpp', True), ('llama.cpp', 'llamacpp', True), ('local', 'local', True), ('openai-compatible', 'openai-compatible', False), ('openai_compatible', 'openai-compatible', False), ('openrouter', 'openrouter', False)])` | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_llm_provider_openai](../modules/test_llm_provider_openai.md) | 3 | — |
