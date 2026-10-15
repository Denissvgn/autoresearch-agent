# test_parity Module

**Path:** `tests/parity/test_parity.py`

## Description

ARC-011 X-002 parity suite.

Discovers every ``*.json`` under ``tests/parity/<category>/`` and asserts that
invoking the named source function reproduces the recorded ``expected`` output
(after normalization). Selectable via ``pytest -m parity``.

Run:  poetry run pytest tests/parity -q      # or  pytest -m parity

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `_engine` | `HOST_CONFIGS_TOKEN`, `WORKSPACE_TOKEN`, `discover_cases`, `invoke`, `load_case`, `normalize` |
| `json` | `json` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 2 | 2 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `test_parity_fixture` | `(case_id: str, case_path: Path, tmp_path: Path) -> None` | `@pytest.mark.parity`, `@pytest.mark.parametrize('case_id, case_path', CASES, ids=[cid for cid, _ in CASES])` | — |
