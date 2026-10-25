# SkillConfigError

**Location:** `src/core/skill_runtime.py:66`
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
    n4["SessionManager._run_local_file_preflight (src/core/session_manager.py)"]
    n5["SessionManager._run_skill_bootstrap (src/core/session_manager.py)"]
    n6["SessionManager._validate_session_skill (src/core/session_manager.py)"]
    n7["ManifestSkillRuntime.command_policy_extension (src/core/skill_runtime.py)"]
    n8["ManifestSkillRuntime.promotion_target (src/core/skill_runtime.py)"]
    n9["materialize_skill_runtime (src/core/skill_runtime.py)"]
    n10["tests/test_canonical_start_wiring.py"]
    n11["tests/test_execution_request.py"]
    n12["_RegistryApiSkill.promotion_target (tests/test_manifest_runtime_production_path.py)"]
    n13["tests/test_preflight_support_matrix.py"]
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
    click n5 "../modules/session_manager.md"
    click n6 "../modules/session_manager.md"
    click n7 "../modules/skill_runtime.md"
    click n8 "../modules/skill_runtime.md"
    click n9 "../modules/skill_runtime.md"
    click n10 "../modules/test_canonical_start_wiring.md"
    click n11 "../modules/test_execution_request.md"
    click n12 "../modules/test_manifest_runtime_production_path.md"
    click n13 "../modules/test_preflight_support_matrix.md"
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
| `SessionManager._run_local_file_preflight` | call | [session_manager](../modules/session_manager.md) | 1 |
| `SessionManager._run_skill_bootstrap` | call | [session_manager](../modules/session_manager.md) | 2 |
| `SessionManager._validate_session_skill` | call | [session_manager](../modules/session_manager.md) | 1 |
| `ManifestSkillRuntime.command_policy_extension` | call | [skill_runtime](../modules/skill_runtime.md) | 3 |
| `ManifestSkillRuntime.promotion_target` | call | [skill_runtime](../modules/skill_runtime.md) | 1 |
| `materialize_skill_runtime` | call | [skill_runtime](../modules/skill_runtime.md) | 3 |
| `test_canonical_start_wiring` | import | [test_canonical_start_wiring](../modules/test_canonical_start_wiring.md) | — |
| `test_execution_request` | import | [test_execution_request](../modules/test_execution_request.md) | — |
| `_RegistryApiSkill.promotion_target` | call | [test_manifest_runtime_production_path](../modules/test_manifest_runtime_production_path.md) | 1 |
| `test_preflight_support_matrix` | import | [test_preflight_support_matrix](../modules/test_preflight_support_matrix.md) | — |

> References: showing 12 of 14 logical references; 2 omitted by the 12-row generated summary limit.
