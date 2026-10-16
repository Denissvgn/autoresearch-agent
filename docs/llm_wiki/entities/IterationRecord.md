# IterationRecord

**Location:** `src/core/skill_runtime.py:90`
**Kind:** Class
**Bases:** `TypedDict`
**Module:** [skill_runtime](../modules/skill_runtime.md)

## Description

Alias over the iteration dict ``StateStore.get_iteration`` returns
(research_id, iteration, primary_metric, metric_name, decision,
config_snapshot, metrics_json, ...).

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["IterationRecord (src/core/skill_runtime.py)"]
    n1["TypedDict"]
    n2["ManifestSkillRuntime.insights_prompt (src/core/skill_runtime.py)"]
    n3["ManifestSkillRuntime.resume_prompt (src/core/skill_runtime.py)"]
    n4["SkillRuntime.insights_prompt (src/core/skill_runtime.py)"]
    n5["SkillRuntime.resume_prompt (src/core/skill_runtime.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/skill_runtime.md"
    click n2 "../modules/skill_runtime.md"
    click n3 "../modules/skill_runtime.md"
    click n4 "../modules/skill_runtime.md"
    click n5 "../modules/skill_runtime.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_runtime](../modules/skill_runtime.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `TypedDict` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `ManifestSkillRuntime.insights_prompt` | type_reference | [skill_runtime](../modules/skill_runtime.md) | — |
| `ManifestSkillRuntime.resume_prompt` | type_reference | [skill_runtime](../modules/skill_runtime.md) | — |
| `SkillRuntime.insights_prompt` | type_reference | [skill_runtime](../modules/skill_runtime.md) | — |
| `SkillRuntime.resume_prompt` | type_reference | [skill_runtime](../modules/skill_runtime.md) | — |
