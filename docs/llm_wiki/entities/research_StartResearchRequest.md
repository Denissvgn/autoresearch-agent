# StartResearchRequest

**Location:** `src/api/research.py:189`
**Bases:** `BaseModel`
**Module:** [research](../modules/research.md)

## Description

_Auto-generated from `StartResearchRequest` in `src/api/research.py`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `instrument` | `str` | `Field(...)` | — |
| `timeframe` | `str` | `Field(...)` | — |
| `model_type` | `str` | `Field(...)` | — |
| `tag` | `Optional[str]` | `Field(...)` | — |
| `quick_mode` | `Optional[bool]` | `Field(...)` | — |
| `max_iterations` | `Optional[int]` | `Field(...)` | — |
| `max_budget_usd` | `Optional[float]` | `Field(...)` | — |
| `timeout_minutes` | `Optional[int]` | `Field(...)` | — |
| `focus_hint` | `Optional[str]` | `Field(...)` | — |
| `trading_mode` | `Optional[str]` | `Field(...)` | — |
| `agent_strategy` | `Optional[str]` | `Field(...)` | — |
| `initial_balance` | `Optional[float]` | `Field(...)` | — |
| `enable_hpo` | `Optional[bool]` | `Field(...)` | — |
| `hpo_trials` | `Optional[int]` | `Field(...)` | — |
| `hpo_timesteps` | `Optional[int]` | `Field(...)` | — |
| `phase_budgets` | `Optional[Dict[str, int]]` | `Field(...)` | — |
| `manifest` | `Optional[Dict[str, Any]]` | `Field(...)` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `validate_phase_budgets` | `(value: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]` | `@field_validator('phase_budgets')`, `@classmethod` | — |

## Relationships

*No cross-module references detected.*
