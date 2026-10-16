# SessionRecord

**Location:** `src/core/skill_runtime.py:82`
**Kind:** Class
**Bases:** `TypedDict`
**Module:** [skill_runtime](../modules/skill_runtime.md)

## Description

Alias over the session dict ``StateStore.get_session`` returns. Keys
mirror the ``research_sessions`` row (research_id, instrument, timeframe,
model_type, tag, status, ...). ``total=False`` — callers read via .get().

## Attributes

| Name | Type | Presence | Description |
|------|------|----------|-------------|
| `research_id` | `str` | *optional* | — |
| `instrument` | `str` | *optional* | — |
| `timeframe` | `str` | *optional* | — |
| `model_type` | `str` | *optional* | — |
| `tag` | `str` | *optional* | — |
| `status` | `str` | *optional* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SessionRecord (src/core/skill_runtime.py)"]
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
| [skill_runtime](../modules/skill_runtime.md) | 0 | `instrument`, `model_type`, `research_id`, `status`, `tag`, `timeframe` |

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
