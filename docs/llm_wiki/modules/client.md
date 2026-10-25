# client Module

**Path:** `ui/src/api/client.ts`

## Description

_Auto-generated from `ui/src/api/client.ts`._

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `AgentLogEntry`, `BlockerDetail`, `CompactPromotion`, `ConsistencyReport`, `CostEstimate`, `FeatureReadinessChannel`, `FeatureReadinessSummary`, `FormField`, `GeneratedSkillDraft`, `HarnessCapabilityEntry`, `HarnessContext`, `HarnessDescriptor`, `HarnessPreflightCheck`, `HpoStudy`, `HpoTrial`, `InferenceParitySummary`, `Iteration`, `LeaderboardEntry`, `LifecycleAction`, `MetricColumn`, `MetricSchema`, `ModelInfo`, `OosProvenanceSummary`, `PaginatedResponse`, `PolicyFinding`, `ProductionAuditEvent`, `ProductionCandidate`, `ProductionOperations`, `ProductionWarning`, `Promotion`, `PromotionApproval`, `PromotionGateCheck`, `PromotionGateEvaluation`, `PromotionPreview`, `PromotionPreviewRequest`, `PromotionScope`, `PromotionScopeRequest`, `PromotionScopeStatus`, `ResearchSession`, `ResearchState`, `RlProfitSummary`, `RollbackStatusSummary`, `ScopedPromotionMetadata`, `SecondaryMetric`, `SkillLeaderboard`, `SkillLeaderboardGroup`, `SkillSummary`, `StartResearchRequest`, `SubjectInfo`, `SystemStatus`, `api`, `clearAutoresearchApiToken`, `getAutoresearchApiToken`, `getAutoresearchWebSocketProtocols`, `hasBuildTimeAutoresearchApiToken`, `normalizeListResponse`, `setAutoresearchApiToken` |
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
| Inbound | `ui` (25) |

> All 25 module neighbor(s) are summarized by package because the module-level view exceeds the 12-node limit.

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
| [HpoTrial](../entities/HpoTrial.md) | Class | 228 | — | — |
| [HpoStudy](../entities/HpoStudy.md) | Class | 236 | — | — |
| [ResearchState](../entities/ResearchState.md) | Class | 255 | — | — |
| [ProductionOperations](../entities/ProductionOperations.md) | Class | 312 | — | — |
| [ProductionCandidate](../entities/ProductionCandidate.md) | Class | 334 | — | — |
| [BlockerDetail](../entities/BlockerDetail.md) | Class | 348 | — | — |
| [CompactPromotion](../entities/CompactPromotion.md) | Class | 353 | — | — |
| [PromotionScopeStatus](../entities/PromotionScopeStatus.md) | Class | 366 | — | — |
| [ProductionWarning](../entities/ProductionWarning.md) | Class | 377 | — | — |
| [RlProfitSummary](../entities/RlProfitSummary.md) | Class | 384 | — | — |
| [FeatureReadinessChannel](../entities/FeatureReadinessChannel.md) | Class | 394 | — | — |
| [FeatureReadinessSummary](../entities/FeatureReadinessSummary.md) | Class | 401 | — | — |
| [OosProvenanceSummary](../entities/OosProvenanceSummary.md) | Class | 407 | — | — |
| [InferenceParitySummary](../entities/InferenceParitySummary.md) | Class | 420 | — | — |
| [RollbackStatusSummary](../entities/RollbackStatusSummary.md) | Class | 427 | — | — |
| [ProductionAuditEvent](../entities/ProductionAuditEvent.md) | Class | 434 | — | — |
| [SystemStatus](../entities/SystemStatus.md) | Class | 446 | — | — |
| [ModelInfo](../entities/ModelInfo.md) | Class | 452 | — | — |
| [SkillSummary](../entities/SkillSummary.md) | Class | 460 | — | — |
| [PolicyFinding](../entities/PolicyFinding.md) | Class | 475 | — | — |
| [GeneratedSkillDraft](../entities/GeneratedSkillDraft.md) | Class | 481 | — | — |
| [CostEstimate](../entities/client_CostEstimate.md) | Class | 492 | — | — |
| [FormField](../entities/FormField.md) | Class | 501 | — | — |
| [MetricColumn](../entities/client_MetricColumn.md) | Class | 514 | — | — |
| [MetricSchema](../entities/client_MetricSchema.md) | Class | 522 | — | — |
| [SubjectInfo](../entities/SubjectInfo.md) | Class | 530 | — | — |
| [LeaderboardEntry](../entities/LeaderboardEntry.md) | Class | 537 | — | — |
| [SkillLeaderboardGroup](../entities/SkillLeaderboardGroup.md) | Class | 552 | — | — |
| [SkillLeaderboard](../entities/SkillLeaderboard.md) | Class | 562 | — | — |
| [HarnessPreflightCheck](../entities/HarnessPreflightCheck.md) | Class | 669 | — | — |
| [HarnessCapabilityEntry](../entities/HarnessCapabilityEntry.md) | Class | 675 | — | — |
| [HarnessDescriptor](../entities/HarnessDescriptor.md) | Class | 680 | — | — |
| [LifecycleAction](../entities/LifecycleAction.md) | Class | 694 | — | — |
| [HarnessContext](../entities/HarnessContext.md) | Class | 700 | — | — |
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
