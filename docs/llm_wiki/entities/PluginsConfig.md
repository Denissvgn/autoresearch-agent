# PluginsConfig

**Location:** `src/core/skill_manifest.py:489`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [skill_manifest](../modules/skill_manifest.md)

## Description

Declared skill plugins + their capability grants (ARC-011 §5.3 / X-004).

Optional in v1: skills with only ``SKILL.yaml``/``SKILL.md`` have no
plugins. The loader (P5-001) cross-checks declared paths against the
package's on-disk files; the registry surfaces the resolved layout via
``SkillLayout`` (P5-001). The ``PluginRunner`` (P5-005) is the sole
consumer at runtime.

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |

## Validators

| Method | Scope | Fields | Mode | Options |
|--------|-------|--------|------|---------|
| `_unique_kinds_and_paths` | model | — | after | — |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `entries` | `list[PluginEntry]` | `entries` | No | No | factory: `list` | — | — | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `_unique_kinds_and_paths` | `() -> 'PluginsConfig'` | `@model_validator(mode='after')` | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["PluginsConfig (src/core/skill_manifest.py)"]
    n1["BaseModel"]
    n2["PluginsConfig._unique_kinds_and_paths (src/core/skill_manifest.py)"]
    n0 --> n1
    n2 --> n0
    click n0 "../modules/skill_manifest.md"
    click n2 "../modules/skill_manifest.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_manifest](../modules/skill_manifest.md) | 1 | `entries` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `PluginsConfig._unique_kinds_and_paths` | type_reference | [skill_manifest](../modules/skill_manifest.md) | — |
