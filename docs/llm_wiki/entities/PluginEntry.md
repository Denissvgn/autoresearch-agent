# PluginEntry

**Location:** `src/core/skill_manifest.py:548`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [skill_manifest](../modules/skill_manifest.md)

## Description

One declared skill plugin with its capability grant (X-004 §6).

``path`` is relative to the skill package root (e.g. ``"bootstrap.py"``,
``"parser.py"``). ``caps`` defaults to the X-004 per-kind default applied
by the loader/registry at materialization time; a manifest may override
any cap to *narrow* it (never widen beyond the kind default — defense in
depth for R10 generated skills).

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `kind` | `PluginKind` | `kind` | Yes | No | — | — | — | — |
| `path` | `str` | `path` | Yes | No | — | — | — | Relative path of the plugin within the skill package. |
| `caps` | `Optional[PluginCaps]` | `caps` | No | Yes | `None` | — | — | Capability grant. Omit to take the X-004 per-kind default; the loader applies it. A manifest may narrow but not widen the default. |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["PluginEntry (src/core/skill_manifest.py)"]
    n1["BaseModel"]
    n2["resolve_phase_advancement (src/core/phase_resolver.py)"]
    n3["load_layout (src/core/skill_loader.py)"]
    n4["_entry (tests/test_domain_semantics_extension.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/skill_manifest.md"
    click n2 "../modules/phase_resolver.md"
    click n3 "../modules/skill_loader.md"
    click n4 "../modules/test_domain_semantics_extension.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_manifest](../modules/skill_manifest.md) | 0 | `caps`, `kind`, `path` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `resolve_phase_advancement` | type_reference | [phase_resolver](../modules/phase_resolver.md) | — |
| `load_layout` | call | [skill_loader](../modules/skill_loader.md) | 2 |
| `_entry` | type_reference | [test_domain_semantics_extension](../modules/test_domain_semantics_extension.md) | — |
