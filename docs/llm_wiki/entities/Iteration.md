# Iteration

**Location:** `ui/src/api/client.ts:45`
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `Iteration` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `id` | `number` | *required* | — |
| `research_id` | `string` | *required* | — |
| `iteration` | `number` | *required* | — |
| `primary_metric` | `number | null` | *required* | — |
| `metric_name` | `string` | *required* | — |
| `all_gates_passed` | `boolean` | *required* | — |
| `decision` | `string` | *required* | — |
| `config_snapshot` | `string | null` | *required* | — |
| `metrics_json` | `string | null` | *required* | — |
| `created_at` | `string` | *required* | — |
| `metrics` | `Record<string, unknown>` | *required* | — |
| `mlflow_run_id` | `string` | *required* | — |
| `mlflow_url` | `string | null` | *required* | — |
| `model_version` | `string | null` | *required* | — |
| `model_registry_name` | `string | null` | *required* | — |
| `training_time_s` | `number | null` | *required* | — |
| `training_mode` | `string | null` | *required* | — |
| `description` | `string | null` | *required* | — |
| `secondary_metrics` | `Record<string, SecondaryMetric>` | *required* | — |
| `search_phase` | `string | null` | *required* | — |
| `attempt_snapshot_hash` | `string | null` | *required* | — |
| `attempt_snapshot_path` | `string | null` | *required* | — |
| `artifact_hash` | `string | null` | *required* | — |
| `config_snapshot_sha256` | `string | null` | *required* | — |
| `consistency_report` | `ConsistencyReport | null` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

- **imported_by**: [IterationsTable](../modules/IterationsTable.md)
- **imported_by**: [MetricsChart](../modules/MetricsChart.md)
