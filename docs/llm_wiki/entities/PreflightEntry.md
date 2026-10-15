# PreflightEntry

**Location:** `src/core/skill_manifest.py:582`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [skill_manifest](../modules/skill_manifest.md)

## Description

One service-dependency preflight check (ARC-011 §9 ``preflight[]``).
``url`` / ``path`` may carry ``{settings.*}`` / ``{skill_params.*}``
placeholders (G6, resolved by the loader).

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |

## Validators

| Method | Scope | Fields | Mode | Options |
|--------|-------|--------|------|---------|
| `_kind_field_consistency` | model | — | after | — |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `name` | `str` | `name` | Yes | No | — | — | — | — |
| `kind` | `PreflightKind` | `kind` | No | No | `'http_health'` | — | — | — |
| `url` | `Optional[str]` | `url` | No | Yes | `None` | — | — | http_health/tcp endpoint (G6 placeholders ok). |
| `path` | `Optional[str]` | `path` | No | Yes | `None` | — | — | local_file path (G6 placeholders ok). |
| `health_paths` | `list[str]` | `health_paths` | No | No | factory: `lambda: ['/health']` | — | — | — |
| `required` | `bool` | `required` | No | No | `True` | — | — | — |
| `timeout_s` | `float` | `timeout_s` | No | No | `3.0` | ge=0 | — | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `_kind_field_consistency` | `() -> 'PreflightEntry'` | `@model_validator(mode='after')` | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["PreflightEntry (src/core/skill_manifest.py)"]
    n1["BaseModel"]
    n2["PreflightEntry._kind_field_consistency (src/core/skill_manifest.py)"]
    n0 --> n1
    n2 --> n0
    click n0 "../modules/skill_manifest.md"
    click n2 "../modules/skill_manifest.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_manifest](../modules/skill_manifest.md) | 1 | `health_paths`, `kind`, `name`, `path`, `required`, `timeout_s`, `url` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `PreflightEntry._kind_field_consistency` | type_reference | [skill_manifest](../modules/skill_manifest.md) | — |
