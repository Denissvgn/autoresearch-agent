# FeatureReadinessChannel

**Location:** `ui/src/api/client.ts:394`
**Kind:** Class
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `FeatureReadinessChannel` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `status` | `string` | Yes | — | — |
| `passed` | `boolean` | Yes | — | — |
| `metrics` | `Record<string, number>` | Yes | — | — |
| `details` | `Record<string, unknown>` | No | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["FeatureReadinessChannel (ui/src/api/client.ts)"]
    n1["ui/src/components/ProductionOpsPanel.tsx"]
    n1 --> n0
    click n0 "../modules/client.md"
    click n1 "../modules/ProductionOpsPanel.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [client](../modules/client.md) | 0 | `details`, `metrics`, `passed`, `status` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `ProductionOpsPanel` | import | [ProductionOpsPanel](../modules/ProductionOpsPanel.md) | — |
