# ResearchState

**Location:** `ui/src/api/client.ts:226`
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `ResearchState` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `schema_version` | `string` | *required* | — |
| `research_id` | `string` | *required* | — |
| `model_type` | `string` | *required* | — |
| `status` | `string` | *required* | — |
| `research_outcome` | `string | null` | *required* | — |
| `terminal_reason` | `string | null` | *required* | — |
| `current_phase` | `string | null` | *required* | — |
| `next_action` | `string | null` | *required* | — |
| `phase_state` | `{
    current_phase: string | null;
    next_action: string | null;
    blocked: boolean;
    block_reason: string | null;
    phases: Array<{ id: string; label: string; status: string; next_action: string }>;
  }` | *required* | — |
| `top_candidates` | `Array<Record<string, unknown>>` | *required* | — |
| `failed_pruned_configs` | `Array<Record<string, unknown>>` | *required* | — |
| `gate_failure_reasons` | `Array<{ iteration: number; blockers: string[] }>` | *required* | — |
| `budget_usage` | `{
    api_cost_usd: number;
    max_budget_usd: number;
    iterations_used: number;
    max_iterations: number;
  }` | *required* | — |
| `hpo_studies` | `HpoStudy[]` | *required* | — |
| `hpo_study_ids` | `Array<string | number | null>` | *required* | — |
| `artifact_hashes` | `Array<{ iteration: number; artifact_hash: string }>` | *required* | — |
| `mlflow_links` | `Array<{ iteration: number; mlflow_run_id: string }>` | *required* | — |
| `promoted_version` | `Promotion | null` | *required* | — |
| `rollback_target` | `string | null` | *required* | — |
| `smoke_status` | `Record<string, unknown> | null` | *required* | — |
| `paper_status` | `unknown` | *required* | — |
| `production_operations` | `ProductionOperations | null` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

- **imported_by**: [ProductionOpsPanel](../modules/ProductionOpsPanel.md)
- **imported_by**: [ResearchStatePanel](../modules/ResearchStatePanel.md)
