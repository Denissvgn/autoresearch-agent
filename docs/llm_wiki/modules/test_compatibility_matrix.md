# test_compatibility_matrix Module

**Path:** `tests/test_compatibility_matrix.py`

## Description

G5 compatibility matrix: structure and honesty guards.

The ten scenarios are predeclared against the 18 lifecycle cells; live
cells without credentials stay INCOMPLETE (fixtures never substitute);
unsupported backends never pass; failed live cells are never
reclassified; the gate is COMPLETE only when all 18 cells pass.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `importlib.util` | `importlib.util` |
| `pathlib` | `Path` |
| `sys` | `sys` |
| `types` | `ModuleType` |
| `typing` | `cast` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_fake_runner` | `(ok = True, summary = '10 passed in 1.0s')` | — | — |
| `test_predeclared_scenarios_are_complete` | `()` | — | — |
| `test_matrix_has_all_18_cells_with_unique_ids` | `()` | — | — |
| `test_fixtures_never_replace_a_named_live_cell` | `()` | — | — |
| `test_failed_live_cell_is_never_reclassified` | `()` | — | — |
| `test_unsupported_backend_never_passes` | `()` | — | — |
| `test_gate_complete_requires_all_18_pass` | `()` | — | — |
| `test_independent_inspection_covers_each_surface` | `()` | — | — |
| `test_cross_path_surfaces_recorded_with_postgres_status` | `()` | — | — |
