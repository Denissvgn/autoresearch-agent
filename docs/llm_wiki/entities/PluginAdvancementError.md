# PluginAdvancementError

**Location:** `src/core/phase_resolver.py:33`
**Kind:** Class
**Bases:** `RuntimeError`
**Module:** [phase_resolver](../modules/phase_resolver.md)

## Description

Base error for plugin phase advancement (explicit, fail-closed).

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["PluginAdvancementError (src/core/phase_resolver.py)"]
    n1["RuntimeError"]
    n2["PluginAdvancementFailed (src/core/phase_resolver.py)"]
    n3["PluginAdvancementRejected (src/core/phase_resolver.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    click n0 "../modules/phase_resolver.md"
    click n2 "../modules/phase_resolver.md"
    click n3 "../modules/phase_resolver.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [phase_resolver](../modules/phase_resolver.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `RuntimeError` | — |
| Subclass | `PluginAdvancementFailed` | [phase_resolver](../modules/phase_resolver.md) |
| Subclass | `PluginAdvancementRejected` | [phase_resolver](../modules/phase_resolver.md) |
