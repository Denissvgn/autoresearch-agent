# UnsupportedPhaseAdvancementError

**Location:** `src/core/skill_runtime.py:156`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [skill_runtime](../modules/skill_runtime.md)

## Description

Raised when a plugin phase-advancement declaration is unsupported.

A ``mode=plugin`` declaration requires a declared ``phase_advancement``
plugin entry (the qualified resolver implementation executes it under
the governed capability rules). Declarations without one, and other
unsupported forms, are rejected explicitly — declarative behavior is
never silently substituted.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["UnsupportedPhaseAdvancementError (src/core/skill_runtime.py)"]
    n1["ValueError"]
    n2["src/core/orchestrator.py"]
    n3["ManifestSkillRuntime._validate_plugin_advancement (src/core/skill_runtime.py)"]
    n4["tests/test_domain_semantics_extension.py"]
    n5["tests/test_goal_phase_semantics.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/skill_runtime.md"
    click n2 "../modules/orchestrator.md"
    click n3 "../modules/skill_runtime.md"
    click n4 "../modules/test_domain_semantics_extension.md"
    click n5 "../modules/test_goal_phase_semantics.md"
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
| `orchestrator` | import | [orchestrator](../modules/orchestrator.md) | — |
| `ManifestSkillRuntime._validate_plugin_advancement` | call | [skill_runtime](../modules/skill_runtime.md) | 1 |
| `test_domain_semantics_extension` | import | [test_domain_semantics_extension](../modules/test_domain_semantics_extension.md) | — |
| `test_goal_phase_semantics` | import | [test_goal_phase_semantics](../modules/test_goal_phase_semantics.md) | — |
