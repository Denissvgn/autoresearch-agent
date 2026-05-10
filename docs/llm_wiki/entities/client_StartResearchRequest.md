# StartResearchRequest

**Location:** `ui/src/api/client.ts:177`
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `StartResearchRequest` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `instrument` | `string` | *required* | — |
| `timeframe` | `string` | *required* | — |
| `model_type` | `string` | *required* | — |
| `tag` | `string` | *required* | — |
| `quick_mode` | `boolean` | *required* | — |
| `max_iterations` | `number` | *required* | — |
| `max_budget_usd` | `number` | *required* | — |
| `timeout_minutes` | `number` | *required* | — |
| `focus_hint` | `string` | *required* | — |
| `trading_mode` | `'stock' | 'margin'` | *required* | — |
| `agent_strategy` | `'AGGR' | 'CONS' | 'BALA' | 'SCAL'` | *required* | — |
| `initial_balance` | `number` | *required* | — |
| `enable_hpo` | `boolean` | *required* | — |
| `hpo_trials` | `number` | *required* | — |
| `hpo_timesteps` | `number` | *required* | — |
| `phase_budgets` | `{ direction?: number; volatility?: number; rl?: number }` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

- **imported_by**: [useResearch](../modules/useResearch.md)
