# SkillConfigError

**Location:** `src/core/skill_runtime.py:65`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [skill_runtime](../modules/skill_runtime.md)

## Description

A skill manifest declares something the runtime cannot honor.

ARC-011 review C2 (2026-08-15): raised when the manifest-driven runtime
hits a declaration with no wired implementation (e.g.
``promotion_target.kind=registry_api`` on the config-promotion path) —
surfacing the deployment error loudly instead of silently downgrading
to a default behavior. ``ValueError`` base matches the
``ManifestValidationError`` convention in ``skill_manifest.py``.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SkillConfigError (src/core/skill_runtime.py)"]
    n1["ValueError"]
    n2["_skill_config_http_error (src/api/research.py)"]
    n3["src/core/orchestrator.py"]
    n4["SessionManager._run_skill_bootstrap (src/core/session_manager.py)"]
    n5["ManifestSkillRuntime.command_policy_extension (src/core/skill_runtime.py)"]
    n6["ManifestSkillRuntime.evaluator_command_params (src/core/skill_runtime.py)"]
    n7["ManifestSkillRuntime.promotion_target (src/core/skill_runtime.py)"]
    n8["materialize_skill_runtime (src/core/skill_runtime.py)"]
    n9["tests/test_canonical_start_wiring.py"]
    n10["tests/test_execution_request.py"]
    n11["_RegistryApiSkill.promotion_target (tests/test_manifest_runtime_production_path.py)"]
    n12["_ScriptedOrchestrator.run (tests/test_session_failure_modes.py)"]
    n13["tests/test_webhook_promotion.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    n10 --> n0
    n11 --> n0
    n12 --> n0
    n13 --> n0
    click n0 "../modules/skill_runtime.md"
    click n2 "../modules/research.md"
    click n3 "../modules/orchestrator.md"
    click n4 "../modules/session_manager.md"
    click n5 "../modules/skill_runtime.md"
    click n6 "../modules/skill_runtime.md"
    click n7 "../modules/skill_runtime.md"
    click n8 "../modules/skill_runtime.md"
    click n9 "../modules/test_canonical_start_wiring.md"
    click n10 "../modules/test_execution_request.md"
    click n11 "../modules/test_manifest_runtime_production_path.md"
    click n12 "../modules/test_session_failure_modes.md"
    click n13 "../modules/test_webhook_promotion.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_runtime](../modules/skill_runtime.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_skill_config_http_error` | type_reference | [research](../modules/research.md) | — |
| `orchestrator` | import | [orchestrator](../modules/orchestrator.md) | — |
| `SessionManager._run_skill_bootstrap` | call | [session_manager](../modules/session_manager.md) | 2 |
| `ManifestSkillRuntime.command_policy_extension` | call | [skill_runtime](../modules/skill_runtime.md) | 3 |
| `ManifestSkillRuntime.evaluator_command_params` | call | [skill_runtime](../modules/skill_runtime.md) | 2 |
| `ManifestSkillRuntime.promotion_target` | call | [skill_runtime](../modules/skill_runtime.md) | 1 |
| `materialize_skill_runtime` | call | [skill_runtime](../modules/skill_runtime.md) | 3 |
| `test_canonical_start_wiring` | import | [test_canonical_start_wiring](../modules/test_canonical_start_wiring.md) | — |
| `test_execution_request` | import | [test_execution_request](../modules/test_execution_request.md) | — |
| `_RegistryApiSkill.promotion_target` | call | [test_manifest_runtime_production_path](../modules/test_manifest_runtime_production_path.md) | 1 |
| `_ScriptedOrchestrator.run` | call | [test_session_failure_modes](../modules/test_session_failure_modes.md) | 1 |
| `test_webhook_promotion` | import | [test_webhook_promotion](../modules/test_webhook_promotion.md) | — |
