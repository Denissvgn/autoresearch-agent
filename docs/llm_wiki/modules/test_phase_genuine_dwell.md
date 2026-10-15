# test_phase_genuine_dwell Module

**Path:** `tests/test_phase_genuine_dwell.py`

## Description

Fix 8 — phases gated by ``auto_phase_evidence`` must still require
``min_iterations`` of phase-tagged iterations (or an explicit agent key).

Before this fix, prepare.py's permissive fallback keys (e.g.
``tsfm_fallback_validation: True``) auto-completed phases 4–7 on the very
first iteration, regardless of whether the agent did real work.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `pytest` | `pytest` |
| `src.core.research_phase_plan` | `_completed_phase_ids` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/research_phase_plan.py"]
    n1["tests/test_phase_genuine_dwell.py"]
    n1 --> n0
    click n0 "../modules/research_phase_plan.md"
    click n1 "../modules/test_phase_genuine_dwell.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [research_phase_plan](../modules/research_phase_plan.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_iteration` | `(*, metrics: dict, search_phase: str, iteration: int = 1) -> dict` | — | — |
| `test_tsfm_single_auto_evidence_iteration_does_not_complete_phase` | `() -> None` | — | — |
| `test_tsfm_two_auto_evidence_iterations_complete_phase` | `() -> None` | — | — |
| `test_tsfm_keyless_iterations_do_not_complete_phase` | `() -> None` | — | Two tsfm-tagged iterations carrying no structured TS-FM evidence must |
| `test_tsfm_keyless_single_iteration_does_not_complete_phase` | `() -> None` | — | — |
| `test_tsfm_structured_fallback_completes_after_dwell` | `() -> None` | — | — |
| `test_tsfm_structured_fallback_requires_passed_true` | `() -> None` | — | — |
| `test_tsfm_with_explicit_adapter_key_completes_immediately` | `() -> None` | — | — |
| `test_tsfm_with_structured_adapter_evidence_completes_immediately` | `() -> None` | — | — |
| `test_tsfm_structured_adapter_rejects_passed_false` | `() -> None` | — | — |
| `test_calibration_replay_requires_phase_tag_when_auto_only` | `() -> None` | — | calibration_replay_gates has min_iterations=1; an auto-evidence |
| `_valid_calibration_evidence` | `() -> dict` | — | A calibration_full_validation/economic_replay block that *passes* |
| `_valid_seed_evidence` | `(run_id: str = 'run-A') -> dict` | — | — |
| `_valid_parity_evidence` | `(run_id: str = 'run-A') -> dict` | — | — |
| `test_issue7_calibration_with_valid_evidence_off_phase_does_not_complete` | `() -> None` | — | Issue 7: VALID server-emitted calibration evidence on a tabular_sweeps |
| `test_issue7_calibration_with_in_phase_tag_does_complete` | `() -> None` | — | Same valid evidence, agent tagged the iterations in-phase, AND enough |
| `test_issue7_multi_seed_with_valid_evidence_off_phase_does_not_complete` | `() -> None` | — | — |
| `test_issue7_multi_seed_with_in_phase_tag_completes` | `() -> None` | — | Gap 2 floor: multi_seed_robustness=3 in-phase iters required. |
| `test_issue7_inference_parity_with_valid_evidence_off_phase_does_not_complete` | `() -> None` | — | — |
| `test_issue7_inference_parity_with_in_phase_tag_completes` | `() -> None` | — | Gap 2 floor: inference_parity_replay=2 in-phase iters required. |
| `test_issue7_tsfm_sweeps_still_completes_off_phase_via_explicit_key` | `() -> None` | — | tsfm_sweeps is deliberately OUT of _PHASE_REQUIRES_IN_PHASE_TAG — its |
| `test_inference_parity_dwell_gate_blocks_off_phase_iteration` | `() -> None` | — | Iteration tagged ``tabular_sweeps`` cannot complete |
| `_baseline_iteration` | `(config: dict) -> dict` | — | Baseline-shape iteration: knobs live under ``metrics_json.config``, |
| `test_issue10a_tabular_baseline_only_does_not_complete_tabular` | `() -> None` | — | Baseline carrying `direction_pct_threshold` + `roster_preset` no |
| `test_issue10a_tabular_with_variant_completes` | `() -> None` | — | A single iteration emitting the deliberate `tabular_sweep_variant` |
| `test_issue10a_tabular_six_in_phase_iters_completes_via_cardinality` | `() -> None` | — | Six phase-tagged iterations with NO `tabular_sweep_variant` still |
| `test_issue10a_atr_sweep_baseline_only_does_not_complete` | `() -> None` | — | `volatility_atr_mult` and `atr_multiplier` are baseline config |
| `test_issue10a_atr_sweep_with_enabled_flag_completes` | `() -> None` | — | `atr_mult_sweep_enabled` (already emitted by structured_hpo.py when |
| `test_issue10a_threshold_calibration_baseline_only_does_not_complete` | `() -> None` | — | `threshold_strategy` and `calibration_method` are baseline defaults |
| `test_issue10a_threshold_calibration_two_in_phase_iters_completes` | `() -> None` | — | Two phase-tagged iterations with no explicit key still complete |
| `test_issue10a_temporal_ensemble_baseline_only_does_not_complete` | `() -> None` | — | Baseline halflife / horizon / pruning config knobs must no longer |
| `test_issue10a_temporal_ensemble_two_in_phase_iters_completes` | `() -> None` | — | — |
| `test_gap2_calibration_one_in_phase_iter_does_not_complete` | `() -> None` | — | A single in-phase calibration iter is no longer enough; floor=2. |
| `test_gap2_calibration_two_in_phase_iters_completes` | `() -> None` | — | — |
| `test_gap2_multi_seed_two_in_phase_iters_does_not_complete` | `() -> None` | — | Two in-phase seed iters insufficient; floor=3 (need ≥3 seeds for |
| `test_gap2_multi_seed_three_in_phase_iters_completes` | `() -> None` | — | — |
| `test_gap2_inference_parity_one_in_phase_iter_does_not_complete` | `() -> None` | — | A single in-phase parity iter is no longer enough; floor=2. |
| `test_gap2_inference_parity_two_in_phase_iters_completes` | `() -> None` | — | — |
| `test_gap2_volatility_floors_match_direction` | `() -> None` | — | Same Gap-2 floors apply to volatility phases. |
