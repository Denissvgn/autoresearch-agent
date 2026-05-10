# conftest Module

**Path:** `tests/conftest.py`

## Description

_Auto-generated from `tests/conftest.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `os` | `os` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.core.results_store` | `ResultsStore` |
| `sys` | `sys` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `close_initialized_results_stores` | `*(async)* (monkeypatch: pytest.MonkeyPatch)` | `@pytest.fixture(autouse=True)` | Close long-lived SQLite connections created by tests. |
