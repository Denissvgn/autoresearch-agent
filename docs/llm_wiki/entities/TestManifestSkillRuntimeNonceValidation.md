# TestManifestSkillRuntimeNonceValidation

**Location:** `tests/test_skill_prompt_engineering_e2e.py:166`
**Kind:** Class
**Bases:** —
**Module:** [test_skill_prompt_engineering_e2e](../modules/test_skill_prompt_engineering_e2e.md)

## Description

P4-003: ManifestSkillRuntime threads nonce config from the manifest.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `runtime` | `()` | `@pytest.fixture` | — |
| `test_valid_nonce_accepted` | `(runtime)` | — | — |
| `test_forged_nonce_rejected` | `(runtime)` | — | — |
| `test_missing_nonce_rejected` | `(runtime)` | — | — |
| `test_valid_nonce_accepted_as_bytes` | `(runtime)` | — | P4-003 wiring: the orchestrator passes ``session_nonce`` as ``bytes`` |
| `test_forged_marker_rejected_as_bytes` | `(runtime)` | — | P4-003 wiring: a forged nonce (bytes session nonce, wrong echoed |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_skill_prompt_engineering_e2e](../modules/test_skill_prompt_engineering_e2e.md) | 6 | — |
