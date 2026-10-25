# HarnessContextPanel Module

**Path:** `ui/src/components/HarnessContextPanel.tsx`

## Description

_Auto-generated from `ui/src/components/HarnessContextPanel.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `HarnessContext` |

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
    n2["ui/src/components/HarnessContextPanel.tsx"]
    n3["ui/src/pages/ResearchDetail.tsx"]
    n1 --> n0
    n1 --> n2
    n2 --> n0
    n3 --> n0
    n3 --> n2
    click n0 "../modules/client.md"
    click n1 "../modules/HarnessUI.test.md"
    click n2 "../modules/HarnessContextPanel.md"
    click n3 "../modules/ResearchDetail.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [HarnessUI.test](../modules/HarnessUI.test.md) |
| Inbound | [ResearchDetail](../modules/ResearchDetail.md) |
| Outbound | [client](../modules/client.md) |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [HarnessContextPanelProps](../entities/HarnessContextPanelProps.md) | Class | 7 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `HarnessContextPanel` | `({ context, onAction }: HarnessContextPanelProps)` | — | — |
