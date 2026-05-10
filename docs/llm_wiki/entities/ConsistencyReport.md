# ConsistencyReport

**Location:** `ui/src/api/client.ts:75`
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `ConsistencyReport` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `schema_version` | `string` | *required* | — |
| `passed` | `boolean` | *required* | — |
| `blockers` | `string[]` | *required* | — |
| `checks` | `Array<{ name: string; status: string; detail?: string | null }>` | *required* | — |
| `config_snapshot_sha256` | `string | null` | *required* | — |
| `artifact_hash` | `string | null` | *required* | — |
| `feature_schema_hash` | `string | null` | *required* | — |
| `mlflow_run_id` | `string | null` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

*No cross-module references detected.*
