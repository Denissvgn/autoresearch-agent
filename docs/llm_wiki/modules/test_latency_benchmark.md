# test_latency_benchmark Module

**Path:** `tests/test_latency_benchmark.py`

## Description

Measured latency minimization: controls, noise, contention, promotion.

Real loopback measurements of real implementation changes: baseline
(scan), improved (index), and regressed (rescan) controls; noise and
repeat qualification; resource-contention detection; minimization
through storage and promotion; and the simulated-mode separation.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.core.latency_benchmark` | `MODE_SIMULATED`, `VARIANTS`, `Measurement`, `MeasurementProtocol`, `MeasurementStore`, `build_workload`, `decide_minimization`, `evaluation_context`, `promote_minimized`, `run_measurement` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/latency_benchmark.py"]
    n1["tests/test_latency_benchmark.py"]
    n1 --> n0
    click n0 "../modules/latency_benchmark.md"
    click n1 "../modules/test_latency_benchmark.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [latency_benchmark](../modules/latency_benchmark.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_stable_probe` | `()` | — | — |
| `_measure` | `(variant_id: str, **kwargs)` | — | — |
| `test_baseline_improved_and_regressed_controls` | `()` | — | — |
| `test_measured_improvement_is_selected_only_when_qualified` | `()` | — | — |
| `test_noisy_samples_do_not_become_a_winner` | `()` | — | — |
| `test_contention_and_incomplete_repeats_are_not_winners` | `()` | — | — |
| `test_incomparable_contexts_and_modes_never_win` | `()` | — | — |
| `test_simulated_scores_stay_a_separate_mode` | `()` | — | — |
| `test_minimization_through_storage_and_promotion` | `(tmp_path)` | — | — |
| `test_contention_probe_is_detectable` | `()` | — | — |
| `test_skill_packages_the_frozen_workload_with_no_core_edits` | `()` | — | — |
