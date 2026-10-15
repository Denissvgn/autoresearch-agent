# DynamicFormFields Module

**Path:** `ui/src/components/DynamicFormFields.tsx`

## Description

_Auto-generated from `ui/src/components/DynamicFormFields.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `FormField`, `api` |
| `../skill-plugins/registry` | `resolve` |
| `./hifi/primitives` | `Field` |
| `react` | `useEffect`, `useState` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `default` |
| Constants | `KNOWN_TYPES` |
| Module calls | `KNOWN_TYPES = Set` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/components/__tests__/DynamicFormFields.test.tsx"]
    n2["ui/src/components/DynamicFormFields.tsx"]
    n3["ui/src/components/hifi/primitives.tsx"]
    n4["ui/src/pages/NewResearch.tsx"]
    n5["ui/src/skill-plugins/registry.ts"]
    n1 --> n0
    n1 --> n2
    n1 --> n5
    n2 --> n0
    n2 --> n3
    n2 --> n5
    n4 --> n2
    n4 --> n3
    n5 --> n0
    click n0 "../modules/client.md"
    click n1 "../modules/DynamicFormFields.test.md"
    click n2 "../modules/DynamicFormFields.md"
    click n3 "../modules/primitives.md"
    click n4 "../modules/NewResearch.md"
    click n5 "../modules/registry.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [DynamicFormFields.test](../modules/DynamicFormFields.test.md) |
| Inbound | [NewResearch](../modules/NewResearch.md) |
| Outbound | [client](../modules/client.md) |
| Outbound | [primitives](../modules/primitives.md) |
| Outbound | [registry](../modules/registry.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 1 | 0 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [Props](../entities/DynamicFormFields_Props.md) | Class | 14 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `DynamicFormFields` | `({ fields, values, onChange, skillId }: Props)` | — | — |
