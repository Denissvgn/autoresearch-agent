# ResearchConfig

**Location:** `src/core/orchestrator.py:69`
**Bases:** —
**Module:** [orchestrator](../modules/orchestrator.md)

**Decorators:** `@dataclass`

## Description

_Auto-generated from `ResearchConfig` in `src/core/orchestrator.py`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `id` | `str` | *required* | — |
| `instrument` | `str` | *required* | — |
| `timeframe` | `str` | *required* | — |
| `model_type` | `str` | *required* | — |
| `tag` | `str` | `''` | — |
| `quick_mode` | `bool` | `False` | — |
| `max_iterations` | `int` | `30` | — |
| `max_budget_usd` | `float` | `10.0` | — |
| `timeout_s` | `int` | `0` | — |
| `focus_hint` | `Optional[str]` | `None` | — |
| `workspace_path` | `str` | `''` | — |
| `trading_mode` | `Optional[str]` | `None` | — |
| `agent_strategy` | `Optional[str]` | `None` | — |
| `initial_balance` | `Optional[float]` | `None` | — |
| `enable_hpo` | `bool` | `False` | — |
| `hpo_trials` | `int` | `20` | — |
| `hpo_timesteps` | `int` | `50000` | — |
| `resumed_from` | `Optional[str]` | `None` | — |
| `pipeline_id` | `Optional[str]` | `None` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

- **imported_by**: [session_manager](../modules/session_manager.md)
- **imported_by**: [test_orchestrator_command_audit](../modules/test_orchestrator_command_audit.md)
- **used_by**: `_config()` in [test_prompt_promotion_policy](../modules/test_prompt_promotion_policy.md)
