# ConsistencyReport

**Location:** `ui/src/api/client.ts:89`
**Kind:** Class
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `ConsistencyReport` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `schema_version` | `string` | Yes | — | — |
| `passed` | `boolean` | Yes | — | — |
| `blockers` | `string[]` | Yes | — | — |
| `checks` | `Array<{ name: string; status: string; detail?: string \| null }>` | Yes | — | — |
| `config_snapshot_sha256` | `string \| null` | No | — | — |
| `artifact_hash` | `string \| null` | No | — | — |
| `feature_schema_hash` | `string \| null` | No | — | — |
| `mlflow_run_id` | `string \| null` | No | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [client](../modules/client.md) | 0 | `artifact_hash`, `blockers`, `checks`, `config_snapshot_sha256`, `feature_schema_hash`, `mlflow_run_id`, `passed`, `schema_version` |
