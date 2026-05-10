# ProductionOperations

**Location:** `ui/src/api/client.ts:262`
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `ProductionOperations` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `schema_version` | `string` | *required* | — |
| `research_id` | `string` | *required* | — |
| `model_type` | `string` | *required* | — |
| `candidate` | `ProductionCandidate | null` | *required* | — |
| `promotion` | `{
    blocked: boolean;
    blockers: string[];
    blocker_details: BlockerDetail[];
    latest_scope?: PromotionScope | null;
    latest_record?: CompactPromotion | null;
    scopes: PromotionScopeStatus[];
  }` | *required* | — |
| `warnings` | `ProductionWarning[]` | *required* | — |
| `rl_profit` | `RlProfitSummary` | *required* | — |
| `feature_readiness` | `FeatureReadinessSummary` | *required* | — |
| `oos_provenance` | `OosProvenanceSummary` | *required* | — |
| `inference_parity` | `InferenceParitySummary` | *required* | — |
| `rollback` | `RollbackStatusSummary` | *required* | — |
| `audit_events` | `ProductionAuditEvent[]` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

- **imported_by**: [ProductionOpsPanel](../modules/ProductionOpsPanel.md)
- **imported_by**: [PromotionModal](../modules/PromotionModal.md)
