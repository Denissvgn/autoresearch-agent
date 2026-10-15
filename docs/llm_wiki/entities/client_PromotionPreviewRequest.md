# PromotionPreviewRequest

**Location:** `ui/src/api/client.ts:139`
**Kind:** Class
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `PromotionPreviewRequest` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `scope` | `PromotionScope` | Yes | — | — |
| `approval` | `PromotionApproval \| null` | No | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["PromotionPreviewRequest (ui/src/api/client.ts)"]
    n1["ui/src/components/PromotionModal.tsx"]
    n2["ui/src/hooks/useResearch.ts"]
    n1 --> n0
    n2 --> n0
    click n0 "../modules/client.md"
    click n1 "../modules/PromotionModal.md"
    click n2 "../modules/useResearch.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [client](../modules/client.md) | 0 | `approval`, `scope` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `PromotionModal` | import | [PromotionModal](../modules/PromotionModal.md) | — |
| `useResearch` | import | [useResearch](../modules/useResearch.md) | — |
