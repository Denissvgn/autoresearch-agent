# test_results_store_manifest_snapshots Module

**Path:** `tests/test_results_store_manifest_snapshots.py`

## Description

_Auto-generated from `tests/test_results_store_manifest_snapshots.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `os` | `os` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.api.results` | `_enrich_iteration` |
| `src.core.consistency_validator` | `build_consistency_report` |
| `src.core.iteration_snapshot` | `build_trial_identity`, `trial_identity_hash` |
| `src.core.research_phase_plan` | `phase_state_json` |
| `src.core.results_store` | `ResultsStore` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/api/results.py"]
    n1["src/core/consistency_validator.py"]
    n2["src/core/iteration_snapshot.py"]
    n3["src/core/research_phase_plan.py"]
    n4["src/core/results_store.py"]
    n5["tests/test_results_store_manifest_snapshots.py"]
    n0 --> n1
    n3 --> n1
    n5 --> n0
    n5 --> n1
    n5 --> n2
    n5 --> n3
    n5 --> n4
    click n0 "../modules/results.md"
    click n1 "../modules/consistency_validator.md"
    click n2 "../modules/iteration_snapshot.md"
    click n3 "../modules/research_phase_plan.md"
    click n4 "../modules/results_store.md"
    click n5 "../modules/test_results_store_manifest_snapshots.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [results](../modules/results.md) |
| Outbound | [consistency_validator](../modules/consistency_validator.md) |
| Outbound | [iteration_snapshot](../modules/iteration_snapshot.md) |
| Outbound | [research_phase_plan](../modules/research_phase_plan.md) |
| Outbound | [results_store](../modules/results_store.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `test_results_store_persists_manifest_and_attempt_snapshot` | *(async)* `(tmp_path: Path)` | `@pytest.mark.asyncio` | — |
| `test_results_store_finds_duplicate_trial_identity_by_scope` | *(async)* `(tmp_path: Path)` | `@pytest.mark.asyncio` | — |
| `test_results_store_records_audit_events` | *(async)* `(tmp_path: Path)` | `@pytest.mark.asyncio` | — |
