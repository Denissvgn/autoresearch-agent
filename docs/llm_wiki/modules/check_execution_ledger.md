# check_execution_ledger Module

**Path:** `scripts/check_execution_ledger.py`

## Description

Execution-ledger validator: fail closed on inconsistent task state.

Validates the private execution ledger set (cards, run, gates, prerequisites,
decisions) that a long-running implementation effort keeps to make progress
durable and auditable. Checks card-ID well-formedness, dependency resolution
and acyclicity, state/transition legality, acceptance-to-check references, and
closure-evidence completeness for completed records.

Card IDs are treated as opaque strings validated against the ledger's own
registry plus a generic pattern; no planning vocabulary is hard-coded here.
Run at every state change and on resume.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `argparse` | `argparse` |
| `json` | `json` |
| `pathlib` | `Path` |
| `re` | `re` |
| `sys` | `sys` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [LedgerError](../entities/LedgerError.md) | 50 | `Exception` | Raised for structural problems that make the ledger uninterpretable. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_load_json` | `(path: Path) -> dict` | — | — |
| `_load_jsonl` | `(path: Path) -> list[dict]` | — | — |
| `validate_cards` | `(cards_doc: dict, errors: list[str]) -> set[str]` | — | Validate the card registry; returns the set of known card IDs. |
| `_validate_acceptance` | `(rec: dict, errors: list[str]) -> None` | — | — |
| `validate_dependencies` | `(cards_doc: dict, known: set[str], errors: list[str]) -> None` | — | Dependency references must resolve and the graph must be acyclic. |
| `validate_closure` | `(cards_doc: dict, errors: list[str]) -> None` | — | A DONE record requires complete, passing, current closure evidence. |
| `validate_side_files` | `(ledger_dir: Path, known: set[str], errors: list[str]) -> None` | — | run/gates/prerequisites/decisions must parse and cross-reference cleanly. |
| `validate_ledger` | `(ledger_dir: Path) -> list[str]` | — | Run every check; return the list of errors found (empty = valid). |
| `main` | `() -> int` | — | — |
