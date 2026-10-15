# _engine Module

**Path:** `tests/parity/_engine.py`

## Description

ARC-011 X-002 parity engine.

Shared by ``tests/parity/test_parity.py`` (verify) and
``tests/parity/capture.py`` (record) so the two paths invoke the target
functions with identical logic. The engine:

  1. materializes a per-case workspace (token substitution + file creation),
  2. dispatches to the real source function named by the fixture's
     ``function`` field,
  3. converts the result to a plain dict, and
  4. normalizes volatile fields (paths → tokens, hashes/timestamps redacted)
     so golden ``expected`` blocks are stable across machines and runs.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `asyncio` | `asyncio` |
| `dataclasses` | `dataclasses` |
| `json` | `json` |
| `os` | `os` |
| `pathlib` | `Path` |
| `re` | `re` |
| `src` | `config` |
| `src.core.command_policy` | `evaluate_command_policy` |
| `src.core.config_promoter` | `ConfigPromoter` |
| `src.core.experiment_parser` | `parse_prepare_output`, `parse_iteration_marker` |
| `src.core.orchestrator` | `ResearchConfig` |
| `src.core.research_phase_plan` | `build_phase_state` |
| `src.core.results_store` | `ResultsStore` |
| `sys` | `sys` |
| `typing` | `Any` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/config.py"]
    n1["src/core/command_policy.py"]
    n2["src/core/config_promoter.py"]
    n3["src/core/experiment_parser.py"]
    n4["src/core/orchestrator.py"]
    n5["src/core/research_phase_plan.py"]
    n6["src/core/results_store.py"]
    n7["tests/parity/_engine.py"]
    n2 --> n0
    n2 --> n5
    n4 --> n0
    n4 --> n3
    n4 --> n5
    n7 --> n0
    n7 --> n1
    n7 --> n2
    n7 --> n3
    n7 --> n4
    n7 --> n5
    n7 --> n6
    click n0 "../modules/config.md"
    click n1 "../modules/command_policy.md"
    click n2 "../modules/config_promoter.md"
    click n3 "../modules/experiment_parser.md"
    click n4 "../modules/orchestrator.md"
    click n5 "../modules/research_phase_plan.md"
    click n6 "../modules/results_store.md"
    click n7 "../modules/_engine.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [config](../modules/config.md) |
| Outbound | [command_policy](../modules/command_policy.md) |
| Outbound | [config_promoter](../modules/config_promoter.md) |
| Outbound | [experiment_parser](../modules/experiment_parser.md) |
| Outbound | [orchestrator](../modules/orchestrator.md) |
| Outbound | [research_phase_plan](../modules/research_phase_plan.md) |
| Outbound | [results_store](../modules/results_store.md) |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `discover_cases` | `(base: Path) -> list[tuple[str, Path]]` | — | Return ``[(case_id, path), ...]`` for every ``*.json`` under ``base``. |
| `load_case` | `(path: Path) -> dict[str, Any]` | — | — |
| `_substitute` | `(obj: Any, mapping: dict[str, str]) -> Any` | — | Replace token strings with real paths (input direction). |
| `_detokenize` | `(obj: Any, mapping: dict[str, str]) -> Any` | — | Replace real paths with tokens (output direction, for stable expected). |
| `_redact` | `(obj: Any) -> Any` | — | Redact values of volatile keys (hashes, timestamps, run ids) and drop |
| `normalize` | `(obj: Any, mapping: dict[str, str]) -> Any` | — | Full output normalization: detokenize then redact. |
| `materialize_files` | `(workspace: Path, create_files: dict[str, str] \| None) -> None` | — | — |
| `invoke` | `(case: dict[str, Any], workspace: Path, host_configs: Path, tmp_path: Path) -> Any` | — | Materialize inputs, call the target function, return its raw (dict) result. |
| `_build_store` | *(async)* `(fixture_name: str, db_path: Path)` | — | Replicate tests/conftest.py replay_iterations seeding, standalone. |
| `_invoke_preview` | *(async)* `(case: dict, workspace: Path, host_configs: Path, tmp_path: Path)` | — | — |
