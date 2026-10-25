# LLMConfig

**Location:** `src/core/skill_manifest.py:117`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [skill_manifest](../modules/skill_manifest.md)

## Description

LLM tier routing (ARC-011 §9 ``llm``).

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `provider` | `str` | `provider` | Yes | No | — | — | — | Provider id (e.g. ``anthropic``, ``router``). |
| `primary_model` | `str` | `primary_model` | Yes | No | — | — | — | — |
| `insight_model` | `Optional[str]` | `insight_model` | No | Yes | `None` | — | — | Smaller model used for the insights summarization pass. |
| `max_output_tokens` | `int` | `max_output_tokens` | No | No | `8192` | ge=1 | — | — |
| `system_prompt` | `str` | `system_prompt` | No | No | `'SKILL.md'` | — | — | — |
| `required_native_tool_use` | `bool` | `required_native_tool_use` | No | No | `True` | — | — | — |
| `required_system_prompt` | `bool` | `required_system_prompt` | No | No | `True` | — | — | — |
| `required_max_context_tokens` | `Optional[int]` | `required_max_context_tokens` | No | Yes | `None` | ge=1 | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["LLMConfig (src/core/skill_manifest.py)"]
    n1["BaseModel"]
    n2["test_anthropic_request_honors_roles_and_caps (tests/test_provider_roles.py)"]
    n3["test_effective_config_records_requested_versus_effective_identity (tests/test_provider_roles.py)"]
    n4["test_global_provider_and_model_override_routes_skill_to_local_llm (tests/test_provider_roles.py)"]
    n5["test_insight_calls_honor_the_manifest_role_and_cap (tests/test_provider_roles.py)"]
    n6["test_manifest_roles_apply_on_the_default_provider_path (tests/test_provider_roles.py)"]
    n7["test_nonanthropic_without_primary_model_is_rejected_with_diagnostics (tests/test_provider_roles.py)"]
    n8["test_openai_request_honors_roles_and_caps (tests/test_provider_roles.py)"]
    n9["test_unsupported_combination_fails_before_session_creation (tests/test_provider_roles.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    click n0 "../modules/skill_manifest.md"
    click n2 "../modules/test_provider_roles.md"
    click n3 "../modules/test_provider_roles.md"
    click n4 "../modules/test_provider_roles.md"
    click n5 "../modules/test_provider_roles.md"
    click n6 "../modules/test_provider_roles.md"
    click n7 "../modules/test_provider_roles.md"
    click n8 "../modules/test_provider_roles.md"
    click n9 "../modules/test_provider_roles.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_manifest](../modules/skill_manifest.md) | 0 | `insight_model`, `max_output_tokens`, `primary_model`, `provider`, `required_max_context_tokens`, `required_native_tool_use`, `required_system_prompt`, `system_prompt` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `test_anthropic_request_honors_roles_and_caps` | call | [test_provider_roles](../modules/test_provider_roles.md) | 1 |
| `test_effective_config_records_requested_versus_effective_identity` | call | [test_provider_roles](../modules/test_provider_roles.md) | 2 |
| `test_global_provider_and_model_override_routes_skill_to_local_llm` | call | [test_provider_roles](../modules/test_provider_roles.md) | 1 |
| `test_insight_calls_honor_the_manifest_role_and_cap` | call | [test_provider_roles](../modules/test_provider_roles.md) | 2 |
| `test_manifest_roles_apply_on_the_default_provider_path` | call | [test_provider_roles](../modules/test_provider_roles.md) | 2 |
| `test_nonanthropic_without_primary_model_is_rejected_with_diagnostics` | call | [test_provider_roles](../modules/test_provider_roles.md) | 1 |
| `test_openai_request_honors_roles_and_caps` | call | [test_provider_roles](../modules/test_provider_roles.md) | 1 |
| `test_unsupported_combination_fails_before_session_creation` | call | [test_provider_roles](../modules/test_provider_roles.md) | 1 |
