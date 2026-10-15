# registry Module

**Path:** `ui/src/skill-plugins/registry.ts`

## Description

_Auto-generated from `ui/src/skill-plugins/registry.ts`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `FormField` |
| `./types` | `SkillPluginRenderer` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `register`, `reset`, `resolve`, `unregister` |
| Constants | `_renderers` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/components/__tests__/DynamicFormFields.test.tsx"]
    n2["ui/src/components/DynamicFormFields.tsx"]
    n3["ui/src/skill-plugins/registry.ts"]
    n4["ui/src/skill-plugins/types.ts"]
    n1 --> n0
    n1 --> n2
    n1 --> n3
    n2 --> n0
    n2 --> n3
    n3 --> n0
    n3 --> n4
    n4 --> n0
    click n0 "../modules/client.md"
    click n1 "../modules/DynamicFormFields.test.md"
    click n2 "../modules/DynamicFormFields.md"
    click n3 "../modules/registry.md"
    click n4 "../modules/types.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [DynamicFormFields.test](../modules/DynamicFormFields.test.md) |
| Inbound | [DynamicFormFields](../modules/DynamicFormFields.md) |
| Outbound | [client](../modules/client.md) |
| Outbound | [types](../modules/types.md) |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `register` | `(renderer: SkillPluginRenderer) -> () => void` | — | Register a skill plugin renderer. Idempotent on `renderer.id` — re-registering |
| `unregister` | `(id: string) -> void` | — | Remove a renderer by id. |
| `resolve` | `(field: FormField) -> SkillPluginRenderer \| null` | — | Resolve a renderer for the given field, or `null` if no plugin handles it. |
| `reset` | `() -> void` | — | Test-only: clear the registry. |
