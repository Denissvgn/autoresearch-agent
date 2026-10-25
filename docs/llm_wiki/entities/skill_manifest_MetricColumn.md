# MetricColumn

**Location:** `src/core/skill_manifest.py:282`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [skill_manifest](../modules/skill_manifest.md)

## Description

One gate badge, chart series, or iteration-table column.

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'allow'` | model_config |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `field` | `str` | `field` | Yes | No | — | — | — | — |
| `label` | `str` | `label` | Yes | No | — | — | — | — |
| `kind` | `Optional[str]` | `kind` | No | Yes | `None` | — | — | e.g. ``boolean_badge``, ``icon``. |
| `axis` | `Optional[Literal['left', 'right']]` | `axis` | No | Yes | `None` | — | — | — |
| `format` | `Optional[str]` | `format` | No | Yes | `None` | — | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["MetricColumn (src/core/skill_manifest.py)"]
    n1["BaseModel"]
    n0 --> n1
    click n0 "../modules/skill_manifest.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_manifest](../modules/skill_manifest.md) | 0 | `axis`, `field`, `format`, `kind`, `label` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |
