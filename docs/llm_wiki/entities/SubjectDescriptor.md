# SubjectDescriptor

**Location:** `src/core/skill_runtime.py:172`
**Kind:** Class
**Bases:** `TypedDict`
**Module:** [skill_runtime](../modules/skill_runtime.md)

## Description

A research subject a skill can enumerate (e.g. an instrument, a model
family). No subject/variant domain exists for the ML skills today — the
transitional runtimes return ``[]`` (greenfield, Phase 2+).

## Attributes

| Name | Type | Presence | Description |
|------|------|----------|-------------|
| `id` | `str` | *optional* | — |
| `label` | `str` | *optional* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SubjectDescriptor (src/core/skill_runtime.py)"]
    n1["TypedDict"]
    n2["ManifestSkillRuntime.list_subjects (src/core/skill_runtime.py)"]
    n3["SkillRuntime.list_subjects (src/core/skill_runtime.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    click n0 "../modules/skill_runtime.md"
    click n2 "../modules/skill_runtime.md"
    click n3 "../modules/skill_runtime.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_runtime](../modules/skill_runtime.md) | 0 | `id`, `label` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `TypedDict` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `ManifestSkillRuntime.list_subjects` | type_reference | [skill_runtime](../modules/skill_runtime.md) | — |
| `SkillRuntime.list_subjects` | type_reference | [skill_runtime](../modules/skill_runtime.md) | — |
