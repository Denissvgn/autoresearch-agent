# VariantsConfig

**Location:** `src/core/skill_manifest.py:195`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [skill_manifest](../modules/skill_manifest.md)

## Description

Variant enumeration (G12). A variant is a per-subject sweep dimension
(e.g. timeframe / question set).

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |

## Validators

| Method | Scope | Fields | Mode | Options |
|--------|-------|--------|------|---------|
| `_static_or_enumerator` | model | — | after | — |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `static` | `Optional[list[str]]` | `static` | No | Yes | `None` | — | — | — |
| `enumerator` | `Optional[str]` | `enumerator` | No | Yes | `None` | — | — | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `_static_or_enumerator` | `() -> 'VariantsConfig'` | `@model_validator(mode='after')` | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["VariantsConfig (src/core/skill_manifest.py)"]
    n1["BaseModel"]
    n2["VariantsConfig._static_or_enumerator (src/core/skill_manifest.py)"]
    n0 --> n1
    n2 --> n0
    click n0 "../modules/skill_manifest.md"
    click n2 "../modules/skill_manifest.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_manifest](../modules/skill_manifest.md) | 1 | `enumerator`, `static` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `VariantsConfig._static_or_enumerator` | type_reference | [skill_manifest](../modules/skill_manifest.md) | — |
