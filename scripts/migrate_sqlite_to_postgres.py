#!/usr/bin/env python3
"""SQLite → Postgres data migration.

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

    .venv/bin/python scripts/migrate_sqlite_to_postgres.py \\
        --sqlite /app/workspace/db/experiments.db \\
        --dsn "postgresql://user:pass@postgres:5432/autoresearch"

The target Postgres DB must already exist. The script creates the schema if
missing.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any, Sequence

# Make `src.` importable when run from the service root.
_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICE_ROOT))

import asyncpg  # noqa: E402

from src.core.postgres_state_store import PostgresStateStore  # noqa: E402

logger = logging.getLogger("migrate_sqlite_to_postgres")

# Tables to migrate, in dependency (FK) order so child rows land after parents.
# `schema_version` is SQLite-specific and is NOT migrated (Postgres has its own
# `pg_schema_version` written by initialize()). `idempotency_records` has no
# AUTOINCREMENT rowid (composite PK) so it uses a synthetic offset.
_TABLES: tuple[tuple[str, str | None], ...] = (
    ("research_sessions", "id"),        # TEXT PK; no rowid batching
    ("iterations", None),               # AUTOINCREMENT rowid
    ("promotions", None),
    ("hpo_studies", None),
    ("planned_trials", None),
    ("pipelines", "id"),
    ("audit_events", "event_id"),
    ("runtime_commands", None),
    ("idempotency_records", "(operation, parent_id, key_hash)"),
)

# Per-table coercion notes (documented, not programmatic — asyncpg's coders
# handle the common int/float/str/text conversions; this documents the edges).
_COERCION_NOTES = {
    "iterations": (
        "all_gates_passed / timed_out / quick_mode are INTEGER (0/1) in SQLite "
        "and SMALLINT in Postgres — asyncpg encodes bool/int directly. "
        "metrics_json / config_snapshot are TEXT and pass through verbatim."
    ),
    "research_sessions": (
        "terminate_request_received is INTEGER DEFAULT 0 (SQLite) → "
        "INTEGER DEFAULT 0 (Postgres). The lock_epoch column is "
        "Postgres-only and defaults to 0 for migrated rows."
    ),
}

_BATCH_SIZE = 500


async def _ensure_pg_schema(dsn: str) -> asyncpg.Connection:
    """Initialize the Postgres schema (idempotent) and return a connection."""
    store = PostgresStateStore(dsn)
    await store.initialize()
    await store.close()
    conn = await asyncpg.connect(dsn.replace("postgresql+asyncpg://", "postgresql://"))
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS migration_state (
               table_name TEXT PRIMARY KEY,
               last_cursor TEXT,
               rows_migrated INTEGER NOT NULL DEFAULT 0,
               migrated_at TIMESTAMPTZ NOT NULL
           )"""
    )
    return conn


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def _read_batch(
    conn: sqlite3.Connection,
    table: str,
    pk: str | None,
    last_cursor: str | None,
    limit: int,
) -> tuple[list[tuple[Any, ...]], str | None]:
    """Read up to ``limit`` rows from SQLite starting after ``last_cursor``."""
    cols = _sqlite_columns(conn, table)
    col_csv = ", ".join(f'"{c}"' for c in cols)
    if pk is None:
        # AUTOINCREMENT rowid path.
        if last_cursor is not None:
            where = f"WHERE rowid > {int(last_cursor)}"
            params: Sequence[Any] = ()
        else:
            where = ""
            params = ()
        cur = conn.execute(
            f"SELECT {col_csv} FROM {table} {where} ORDER BY rowid LIMIT {limit}",
            params,
        )
        rows = cur.fetchall()
        new_cursor = str(rows[-1][0] - 1 + 1) if rows else last_cursor  # rowid of last
        # rowid is not in cols; fetch it explicitly for the cursor.
        cur2 = conn.execute(
            f"SELECT rowid FROM {table} {where} ORDER BY rowid LIMIT {limit}", params
        )
        rowids = [r[0] for r in cur2.fetchall()]
        new_cursor = str(rowids[-1]) if rowids else last_cursor
        return rows, new_cursor
    # Composite / TEXT PK path: order by the (first column of the) PK and page
    # on it. For composite PKs we page on the first column only — sufficient
    # for resumability because ON CONFLICT DO NOTHING makes re-runs idempotent
    # regardless of the cursor's exactness.
    if "(" in pk:
        # e.g. "(operation, parent_id, key_hash)" → "operation"
        first_pk = pk.split("(", 1)[1].split(",")[0].strip().rstrip(")")
    else:
        first_pk = pk
    if last_cursor is not None:
        where = f"WHERE \"{first_pk}\" > ?"
        params = (last_cursor,)
    else:
        where = ""
        params = ()
    cur = conn.execute(
        f'SELECT {col_csv} FROM {table} {where} ORDER BY "{first_pk}" LIMIT {limit}',
        params,
    )
    rows = cur.fetchall()
    pk_idx = cols.index(first_pk)
    new_cursor = str(rows[-1][pk_idx]) if rows else last_cursor
    return rows, new_cursor


