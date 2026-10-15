# StructuredHPOConfig

**Location:** `src/core/skill_manifest.py:842`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [skill_manifest](../modules/skill_manifest.md)

## Description

Optional structured-HPO capability (ARC-011 §9 ``structured_hpo``).

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `enabled` | `bool` | `enabled` | No | No | `False` | — | — | — |
| `plan_generator` | `Optional[str]` | `plan_generator` | No | Yes | `None` | — | — | — |
| `max_trials` | `int` | `max_trials` | No | No | `200` | ge=1 | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["StructuredHPOConfig (src/core/skill_manifest.py)"]
    n1["BaseModel"]
    n0 --> n1
    click n0 "../modules/skill_manifest.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_manifest](../modules/skill_manifest.md) | 0 | `enabled`, `max_trials`, `plan_generator` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |
