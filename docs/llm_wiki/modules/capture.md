# capture Module

**Path:** `tests/parity/capture.py`

## Description

ARC-011 X-002 parity fixture capture.

Regenerates the ``expected`` block of every parity case by invoking the real
source functions against the current code, then writes the normalized result
plus the originating git SHA back into each fixture JSON.

Run from the service root:

    python tests/parity/capture.py            # refuses on a dirty tree
    python tests/parity/capture.py --force    # allow dirty (e.g. while iterating)

Re-running against the same commit is idempotent (``expected`` and ``source_sha``
are unchanged). When a refactor intentionally changes behavior, re-run this
script on a clean tree at the new HEAD and commit the diff with the linked task.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `_engine` | `HOST_CONFIGS_TOKEN`, `WORKSPACE_TOKEN`, `discover_cases`, `invoke`, `load_case`, `normalize` |
| `argparse` | `argparse` |
| `json` | `json` |
| `pathlib` | `Path` |
| `subprocess` | `subprocess` |
| `sys` | `sys` |
| `tempfile` | `tempfile` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_git` | `(args: list[str]) -> str` | — | — |
| `main` | `() -> int` | — | — |
