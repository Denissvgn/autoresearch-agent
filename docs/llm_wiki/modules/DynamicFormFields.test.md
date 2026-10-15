# DynamicFormFields.test Module

**Path:** `ui/src/components/__tests__/DynamicFormFields.test.tsx`

## Description

_Auto-generated from `ui/src/components/__tests__/DynamicFormFields.test.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../../api/client` | `apiModule`, `FormField` |
| `../../skill-plugins/registry` | `reset`, `register` |
| `../DynamicFormFields` | `DynamicFormFields` |
| `@testing-library/react` | `render`, `screen` |
| `@testing-library/user-event` | `userEvent` |
| `vitest` | `describe`, `it`, `expect`, `beforeEach`, `afterEach`, `vi` |

## Module Signals

| Signal | Values |
|--------|--------|
| Module calls | `describe` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/components/__tests__/DynamicFormFields.test.tsx"]
    n2["ui/src/components/DynamicFormFields.tsx"]
    n3["ui/src/skill-plugins/registry.ts"]
    n1 --> n0
    n1 --> n2
    n1 --> n3
    n2 --> n0
    n2 --> n3
    n3 --> n0
    click n0 "../modules/client.md"
    click n1 "../modules/DynamicFormFields.test.md"
    click n2 "../modules/DynamicFormFields.md"
    click n3 "../modules/registry.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [client](../modules/client.md) |
| Outbound | [DynamicFormFields](../modules/DynamicFormFields.md) |
| Outbound | [registry](../modules/registry.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 3 | 0 |
