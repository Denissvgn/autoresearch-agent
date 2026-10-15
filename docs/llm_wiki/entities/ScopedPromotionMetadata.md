# ScopedPromotionMetadata

**Location:** `ui/src/api/client.ts:197`
**Kind:** Class
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `ScopedPromotionMetadata` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `schema_version` | `string` | No | — | — |
| `scope` | `PromotionScope` | No | — | — |
| `promotion_allowed` | `boolean` | No | — | — |
| `blockers` | `string[]` | No | — | — |
| `checks` | `PromotionGateCheck[]` | No | — | — |
| `required_prior_scopes` | `PromotionScope[]` | No | — | — |
| `prior_promotions` | `Record<string, unknown>` | No | — | — |
| `decision_chain` | `Array<Record<string, unknown>>` | No | — | — |
| `approval` | `Record<string, unknown>` | No | — | — |
| `evidence` | `Record<string, unknown>` | No | — | — |
| `rollback_target` | `string \| null` | No | — | — |
| `rollback_targets` | `Record<string, unknown>` | No | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [client](../modules/client.md) | 0 | `approval`, `blockers`, `checks`, `decision_chain`, `evidence`, `prior_promotions`, `promotion_allowed`, `required_prior_scopes`, `rollback_target`, `rollback_targets`, `schema_version`, `scope` |
