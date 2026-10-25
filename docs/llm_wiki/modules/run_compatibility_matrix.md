# run_compatibility_matrix Module

**Path:** `scripts/run_compatibility_matrix.py`

## Description

Run the full initial compatibility matrix (G5) on an exact commit.

18 required lifecycle cells: three harnesses (built-in, Codex, Claude
Code) x three domains (real-prompt, code-test, latency) x two qualified
backends (SQLite, same-host Postgres workers). The ten cross-path
scenarios are predeclared against cells before execution; required live
cells cannot be reclassified after failure, and passing simulations or
fixture-only adapters never replace a named live cell. Cells without
live credentials or a reachable backend are recorded INCOMPLETE — the
gate is left incomplete, never passed by substitution.

Usage:
    python scripts/run_compatibility_matrix.py [--out PATH]

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `argparse` | `argparse` |
| `ci_qualification_gates` | `collect_current_inputs` |
| `dataclasses` | `dataclass`, `field` |
| `json` | `json` |
| `os` | `os` |
| `pathlib` | `Path` |
| `subprocess` | `subprocess` |
| `sys` | `sys` |
| `time` | `time` |
| `typing` | `Any`, `Optional`, `Sequence` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [Cell](../entities/Cell.md) | 199 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `postgres_available` | `() -> bool` | — | — |
| `run_suite` | `(suites: Sequence[str], timeout_s: int = 600) -> tuple[bool, str]` | — | — |
| `execute_cell` | `(cell: Cell, *, live_credentials: bool, postgres: bool, runner = run_suite) -> Cell` | — | One lifecycle cell. Required live cells are never reclassified. |
| `asdict_cell` | `(cell: Cell) -> dict[str, Any]` | — | — |
| `build_matrix` | `(*, live_credentials: bool, postgres: bool, runner = run_suite, commit: str = '') -> dict[str, Any]` | — | — |
| `main` | `(argv: Optional[Sequence[str]] = None) -> int` | — | — |
