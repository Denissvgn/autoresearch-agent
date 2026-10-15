# FakeStore

**Location:** `tests/test_research_api_compat.py:73`
**Kind:** Class
**Bases:** —
**Module:** [test_research_api_compat](../modules/test_research_api_compat.md)

## Description

_Auto-generated from `FakeStore` in `tests/test_research_api_compat.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `() -> None` | — | — |
| `ping` | *(async)* `() -> bool` | — | — |
| `record_audit_event` | *(async)* `(**kwargs: Any) -> None` | — | — |
| `get_session` | *(async)* `(research_id: str) -> Dict[str, Any] \| None` | — | — |
| `list_sessions` | *(async)* `(*, status: str \| None = None, model_type: str \| None = None, instrument: str \| None = None, limit: int \| None = None, offset: int = 0, cursor: tuple \| None = None) -> list[Dict[str, Any]]` | — | — |
| `count_sessions` | *(async)* `(*, status: str \| None = None, model_type: str \| None = None, instrument: str \| None = None) -> int` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["FakeStore (tests/test_research_api_compat.py)"]
    n1["configure (tests/test_research_api_compat.py)"]
    n2["create_test_app (tests/test_research_api_compat.py)"]
    n1 --> n0
    n2 --> n0
    click n0 "../modules/test_research_api_compat.md"
    click n1 "../modules/test_research_api_compat.md"
    click n2 "../modules/test_research_api_compat.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_research_api_compat](../modules/test_research_api_compat.md) | 6 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `configure` | call | [test_research_api_compat](../modules/test_research_api_compat.md) | 1 |
| `create_test_app` | call | [test_research_api_compat](../modules/test_research_api_compat.md) | 1 |
