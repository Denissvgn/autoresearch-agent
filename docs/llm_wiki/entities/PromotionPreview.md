# PromotionPreview

**Location:** `ui/src/api/client.ts:125`
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `PromotionPreview` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `research_id` | `string` | *required* | — |
| `iteration` | `number` | *required* | — |
| `model_type` | `string` | *required* | — |
| `instrument` | `string` | *required* | — |
| `timeframe` | `string` | *required* | — |
| `scope` | `PromotionScope` | *required* | — |
| `promotion_scope` | `PromotionScope` | *required* | — |
| `promotion_allowed` | `boolean` | *required* | — |
| `scope_promotion_allowed` | `boolean` | *required* | — |
| `target_path` | `string` | *required* | — |
| `new_config` | `string` | *required* | — |
| `current_config` | `string | null` | *required* | — |
| `best_metric` | `number | null` | *required* | — |
| `gates_passed` | `boolean` | *required* | — |
| `gate_bundle_evaluation` | `PromotionGateEvaluation | null` | *required* | — |
| `consistency_report` | `ConsistencyReport | null` | *required* | — |
| `development_promotion_metadata` | `Record<string, unknown> | null` | *required* | — |
| `scoped_promotion_metadata` | `ScopedPromotionMetadata | null` | *required* | — |
| `promotion_metadata` | `Record<string, unknown> | null` | *required* | — |
| `scope_gate_evaluation` | `PromotionGateEvaluation | null` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

- **imported_by**: [PromotionModal](../modules/PromotionModal.md)
