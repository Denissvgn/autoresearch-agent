# test_phase_hpo_consistency_state Module

**Path:** `tests/test_phase_hpo_consistency_state.py`

## Description

_Auto-generated from `tests/test_phase_hpo_consistency_state.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `pytest` | `pytest` |
| `src.core.consistency_validator` | `build_consistency_report` |
| `src.core.research_phase_plan` | `build_phase_state` |
| `src.core.research_state` | `build_research_state` |
| `src.core.structured_hpo` | `build_structured_hpo_plan`, `materialize_planned_trials`, `validate_config_patch` |
| `yaml` | `yaml` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_phase_status` | `(state: dict, phase_id: str) -> str` | — | — |
| `_passing_metrics` | `() -> dict` | — | — |
| `test_direction_phase_state_advances_past_tabular_sweeps` | `()` | — | — |
| `test_promotion_proposal_requires_preview_or_promotion_evidence` | `()` | — | — |
| `test_research_state_marks_iteration_budget_exhausted_when_phases_pending` | `()` | — | — |
| `test_structured_direction_hpo_plan_is_bounded_by_iterations` | `()` | — | — |
| `test_structured_hpo_plan_never_inflates_requested_trials` | `()` | — | — |
| `test_structured_hpo_plan_bounds_direction_trials_by_budget` | `()` | — | — |
| `test_direction_structured_trials_include_deadzone_horizon_calibration_controls` | `()` | — | — |
| `test_structured_volatility_hpo_uses_current_feature_library_version` | `()` | — | — |
| `test_structured_hpo_invalid_knobs_are_rejected` | `()` | — | — |
| `test_materialize_planned_trials_writes_concrete_train_yamls` | `(tmp_path)` | — | — |
| `test_consistency_report_passes_for_complete_direction_candidate` | `()` | — | — |
| `test_consistency_report_blocks_missing_inference_parity_for_candidate` | `()` | — | — |
| `test_consistency_report_warns_for_missing_artifact_on_non_candidate` | `()` | — | — |
| `test_research_state_summarizes_candidates_failures_and_budget` | `()` | — | — |
| `test_research_state_exposes_planned_trials_and_manual_review` | `()` | — | — |
