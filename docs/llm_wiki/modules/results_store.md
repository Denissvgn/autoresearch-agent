# results_store Module

**Path:** `src/core/results_store.py`

## Description

SQLite-backed persistence for research sessions, iterations, and promotions.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `aiosqlite` | `aiosqlite` |
| `asyncio` | `asyncio` |
| `collections` | `Counter`, `defaultdict` |
| `contextlib` | `asynccontextmanager` |
| `datetime` | `datetime`, `timezone` |
| `hashlib` | `hashlib` |
| `json` | `json` |
| `logging` | `logging` |
| `os` | `os` |
| `src.core.observability` | `OBSERVABILITY_SCHEMA_VERSION`, `alert_suggestions`, `log_research_event` |
| `typing` | `Any`, `AsyncIterator`, `Dict`, `List`, `Optional`, `Sequence` |
| `uuid` | `uuid` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ResultsStore](../entities/ResultsStore.md) | 527 | — | Async SQLite store for experiment data. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_json_object` | `(raw: Any) -> Dict[str, Any]` | — | — |
| `_json_list` | `(raw: Any) -> List[Any]` | — | — |
| `_truthy_status` | `(payload: Dict[str, Any]) -> bool` | — | — |
| `_attempt_outcome` | `(row: Dict[str, Any], metrics: Dict[str, Any]) -> str` | — | — |
| `_replay_status` | `(metrics: Dict[str, Any]) -> str` | — | — |
| `_reason_slug` | `(value: Any) -> str` | — | — |
| `_counter_rows` | `(counter: Counter[tuple[Any, Ellipsis]], keys: tuple[str, Ellipsis]) -> List[Dict[str, Any]]` | — | — |
| `_value_rows` | `(values: Dict[str, float], key: str) -> List[Dict[str, Any]]` | — | — |
| `_add_column_if_missing` | `*(async)* (db: aiosqlite.Connection, table: str, column_def: str) -> None` | — | Idempotent ``ALTER TABLE ADD COLUMN`` migration. |
| `_get_schema_version` | `*(async)* (db: aiosqlite.Connection) -> int` | — | — |
| `_set_schema_version` | `*(async)* (db: aiosqlite.Connection, version: int) -> None` | — | — |
| `_migrate_to_v1` | `*(async)* (db: aiosqlite.Connection) -> None` | — | Reconcile the current pre-versioned SQLite schema. |
| `_migrate_to_v2` | `*(async)* (db: aiosqlite.Connection) -> None` | — | Add API idempotency records and audit query covering indexes. |