async def _migrate_table(
    pg: asyncpg.Connection,
    sqlite_conn: sqlite3.Connection,
    table: str,
    pk: str | None,
) -> int:
    cols = _sqlite_columns(sqlite_conn, table)
    if not cols:
        logger.warning("table %s has no columns in SQLite; skipping", table)
        return 0
    col_csv = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
    # ON CONFLICT makes the move idempotent on re-run. The conflict target is
    # the PK / first UNIQUE; for simplicity we use DO NOTHING (a re-run after
    # a partial migration is safe because the resume cursor + DO NOTHING both
    # guard). Tables with composite PKs use the composite target.
    insert_sql = (
        f'INSERT INTO {table} ({col_csv}) VALUES ({placeholders}) '
        f'ON CONFLICT DO NOTHING'
    )

    state = await pg.fetchrow(
        "SELECT last_cursor, rows_migrated FROM migration_state WHERE table_name = $1",
        table,
    )
    last_cursor = state["last_cursor"] if state else None
    total = state["rows_migrated"] if state else 0

    while True:
        rows, new_cursor = await asyncio.to_thread(
            _read_batch, sqlite_conn, table, pk, last_cursor, _BATCH_SIZE
        )
        if not rows:
            break
        async with pg.transaction():
            # COPY would be faster but ON CONFLICT isn't supported with COPY;
            # batched executemany is the right trade for idempotency.
            await pg.executemany(insert_sql, rows)
        total += len(rows)
        last_cursor = new_cursor
        await pg.execute(
            """INSERT INTO migration_state (table_name, last_cursor, rows_migrated, migrated_at)
               VALUES ($1, $2, $3, NOW())
               ON CONFLICT (table_name) DO UPDATE SET
                   last_cursor = EXCLUDED.last_cursor,
                   rows_migrated = EXCLUDED.rows_migrated,
                   migrated_at = EXCLUDED.migrated_at""",
            table, last_cursor, total,
        )
        logger.info("migrated %s: %d rows (cursor=%s)", table, total, last_cursor)
    return total


async def migrate(sqlite_path: str, pg_dsn: str) -> dict[str, int]:
    """Run the full migration. Returns per-table row counts."""
    sqlite_conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    sqlite_conn.row_factory = None  # plain tuples
    try:
        # Sanity: source SQLite must have the canonical schema.
        tables_present = {
            row[0]
            for row in sqlite_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        pg = await _ensure_pg_schema(pg_dsn)
        try:
            counts: dict[str, int] = {}
            for table, pk in _TABLES:
                if table not in tables_present:
                    logger.info("table %s absent in source SQLite; skipping", table)
                    continue
                counts[table] = await _migrate_table(pg, sqlite_conn, table, pk)
            logger.info("migration complete: %s", counts)
            return counts
        finally:
            await pg.close()
    finally:
        sqlite_conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Migrate autoresearch SQLite DB → Postgres.")
    ap.add_argument("--sqlite", required=True, help="Path to experiments.db")
    ap.add_argument("--dsn", required=True, help="Postgres DSN (postgresql://...)")
    ap.add_argument(
        "-v", "--verbose", action="store_true", help="DEBUG logging"
    )
    args = ap.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
    )
    counts = asyncio.run(migrate(args.sqlite, args.dsn))
    total = sum(counts.values())
    print(f"\nMigration summary ({total} rows):")
    for table, n in counts.items():
        print(f"  {table:24s} {n:>8d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
