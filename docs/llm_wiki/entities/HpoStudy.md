# HpoStudy

**Location:** `ui/src/api/client.ts:235`
**Kind:** Class
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `HpoStudy` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `id` | `number` | Yes | — | — |
| `research_id` | `string` | Yes | — | — |
| `iteration` | `number` | Yes | — | — |
| `n_trials` | `number` | Yes | — | — |
| `completed_trials` | `number` | Yes | — | — |
| `best_composite` | `number \| null` | Yes | — | — |
| `training_time_s` | `number \| null` | Yes | — | — |
| `top_trials` | `HpoTrial[]` | Yes | — | — |
| `study_id` | `string \| null` | No | — | — |
| `max_trials` | `number \| null` | No | — | — |
| `search_space` | `Record<string, unknown>` | No | — | — |
| `budget` | `Record<string, unknown>` | No | — | — |
| `timeout_s` | `number \| null` | No | — | — |
| `quick_mode` | `boolean \| number` | No | — | — |
| `status` | `string` | Yes | — | — |
| `created_at` | `string` | Yes | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [client](../modules/client.md) | 0 | `best_composite`, `budget`, `completed_trials`, `created_at`, `id`, `iteration`, `max_trials`, `n_trials`, `quick_mode`, `research_id`, `search_space`, `status` |
