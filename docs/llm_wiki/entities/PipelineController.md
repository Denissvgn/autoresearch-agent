# PipelineController

**Location:** `src/core/pipeline_controller.py:163`
**Bases:** —
**Module:** [pipeline_controller](../modules/pipeline_controller.md)

## Description

Orchestrates sequential direction → volatility → rl research.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(store: ResultsStore, session_manager) -> None` | — | — |
| `request_stop` | `(pipeline_id: str) -> None` | — | — |
| `_should_stop` | `(pipeline_id: str) -> bool` | — | — |
| `_compute_phase_budgets` | `(config: PipelineConfig) -> Dict[str, int]` | — | — |
| `run` | `*(async)* (config: PipelineConfig) -> None` | — | Run the full pipeline: direction → volatility → enrich → rl. |
| `_start_phase` | `*(async)* (config: PipelineConfig, phase: str, phase_budget: int, phase_timeout_m: int) -> Dict[str, Any]` | — | Start a single phase as a research sub-session. |
| `_wait_for_session` | `*(async)* (session_id: str) -> None` | — | Poll until a session is no longer running. |
| `_evaluate_phase` | `*(async)* (session_id: str) -> bool` | — | Check if any iteration of a phase passed all gates. |
| `_promote_phase` | `*(async)* (session_id: str, phase: str) -> tuple[Dict[str, Any], Dict[str, Any]]` | — | Promote a completed phase through the audited ConfigPromoter path. |
| `_mark_promotion_blocked` | `*(async)* () -> None` | — | — |
| `_safe_mark_promotion_blocked` | `*(async)* () -> None` | — | — |
| `_run_enrichment` | `*(async)* (config: PipelineConfig) -> None` | — | Run enrich_rl_dataset.py between volatility and rl phases. |

## Relationships

- **imported_by**: [session_manager](../modules/session_manager.md)
- **imported_by**: [test_pipeline_promotion](../modules/test_pipeline_promotion.md)
