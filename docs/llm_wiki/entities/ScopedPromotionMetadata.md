# ScopedPromotionMetadata

**Location:** `ui/src/api/client.ts:162`
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `ScopedPromotionMetadata` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `schema_version` | `string` | *required* | — |
| `scope` | `PromotionScope` | *required* | — |
| `promotion_allowed` | `boolean` | *required* | — |
| `blockers` | `string[]` | *required* | — |
| `checks` | `PromotionGateCheck[]` | *required* | — |
| `required_prior_scopes` | `PromotionScope[]` | *required* | — |
| `prior_promotions` | `Record<string, unknown>` | *required* | — |
| `decision_chain` | `Array<Record<string, unknown>>` | *required* | — |
| `approval` | `Record<string, unknown>` | *required* | — |
| `evidence` | `Record<string, unknown>` | *required* | — |
| `rollback_target` | `string | null` | *required* | — |
| `rollback_targets` | `Record<string, unknown>` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

*No cross-module references detected.*
