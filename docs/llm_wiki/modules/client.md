# client Module

**Path:** `ui/src/api/client.ts`

## Description

_Auto-generated from `ui/src/api/client.ts`._

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `AgentLogEntry`, `BlockerDetail`, `CompactPromotion`, `ConsistencyReport`, `CostEstimate`, `FeatureReadinessChannel`, `FeatureReadinessSummary`, `FormField`, `GeneratedSkillDraft`, `HpoStudy`, `HpoTrial`, `InferenceParitySummary`, `Iteration`, `LeaderboardEntry`, `MetricColumn`, `MetricSchema`, `ModelInfo`, `OosProvenanceSummary`, `PaginatedResponse`, `PolicyFinding`, `ProductionAuditEvent`, `ProductionCandidate`, `ProductionOperations`, `ProductionWarning`, `Promotion`, `PromotionApproval`, `PromotionGateCheck`, `PromotionGateEvaluation`, `PromotionPreview`, `PromotionPreviewRequest`, `PromotionScope`, `PromotionScopeRequest`, `PromotionScopeStatus`, `ResearchSession`, `ResearchState`, `RlProfitSummary`, `RollbackStatusSummary`, `ScopedPromotionMetadata`, `SecondaryMetric`, `SkillLeaderboard`, `SkillSummary`, `StartResearchRequest`, `SubjectInfo`, `SystemStatus`, `api`, `clearAutoresearchApiToken`, `getAutoresearchApiToken`, `getAutoresearchWebSocketProtocols`, `hasBuildTimeAutoresearchApiToken`, `normalizeListResponse`, `setAutoresearchApiToken` |
| Constants | `BASE`, `API_TOKEN_STORAGE_KEY`, `api` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui"]
    n1["ui/src/api/client.ts"]
    n0 --> n1
    click n1 "../modules/client.md"
```

> Module-level dependencies exceed the generated-diagram limits, so the diagram and table below group them by top-level package. Counts report the number of module neighbors in each package.

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | `ui` (23) |

> All 23 module neighbor(s) are summarized by package because the module-level view exceeds the 12-node limit.

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [ResearchSession](../entities/ResearchSession.md) | Class | 4 | — | — |
| [PaginatedResponse](../entities/PaginatedResponse.md) | Class | 38 | — | — |
| [SecondaryMetric](../entities/SecondaryMetric.md) | Class | 45 | — | — |
| [Iteration](../entities/Iteration.md) | Class | 50 | — | — |
| [ConsistencyReport](../entities/ConsistencyReport.md) | Class | 89 | — | — |
| [AgentLogEntry](../entities/AgentLogEntry.md) | Class | 100 | — | — |
| [Promotion](../entities/Promotion.md) | Class | 111 | — | — |
| [PromotionApproval](../entities/client_PromotionApproval.md) | Class | 127 | — | — |
| [PromotionPreviewRequest](../entities/client_PromotionPreviewRequest.md) | Class | 139 | — | — |
| [PromotionScopeRequest](../entities/client_PromotionScopeRequest.md) | Class | 144 | — | — |
| [PromotionPreview](../entities/PromotionPreview.md) | Class | 149 | — | — |
| [PromotionGateCheck](../entities/PromotionGateCheck.md) | Class | 183 | — | — |
| [PromotionGateEvaluation](../entities/PromotionGateEvaluation.md) | Class | 190 | — | — |
| [ScopedPromotionMetadata](../entities/ScopedPromotionMetadata.md) | Class | 197 | — | — |
| [StartResearchRequest](../entities/client_StartResearchRequest.md) | Class | 212 | — | — |
| [HpoTrial](../entities/HpoTrial.md) | Class | 227 | — | — |
| [HpoStudy](../entities/HpoStudy.md) | Class | 235 | — | — |
| [ResearchState](../entities/ResearchState.md) | Class | 254 | — | — |
| [ProductionOperations](../entities/ProductionOperations.md) | Class | 311 | — | — |
| [ProductionCandidate](../entities/ProductionCandidate.md) | Class | 333 | — | — |
| [BlockerDetail](../entities/BlockerDetail.md) | Class | 347 | — | — |
| [CompactPromotion](../entities/CompactPromotion.md) | Class | 352 | — | — |
| [PromotionScopeStatus](../entities/PromotionScopeStatus.md) | Class | 365 | — | — |
| [ProductionWarning](../entities/ProductionWarning.md) | Class | 376 | — | — |
| [RlProfitSummary](../entities/RlProfitSummary.md) | Class | 383 | — | — |
| [FeatureReadinessChannel](../entities/FeatureReadinessChannel.md) | Class | 393 | — | — |
| [FeatureReadinessSummary](../entities/FeatureReadinessSummary.md) | Class | 400 | — | — |
| [OosProvenanceSummary](../entities/OosProvenanceSummary.md) | Class | 406 | — | — |
| [InferenceParitySummary](../entities/InferenceParitySummary.md) | Class | 419 | — | — |
| [RollbackStatusSummary](../entities/RollbackStatusSummary.md) | Class | 426 | — | — |
| [ProductionAuditEvent](../entities/ProductionAuditEvent.md) | Class | 433 | — | — |
| [SystemStatus](../entities/SystemStatus.md) | Class | 445 | — | — |
| [ModelInfo](../entities/ModelInfo.md) | Class | 451 | — | — |
| [SkillSummary](../entities/SkillSummary.md) | Class | 459 | — | — |
| [PolicyFinding](../entities/PolicyFinding.md) | Class | 474 | — | — |
| [GeneratedSkillDraft](../entities/GeneratedSkillDraft.md) | Class | 480 | — | — |
| [CostEstimate](../entities/CostEstimate.md) | Class | 491 | — | — |
| [FormField](../entities/FormField.md) | Class | 500 | — | — |
| [MetricColumn](../entities/client_MetricColumn.md) | Class | 513 | — | — |
| [MetricSchema](../entities/client_MetricSchema.md) | Class | 521 | — | — |
| [SubjectInfo](../entities/SubjectInfo.md) | Class | 529 | — | — |
| [LeaderboardEntry](../entities/LeaderboardEntry.md) | Class | 536 | — | — |
| [SkillLeaderboard](../entities/SkillLeaderboard.md) | Class | 551 | — | — |
| [PromotionScope](../entities/client_PromotionScope.md) | Type alias | 125 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `getAutoresearchApiToken` | `() -> string \| null` | — | — |
| `hasBuildTimeAutoresearchApiToken` | `() -> boolean` | — | — |
| `setAutoresearchApiToken` | `(token: string) -> void` | — | — |
| `clearAutoresearchApiToken` | `() -> void` | — | — |
| `getAutoresearchWebSocketProtocols` | `() -> string[] \| undefined` | — | — |
| `normalizeListResponse` | `(payload: T[] \| PaginatedResponse<T>) -> T[]` | — | — |
