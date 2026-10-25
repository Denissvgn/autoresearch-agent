# HarnessPicker Module

**Path:** `ui/src/components/HarnessPicker.tsx`

## Description

_Auto-generated from `ui/src/components/HarnessPicker.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `HarnessDescriptor` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `default` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/components/__tests__/HarnessUI.test.tsx"]
    n2["ui/src/components/HarnessPicker.tsx"]
    n3["ui/src/pages/NewResearch.tsx"]
    n1 --> n0
    n1 --> n2
    n2 --> n0
    n3 --> n2
    click n0 "../modules/client.md"
    click n1 "../modules/HarnessUI.test.md"
    click n2 "../modules/HarnessPicker.md"
    click n3 "../modules/NewResearch.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [HarnessUI.test](../modules/HarnessUI.test.md) |
| Inbound | [NewResearch](../modules/NewResearch.md) |
| Outbound | [client](../modules/client.md) |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [HarnessPickerProps](../entities/HarnessPickerProps.md) | Class | 7 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `HarnessPicker` | `({ harnesses, selected, onSelect }: HarnessPickerProps)` | — | — |
