# types Module

**Path:** `ui/src/skill-plugins/types.ts`

## Description

_Auto-generated from `ui/src/skill-plugins/types.ts`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `FormField` |
| `react` | `ReactNode` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `SkillPluginRenderer`, `SkillPluginRendererProps` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/skill-plugins/registry.ts"]
    n2["ui/src/skill-plugins/types.ts"]
    n1 --> n0
    n1 --> n2
    n2 --> n0
    click n0 "../modules/client.md"
    click n1 "../modules/registry.md"
    click n2 "../modules/types.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [registry](../modules/registry.md) |
| Outbound | [client](../modules/client.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 1 | 0 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [SkillPluginRendererProps](../entities/SkillPluginRendererProps.md) | Class | 22 | — | Props passed to a skill plugin renderer. Mirrors the FieldInput contract so |
| [SkillPluginRenderer](../entities/SkillPluginRenderer.md) | Class | 33 | — | A renderer for one or more field types. Registered against the plugin |
