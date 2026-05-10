# client Module

**Path:** `ui/src/api/client.ts`

## Description

_Auto-generated from `ui/src/api/client.ts`._

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ResearchSession](../entities/ResearchSession.md) | 4 | — | — |
| [PaginatedResponse](../entities/PaginatedResponse.md) | 33 | — | — |
| [SecondaryMetric](../entities/SecondaryMetric.md) | 40 | — | — |
| [Iteration](../entities/Iteration.md) | 45 | — | — |
| [ConsistencyReport](../entities/ConsistencyReport.md) | 75 | — | — |
| [AgentLogEntry](../entities/AgentLogEntry.md) | 86 | — | — |
| [Promotion](../entities/Promotion.md) | 96 | — | — |
| [PromotionApproval](../entities/client_PromotionApproval.md) | 112 | — | — |
| [PromotionScopeRequest](../entities/client_PromotionScopeRequest.md) | 120 | — | — |
| [PromotionPreview](../entities/PromotionPreview.md) | 125 | — | — |
| [PromotionGateCheck](../entities/PromotionGateCheck.md) | 148 | — | — |
| [PromotionGateEvaluation](../entities/PromotionGateEvaluation.md) | 155 | — | — |
| [ScopedPromotionMetadata](../entities/ScopedPromotionMetadata.md) | 162 | — | — |
| [StartResearchRequest](../entities/client_StartResearchRequest.md) | 177 | — | — |
| [HpoTrial](../entities/HpoTrial.md) | 199 | — | — |
| [HpoStudy](../entities/HpoStudy.md) | 207 | — | — |
| [ResearchState](../entities/ResearchState.md) | 226 | — | — |
| [ProductionOperations](../entities/ProductionOperations.md) | 262 | — | — |
| [ProductionCandidate](../entities/ProductionCandidate.md) | 284 | — | — |
| [BlockerDetail](../entities/BlockerDetail.md) | 297 | — | — |
| [CompactPromotion](../entities/CompactPromotion.md) | 302 | — | — |
| [PromotionScopeStatus](../entities/PromotionScopeStatus.md) | 315 | — | — |
| [ProductionWarning](../entities/ProductionWarning.md) | 326 | — | — |
| [RlProfitSummary](../entities/RlProfitSummary.md) | 333 | — | — |
| [FeatureReadinessChannel](../entities/FeatureReadinessChannel.md) | 343 | — | — |
| [FeatureReadinessSummary](../entities/FeatureReadinessSummary.md) | 350 | — | — |
| [OosProvenanceSummary](../entities/OosProvenanceSummary.md) | 356 | — | — |
| [InferenceParitySummary](../entities/InferenceParitySummary.md) | 369 | — | — |
| [RollbackStatusSummary](../entities/RollbackStatusSummary.md) | 376 | — | — |
| [ProductionAuditEvent](../entities/ProductionAuditEvent.md) | 383 | — | — |
| [SystemStatus](../entities/SystemStatus.md) | 395 | — | — |
| [InstrumentInfo](../entities/InstrumentInfo.md) | 401 | — | — |
| [ModelInfo](../entities/ModelInfo.md) | 407 | — | — |
| [PromotionScope](../entities/PromotionScope.md) | 110 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `getAutoresearchApiToken` | `() -> string | null` | — | — |
| `hasBuildTimeAutoresearchApiToken` | `() -> boolean` | — | — |
| `setAutoresearchApiToken` | `(token: string) -> void` | — | — |
| `clearAutoresearchApiToken` | `() -> void` | — | — |
| `getAutoresearchWebSocketProtocols` | `() -> string[] | undefined` | — | — |
| `normalizeListResponse` | `(payload: T[] | PaginatedResponse<T>) -> T[]` | — | — |
