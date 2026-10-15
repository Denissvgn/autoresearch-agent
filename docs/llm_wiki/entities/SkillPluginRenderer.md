# SkillPluginRenderer

**Location:** `ui/src/skill-plugins/types.ts:33`
**Kind:** Class
**Bases:** —
**Module:** [types](../modules/types.md)

## Description

A renderer for one or more field types. Registered against the plugin
registry; the first renderer whose `canRender` returns true wins.

## Attributes

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `id` | `string` | Yes | — | — |
| `canRender` | `(field: FormField) => boolean` | Yes | — | — |
| `render` | `(props: SkillPluginRendererProps) => ReactNode` | Yes | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SkillPluginRenderer (ui/src/skill-plugins/types.ts)"]
    n1["register (ui/src/skill-plugins/registry.ts)"]
    n2["resolve (ui/src/skill-plugins/registry.ts)"]
    n1 --> n0
    n2 --> n0
    click n0 "../modules/types.md"
    click n1 "../modules/registry.md"
    click n2 "../modules/registry.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [types](../modules/types.md) | 0 | `canRender`, `id`, `render` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `register` | type_reference | [registry](../modules/registry.md) | — |
| `resolve` | type_reference | [registry](../modules/registry.md) | — |
