# TestCapabilityMatching

**Location:** `tests/test_llm_provider_openai.py:268`
**Kind:** Class
**Bases:** —
**Module:** [test_llm_provider_openai](../modules/test_llm_provider_openai.md)

## Description

P4-009: ``build_provider(required_capabilities=...)`` validates the
provider's ``capabilities()`` against the skill's requirements and raises
``ProviderCapabilityMismatch`` on mismatch (fail-closed at session start).

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `_settings` | `()` | `@staticmethod` | — |
| `test_satisfied_requirements_accepted` | `()` | — | — |
| `test_missing_native_tool_use_raises` | `()` | — | — |
| `test_missing_system_prompt_raises` | `()` | — | — |
| `test_insufficient_context_raises` | `()` | — | — |
| `test_no_requirements_skips_check` | `()` | — | ``required_capabilities=None`` (the orchestrator init path) must not |
| `test_from_llm_config_reads_required_fields` | `()` | — | P4-009: ``RequiredCapabilities.from_llm_config`` reads the manifest's |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_llm_provider_openai](../modules/test_llm_provider_openai.md) | 7 | — |
