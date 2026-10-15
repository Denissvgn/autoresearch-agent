# ProductionOpsPanel Module

**Path:** `ui/src/components/ProductionOpsPanel.tsx`

## Description

_Auto-generated from `ui/src/components/ProductionOpsPanel.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `FeatureReadinessChannel`, `ProductionOperations`, `ResearchState` |
| `../utils/productionOps` | `blockerLabels`, `formatMetric`, `productionReady`, `scopeSummary`, `toneClasses`, `toneForStatus`, `warningTone` |
| `./ClipboardCopy` | `ClipboardCopy` |
| `react` | `useState` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `default` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/components/ClipboardCopy.tsx"]
    n2["ui/src/components/ProductionOpsPanel.tsx"]
    n3["ui/src/utils/productionOps.ts"]
    n2 --> n0
    n2 --> n1
    n2 --> n3
    click n0 "../modules/client.md"
    click n1 "../modules/ClipboardCopy.md"
    click n2 "../modules/ProductionOpsPanel.md"
    click n3 "../modules/productionOps.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [client](../modules/client.md) |
| Outbound | [ClipboardCopy](../modules/ClipboardCopy.md) |
| Outbound | [productionOps](../modules/productionOps.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 1 | 0 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [Props](../entities/ProductionOpsPanel_Props.md) | Class | 14 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `ProductionOpsPanel` | `({ state }: Props)` | — | — |
