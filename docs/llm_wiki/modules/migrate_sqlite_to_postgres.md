# migrate_sqlite_to_postgres Module

**Path:** `scripts/migrate_sqlite_to_postgres.py`

## Description

SQLite → Postgres data migration.

Idempotent, re-runnable mover for an existing ``experiments.db`` SQLite file
into a Postgres database that ``PostgresStateStore`` will manage. The target
DB's canonical schema (``_SCHEMA_SQL_PG``) is created by
``PostgresStateStore.initialize()``; this script only moves ROWS.

Design notes:

* **Batched:** each table is read in ``rowid``-ordered batches from SQLite and
  batch-INSERTed into Postgres within a per-table transaction.
* **Resumable:** a ``migration_state`` table on the Postgres target records the
  last-migrated ``rowid`` per table; re-running picks up where it left off.
* **Idempotent:** rows already present are skipped (the resume cursor + UNIQUE
  constraints make a re-run a no-op on already-moved data).
* **Type coercion:** SQLite is loosely typed; Postgres is strict. The
  ``_COERCION_NOTES`` map documents the per-table coercions. NULL vs empty-
  string distinctions are preserved as-is (SQLite NULL → Postgres NULL,
  SQLite '' → Postgres '').

Usage::

    .venv/bin/python scripts/migrate_sqlite_to_postgres.py \
        --sqlite /app/workspace/db/experiments.db \
        --dsn "postgresql://user:pass@postgres:5432/autoresearch"

The target Postgres DB must already exist. The script creates the schema if
missing.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `argparse` | `argparse` |
| `asyncio` | `asyncio` |
| `asyncpg` | `asyncpg` |
| `logging` | `logging` |
| `pathlib` | `Path` |
| `sqlite3` | `sqlite3` |
| `src.core.postgres_state_store` | `PostgresStateStore` |
| `sys` | `sys` |
| `typing` | `Any`, `Sequence` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["scripts/migrate_sqlite_to_postgres.py"]
    n1["src/core/postgres_state_store.py"]
    n0 --> n1
    click n0 "../modules/migrate_sqlite_to_postgres.md"
    click n1 "../modules/postgres_state_store.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [postgres_state_store](../modules/postgres_state_store.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 0 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_ensure_pg_schema` | *(async)* `(dsn: str) -> asyncpg.Connection` | — | Initialize the Postgres schema (idempotent) and return a connection. |
| `_sqlite_columns` | `(conn: sqlite3.Connection, table: str) -> list[str]` | — | — |
| `_read_batch` | `(conn: sqlite3.Connection, table: str, pk: str \| None, last_cursor: str \| None, limit: int) -> tuple[list[tuple[Any, ...]], str \| None]` | — | Read up to ``limit`` rows from SQLite starting after ``last_cursor``. |
| `_migrate_table` | *(async)* `(pg: asyncpg.Connection, sqlite_conn: sqlite3.Connection, table: str, pk: str \| None) -> int` | — | — |
| `migrate` | *(async)* `(sqlite_path: str, pg_dsn: str) -> dict[str, int]` | — | Run the full migration. Returns per-table row counts. |
| `main` | `() -> int` | — | — |
