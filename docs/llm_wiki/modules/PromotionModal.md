# PromotionModal Module

**Path:** `ui/src/components/PromotionModal.tsx`

## Description

_Auto-generated from `ui/src/components/PromotionModal.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `ProductionOperations`, `PromotionApproval`, `PromotionPreview`, `PromotionPreviewRequest`, `PromotionScope`, `PromotionScopeRequest` |
| `../hooks/useResearch` | `usePreviewPromotion`, `useConfirmPromotion` |
| `../utils/productionOps` | `blockerLabels`, `scopeLabel`, `scopeSummary`, `toneClasses`, `toneForStatus` |
| `./ConfigDiff` | `ConfigDiff` |
| `react` | `useState` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `default` |
| Constants | `SCOPES` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/components/__tests__/PromotionModal.test.tsx"]
    n2["ui/src/components/ConfigDiff.tsx"]
    n3["ui/src/components/PromotionModal.tsx"]
    n4["ui/src/hooks/useResearch.ts"]
    n5["ui/src/utils/productionOps.ts"]
    n1 --> n0
    n1 --> n3
    n3 --> n0
    n3 --> n2
    n3 --> n4
    n3 --> n5
    n4 --> n0
    click n0 "../modules/client.md"
    click n1 "../modules/PromotionModal.test.md"
    click n2 "../modules/ConfigDiff.md"
    click n3 "../modules/PromotionModal.md"
    click n4 "../modules/useResearch.md"
    click n5 "../modules/productionOps.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [PromotionModal.test](../modules/PromotionModal.test.md) |
| Outbound | [client](../modules/client.md) |
| Outbound | [ConfigDiff](../modules/ConfigDiff.md) |
| Outbound | [useResearch](../modules/useResearch.md) |
| Outbound | [productionOps](../modules/productionOps.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 1 | 0 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [Props](../entities/PromotionModal_Props.md) | Class | 20 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `PromotionModal` | `({ researchId, operations, onClose }: Props)` | — | — |
