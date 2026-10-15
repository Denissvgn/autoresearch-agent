# TestPromptEngineeringSkillManifest

**Location:** `tests/test_skill_prompt_engineering_e2e.py:49`
**Kind:** Class
**Bases:** —
**Module:** [test_skill_prompt_engineering_e2e](../modules/test_skill_prompt_engineering_e2e.md)

## Description

P4-012: the skill manifest loads and declares the Phase-4 properties.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `manifest` | `()` | `@pytest.fixture` | — |
| `test_skill_id_and_category` | `(manifest)` | — | — |
| `test_provider_is_openai` | `(manifest)` | — | — |
| `test_require_signed_metrics` | `(manifest)` | — | — |
| `test_promotion_target_is_registry_api` | `(manifest)` | — | — |
| `test_demo_experiment_command_declared_and_renders` | `(manifest)` | — | ARC-012 P7-011: the skill declares the command the demo provider |
| `test_config_flag_declared_for_prompt_artifact` | `(manifest)` | — | ARC-012 P7-011: the per-iteration config artifact rides --prompt — |
| `test_demo_command_closed_placeholder_vocabulary` | `()` | — | A skill declaring an unknown placeholder (or a multi-line command) |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_skill_prompt_engineering_e2e](../modules/test_skill_prompt_engineering_e2e.md) | 8 | — |
