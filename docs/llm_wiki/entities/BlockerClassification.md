# BlockerClassification

**Location:** `src/core/skill_manifest.py:827`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [skill_manifest](../modules/skill_manifest.md)

## Description

Actionable-blocker + per-phase evidence-key sets (G3). Reproduces
``_AGENT_ACTIONABLE_BLOCKERS`` and ``_PHASE_SPECIFIC_AGENT_KEYS`` (today at
``orchestrator.py``) as pure declarative data.

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `actionable_blockers` | `list[str]` | `actionable_blockers` | No | No | factory: `list` | — | — | — |
| `phase_evidence_keys` | `dict[str, list[str]]` | `phase_evidence_keys` | No | No | factory: `dict` | — | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["BlockerClassification (src/core/skill_manifest.py)"]
    n1["BaseModel"]
    n0 --> n1
    click n0 "../modules/skill_manifest.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_manifest](../modules/skill_manifest.md) | 0 | `actionable_blockers`, `phase_evidence_keys` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |
