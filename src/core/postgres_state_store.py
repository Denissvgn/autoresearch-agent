"""``PostgresStateStore`` — the multi-worker Postgres backend (ARC-011 P6-002).

A 1:1 translation of :class:`SQLiteStateStore` to raw asyncpg, satisfying the
same 48-method :class:`StateStore` protocol. The port is **mechanical** at the
SQL level (``?`` → ``$N``, ``AUTOINCREMENT`` → ``BIGSERIAL``, ``INSERT OR
REPLACE`` → ``ON CONFLICT … DO UPDATE``) so the X-002 parity suite and the
dual-backend sweep (P6-002b) verify behavior is byte-identical.

Design input: ``docs/adr/ARC-011-postgres-state-store.md`` (P6-001). Key points:

* **Raw asyncpg, not SQLAlchemy** (D-driver): mirrors SQLiteStateStore's
  hand-written-SQL shape for parity; ``pg_advisory_xact_lock`` is first-class.
* **Connection sharing via ContextVar** (D-connection-sharing): the 48 protocol
  methods keep their signatures. A :class:`contextvars.ContextVar` carries the
  in-flight transaction's connection; the additive ``session_lock`` method
  acquires a pooled connection, begins a transaction, takes the advisory lock,
  and publishes its connection via the ContextVar. Each method joins the
  in-flight txn if one is held, else grabs its own short-lived connection.
* **No ``self._write_lock``**: Postgres MVCC + atomic ``ON CONFLICT`` make the
  in-process asyncio.Lock unnecessary. ``SQLiteStateStore`` keeps it.
* **Fencing support** (D-fencing, feeds P6-004): the schema adds
  ``research_sessions.lock_epoch``; the four post-command write methods accept
  an optional ``lock_epoch`` precondition so a stale worker's late write is
  discarded (0 rows). When the precondition is omitted the write is
  unconditional — matching SQLite semantics and keeping the parity suite green.

Single-host, N-worker, one shared DB (D-scope-single-host). Same-session
concurrency is serialized by the advisory lock (held via ``session_lock``);
cross-session concurrency relies on MVCC.
"""

from __future__ import annotations

import contextvars
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

import asyncpg

from src.core.artifact_reference import normalize_optional_artifact_ref
from src.core.gate_status import consistency_report_passed
from src.core.observability import log_research_event
from src.core.pagination import clamp_limit

logger = logging.getLogger("src.core.results_store")

_MODEL_TO_SKILL = {
    "direction": "direction-autotuner",
    "volatility": "volatility-autotuner",
    "rl": "rl-autotuner",
}

# Canonical Postgres DDL — one consolidated schema (current latest shape), no
# v1..v6 incrementals. SQLite's migration steps existed only because SQLite has
# no real migration framework; a fresh Postgres DB never needs them
# (D-migration, ARC-011-postgres-state-store.md §2). ``pg_schema_version`` keeps
# the same forward-compat gate the protocol requires (``get_schema_version``).
_SCHEMA_SQL_PG = """
CREATE TABLE IF NOT EXISTS pg_schema_version (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS research_sessions (
    id TEXT PRIMARY KEY,
    instrument TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    model_type TEXT NOT NULL,
    tag TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    quick_mode SMALLINT DEFAULT 0,
    max_iterations INTEGER DEFAULT 15,
    max_budget_usd DOUBLE PRECISION DEFAULT 10.0,
    focus_hint TEXT,
    workspace_path TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    total_api_cost_usd DOUBLE PRECISION DEFAULT 0.0,
    best_iteration INTEGER,
    best_metric DOUBLE PRECISION,
    error_message TEXT,
    -- v1 (research_session_columns): ML-60/62/63 + DPU-081 + DPU-084/087
    insights TEXT,
    resumed_from TEXT,
    pipeline_id TEXT,
    manifest_json TEXT,
    manifest_path TEXT,
    manifest_hash TEXT,
    current_phase TEXT,
    next_action TEXT,
    phase_state_json TEXT,
    -- v3: F9 structured terminal reason
    terminal_reason TEXT,
    -- v4: promotion waiver + effective-iteration counter
    terminate_request_received SMALLINT DEFAULT 0,
    terminate_request_body TEXT,
    effective_iteration_count INTEGER DEFAULT 0,
    -- v6: P3-019 native canonical skill columns (NOT NULL DEFAULT '' matches SQLite)
    skill_id TEXT NOT NULL DEFAULT '',
    subject_id TEXT NOT NULL DEFAULT '',
    variant TEXT NOT NULL DEFAULT '',
    -- Phase 6 (P6-002a): fencing-token epoch (D-fencing)
    lock_epoch BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS iterations (
    id BIGSERIAL PRIMARY KEY,
    research_id TEXT NOT NULL REFERENCES research_sessions(id),
    iteration INTEGER NOT NULL,
    primary_metric DOUBLE PRECISION,
    metric_name TEXT,
    all_gates_passed SMALLINT,
    decision TEXT,
    description TEXT,
    config_snapshot TEXT,
    canonical_config_hash TEXT,
    trial_identity_hash TEXT,
    trial_identity_json TEXT,
    duplicate_of_research_id TEXT,
    duplicate_of_iteration INTEGER,
    duplicate_reason TEXT,
    metrics_json TEXT,
    attempt_snapshot_json TEXT,
    attempt_snapshot_path TEXT,
    attempt_snapshot_hash TEXT,
    consistency_report_json TEXT,
    training_time_s DOUBLE PRECISION,
    api_cost_usd DOUBLE PRECISION DEFAULT 0.0,
    created_at TEXT NOT NULL,
    mlflow_run_id TEXT,
    search_phase TEXT,
    hpo_study_id INTEGER,
    UNIQUE(research_id, iteration)
);

CREATE TABLE IF NOT EXISTS promotions (
    id BIGSERIAL PRIMARY KEY,
    research_id TEXT NOT NULL REFERENCES research_sessions(id),
    iteration INTEGER NOT NULL,
    model_type TEXT NOT NULL,
    instrument TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    target_path TEXT NOT NULL,
    config_yaml TEXT NOT NULL,
    previous_yaml TEXT,
    scope TEXT NOT NULL DEFAULT 'development',
    metadata_path TEXT,
    promotion_metadata_json TEXT,
    rollback_metadata_path TEXT,
    rollback_metadata_json TEXT,
    rolled_back_at TEXT,
    promoted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hpo_studies (
    id BIGSERIAL PRIMARY KEY,
    research_id TEXT NOT NULL REFERENCES research_sessions(id),
    iteration INTEGER NOT NULL,
    study_id TEXT,
    n_trials INTEGER NOT NULL DEFAULT 0,
    max_trials INTEGER,
    completed_trials INTEGER NOT NULL DEFAULT 0,
    best_composite DOUBLE PRECISION,
    training_time_s DOUBLE PRECISION,
    top_trials_json TEXT,
    search_space_json TEXT,
    budget_json TEXT,
    timeout_s INTEGER,
    quick_mode SMALLINT DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS planned_trials (
    id BIGSERIAL PRIMARY KEY,
    research_id TEXT NOT NULL REFERENCES research_sessions(id),
    study_id TEXT,
    trial_id TEXT NOT NULL,
    trial_index INTEGER NOT NULL,
    search_phase TEXT NOT NULL,
    config_patch_json TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    canonical_config_hash TEXT,
    trial_identity_hash TEXT,
    trial_identity_json TEXT,
    expected_command TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    result_path TEXT,
    mlflow_run_id TEXT,
    train_config_path TEXT,
    manual_review_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(research_id, trial_id)
);

CREATE TABLE IF NOT EXISTS pipelines (
    id TEXT PRIMARY KEY,
    instrument TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    tag TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    current_phase TEXT,
    completed_phases TEXT DEFAULT '[]',
    direction_session_id TEXT,
    volatility_session_id TEXT,
    rl_session_id TEXT,
    max_iterations INTEGER DEFAULT 30,
    max_budget_usd DOUBLE PRECISION DEFAULT 30.0,
    total_api_cost_usd DOUBLE PRECISION DEFAULT 0.0,
    phase_budgets TEXT,
    quick_mode SMALLINT DEFAULT 0,
    timeout_s INTEGER DEFAULT 0,
    focus_hint TEXT,
    trading_mode TEXT,
    agent_strategy TEXT,
    initial_balance DOUBLE PRECISION,
    enable_hpo SMALLINT DEFAULT 0,
    hpo_trials INTEGER,
    hpo_timesteps INTEGER,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT,
    promotion_blocked_phase TEXT,
    promotion_blockers_json TEXT,
    promotion_preview_json TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    research_id TEXT,
    pipeline_id TEXT,
    request_metadata_json TEXT NOT NULL DEFAULT '{}',
    outcome TEXT NOT NULL,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS runtime_commands (
    id BIGSERIAL PRIMARY KEY,
    research_id TEXT NOT NULL REFERENCES research_sessions(id),
    turn INTEGER,
    tool_name TEXT NOT NULL,
    command TEXT,
    normalized_command TEXT,
    policy_operation TEXT,
    timeout_s INTEGER,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    returncode INTEGER,
    timed_out SMALLINT DEFAULT 0,
    output_preview TEXT,
    error_message TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    operation TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    child_id TEXT,
    response_json TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    PRIMARY KEY (operation, parent_id, key_hash)
);
"""

_INDEXES_SQL_PG = """
CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_events_action ON audit_events(action);
CREATE INDEX IF NOT EXISTS idx_audit_events_research_id ON audit_events(research_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor_timestamp
    ON audit_events(actor_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_research_timestamp
    ON audit_events(research_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_pipeline_id ON audit_events(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_planned_trials_research_id ON planned_trials(research_id);
CREATE INDEX IF NOT EXISTS idx_planned_trials_expected_command
    ON planned_trials(research_id, expected_command);
CREATE INDEX IF NOT EXISTS idx_runtime_commands_research_status
    ON runtime_commands(research_id, status);
-- Keyset indexes mirror the SQLite v5 declarations (DESC) so the
-- ORDER BY started_at DESC, id DESC list queries are served by a forward
-- index scan on both backends.
CREATE INDEX IF NOT EXISTS idx_sessions_started_at_rowid
    ON research_sessions(started_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_pipelines_started_at_rowid
    ON pipelines(started_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_iterations_research_iteration
    ON iterations(research_id, iteration);
CREATE INDEX IF NOT EXISTS idx_iterations_trial_identity_hash
    ON iterations(trial_identity_hash);
CREATE INDEX IF NOT EXISTS idx_planned_trials_trial_identity_hash
    ON planned_trials(trial_identity_hash);
"""

_PG_SCHEMA_VERSION = 1


def _json_object(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _truthy(value: Any) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "items"):
        return dict(row)
    return dict(row)


class PostgresStateStore:
    """Multi-worker Postgres implementation of :class:`StateStore`.

    Owns the canonical Postgres DDL (``_SCHEMA_SQL_PG``) and the connection
    pool. The 48 protocol methods mirror :class:`SQLiteStateStore` 1:1; the
    concurrency substrate is what differs — a pool of connections coordinated
    by transaction-scoped advisory locks (via :meth:`session_lock`) and atomic
    ``ON CONFLICT`` upserts, instead of SQLite's single-writer serialization.

    See ``docs/adr/ARC-011-postgres-state-store.md`` (P6-001) for the lock /
    fencing / connection-sharing design consumed here.
    """

    def __init__(self, dsn: str, *, min_size: int = 2, max_size: int = 10) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: Optional[asyncpg.Pool] = None
        # Carries the in-flight advisory-locked transaction's connection so
        # the protocol methods (which take no ``conn`` arg) can join it.
        # asyncio guarantees ContextVars are task-local, so concurrent tasks
        # on the same worker do not collide (D-connection-sharing).
        self._txn_conn: contextvars.ContextVar[Optional[asyncpg.Connection]] = (
            contextvars.ContextVar("_pg_txn_conn", default=None)
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._pool is not None:
            await self.close()
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            command_timeout=30,
        )
        if self._pool is None:  # pragma: no cover - defensive
            raise RuntimeError("asyncpg.create_pool returned None")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(_SCHEMA_SQL_PG)
                await conn.execute(_INDEXES_SQL_PG)
                # Upsert the schema-version row (idempotent on re-init).
                await conn.execute(
                    """INSERT INTO pg_schema_version (id, version, applied_at)
                       VALUES (1, $1, NOW())
                       ON CONFLICT (id) DO UPDATE SET version = EXCLUDED.version,
                           applied_at = EXCLUDED.applied_at""",
                    _PG_SCHEMA_VERSION,
                )
        logger.info("PostgresStateStore initialized (schema v%d)", _PG_SCHEMA_VERSION)

    async def close(self) -> None:
        if self._pool is None:
            return
        pool = self._pool
        self._pool = None
        await pool.close()

    async def ping(self) -> bool:
        try:
            conn = await self._conn()
            try:
                val = await conn.fetchval("SELECT 1")
                return val == 1
            finally:
                await self._release_short_lived(conn)
        except asyncpg.PostgresError:
            logger.exception("PostgresStateStore ping failed")
            return False

    async def get_schema_version(self) -> int:
        conn = await self._conn()
        try:
            version = await conn.fetchval(
                "SELECT version FROM pg_schema_version WHERE id = 1"
            )
            return int(version) if version is not None else 0
        finally:
            await self._release_short_lived(conn)

    # ------------------------------------------------------------------
    # Connection resolution + session_lock (D-connection-sharing)
    # ------------------------------------------------------------------

    async def _conn(self) -> asyncpg.Connection:
        """Return the connection to use for this call.

        If a :meth:`session_lock` block is in flight on this task, its
        advisory-locked transactional connection is reused (so the call joins
        the held transaction). Otherwise a fresh short-lived connection is
        acquired from the pool and the caller is responsible for releasing it
        via :meth:`_release_short_lived`.
        """
        existing = self._txn_conn.get()
        if existing is not None:
            return existing
        if self._pool is None:
            raise RuntimeError("PostgresStateStore is not initialized")
        return await self._pool.acquire()

    async def _release_short_lived(self, conn: asyncpg.Connection) -> None:
        """Release a connection acquired outside a session_lock block."""
        if self._txn_conn.get() is conn:
            # Belongs to the in-flight transaction; do not release.
            return
        if self._pool is None:
            return
        await self._pool.release(conn)

    @asynccontextmanager
    async def session_lock(self, session_id: str) -> AsyncIterator[None]:
        """Hold an exclusive cross-process lock on the session.

        SQLiteStateStore: no-op (its in-process ``SessionLockRegistry`` already
        serializes the transition critical section). PostgresStateStore: acquire
        a pooled connection, BEGIN, ``pg_advisory_xact_lock(hashtext($1))``,
        publish the conn via the ContextVar, yield, COMMIT/release.

        Re-entrant within one task: if a ``session_lock`` is already held, the
        inner call joins the outer transaction (the outer holder remains the
        lock owner). Transaction-scoped advisory locks auto-release on
        COMMIT/ROLLBACK, so a crash mid-transition cannot orphan a lock
        (R-advisory-lock-leak).
        """
        if self._txn_conn.get() is not None:
            yield
            return
        if self._pool is None:
            raise RuntimeError("PostgresStateStore is not initialized")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1))", session_id
                )
                token = self._txn_conn.set(conn)
                try:
                    yield
                finally:
                    self._txn_conn.reset(token)

    async def bump_session_epoch(self, session_id: str) -> None:
        """Increment ``research_sessions.lock_epoch`` (ARC-011 P6-003 / D-fencing).

        Called by ``SessionStateMachine._apply`` after a committed transition,
        inside the held ``session_lock`` (so the bump itself is serialized).
        Any command dispatched before the transition is thereby deauthorized —
        its captured epoch no longer matches, so the conditional state-advancing
        writes (``add_iteration`` / ``update_session`` with ``lock_epoch=``)
        return 0 rows and the orchestrator discards the stale result (the H4 fix).

        ``finish_runtime_command`` is intentionally NOT fenced: it writes only
        to the ``runtime_commands`` observability table (keyed by command_id,
        no lock_epoch column, drives no session state). ``update_planned_trial_status``
        accepts ``lock_epoch`` for completeness but is not on the orchestrator's
        hot post-command path today.
        """
        conn = await self._conn()
        try:
            await conn.execute(
                "UPDATE research_sessions SET lock_epoch = lock_epoch + 1 "
                "WHERE id = $1",
                session_id,
            )
        finally:
            await self._release_short_lived(conn)

    # ------------------------------------------------------------------
    # Idempotency records — atomic ON CONFLICT (P6-003 / H1)
    # ------------------------------------------------------------------

    async def begin_idempotency_record(
        self,
        *,
        operation: str,
        parent_id: str,
        key_hash: str,
        request_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """Reserve an idempotency key or return the existing record.

        Atomic ``INSERT … ON CONFLICT DO NOTHING RETURNING`` replaces the
        SQLite SELECT-then-INSERT-under-asyncio.Lock pattern — under
        WEB_CONCURRENCY>1 two workers can race the SELECT and both INSERT; the
        unique constraint makes exactly one win. ``RETURNING`` non-empty ⇒ we
        won the reservation (first-time, return None so the caller proceeds);
        empty ⇒ a record already exists (replay, return it).
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = await self._conn()
        try:
            inserted = await conn.fetchrow(
                """INSERT INTO idempotency_records
                   (operation, parent_id, key_hash, request_hash, status, created_at)
                   VALUES ($1, $2, $3, $4, 'running', $5)
                   ON CONFLICT (operation, parent_id, key_hash) DO NOTHING
                   RETURNING *""",
                operation, parent_id, key_hash, request_hash, now,
            )
            if inserted is not None:
                return None  # we won the reservation
            # A record already exists — replay it.
            existing = await conn.fetchrow(
                """SELECT * FROM idempotency_records
                   WHERE operation = $1 AND parent_id = $2 AND key_hash = $3""",
                operation, parent_id, key_hash,
            )
            return _row_to_dict(existing) if existing else None
        finally:
            await self._release_short_lived(conn)

    async def complete_idempotency_record(
        self,
        *,
        operation: str,
        parent_id: str,
        key_hash: str,
        child_id: Optional[str],
        response: Dict[str, Any],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        response_json = json.dumps(response, sort_keys=True, default=str)
        conn = await self._conn()
        try:
            await conn.execute(
                """UPDATE idempotency_records
                   SET status = 'completed',
                       child_id = $4,
                       response_json = $5,
                       completed_at = $6
                   WHERE operation = $1 AND parent_id = $2 AND key_hash = $3""",
                operation, parent_id, key_hash, child_id, response_json, now,
            )
        finally:
            await self._release_short_lived(conn)

    async def delete_idempotency_record(
        self,
        *,
        operation: str,
        parent_id: str,
        key_hash: str,
    ) -> None:
        conn = await self._conn()
        try:
            await conn.execute(
                """DELETE FROM idempotency_records
                   WHERE operation = $1 AND parent_id = $2 AND key_hash = $3""",
                operation, parent_id, key_hash,
            )
        finally:
            await self._release_short_lived(conn)

    # ------------------------------------------------------------------
    # Audit events
    # ------------------------------------------------------------------

    async def record_audit_event(
        self,
        *,
        actor_id: str,
        action: str,
        outcome: str,
        research_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        request_metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        event_id = f"aud_{uuid.uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata = request_metadata or {}
        metadata_json = json.dumps(metadata, sort_keys=True)
        conn = await self._conn()
        try:
            await conn.execute(
                """INSERT INTO audit_events
                   (event_id, timestamp, actor_id, action, research_id,
                    pipeline_id, request_metadata_json, outcome, error_message)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                event_id, timestamp, actor_id, action, research_id,
                pipeline_id, metadata_json, outcome, error_message,
            )
        finally:
            await self._release_short_lived(conn)
        log_research_event(
            logger,
            "audit.recorded",
            research_id=research_id,
            pipeline_id=pipeline_id,
            phase=metadata.get("phase"),
            trial_id=metadata.get("trial_id"),
            promotion_id=metadata.get("promotion_id"),
            audit_event_id=event_id,
            actor_id=actor_id,
            action=action,
            outcome=outcome,
        )
        return {
            "event_id": event_id,
            "timestamp": timestamp,
            "actor_id": actor_id,
            "action": action,
            "research_id": research_id,
            "pipeline_id": pipeline_id,
            "request_metadata": metadata,
            "outcome": outcome,
            "error_message": error_message,
        }

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        session_id: str,
        instrument: str,
        timeframe: str,
        model_type: str,
        tag: str,
        quick_mode: bool,
        max_iterations: int,
        max_budget_usd: float,
        focus_hint: Optional[str],
        workspace_path: str,
        manifest_json: Optional[str] = None,
        manifest_path: Optional[str] = None,
        manifest_hash: Optional[str] = None,
        skill_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        variant: Optional[str] = None,
    ) -> Dict[str, Any]:
        # ARC-011 review C4 (P4-016): canonical non-ML sessions carry
        # model_type="" (no legacy alias) — previously a KeyError; unmapped
        # types pass their own name through (SQLite-parity fix).
        # ARC-012 P7-005: skill_id, when given, is the skill_name source of
        # truth and the canonical columns are persisted natively.
        skill_name = (
            skill_id
            or _MODEL_TO_SKILL.get(model_type, model_type or "")
        )
        now = datetime.now(timezone.utc).isoformat()
        conn = await self._conn()
        try:
            await conn.execute(
                """INSERT INTO research_sessions
                   (id, instrument, timeframe, model_type, tag, skill_name,
                    skill_id, subject_id, variant,
                    status, quick_mode, max_iterations, max_budget_usd,
                    focus_hint, workspace_path, manifest_json, manifest_path,
                    manifest_hash, started_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'running',
                           $10, $11, $12, $13, $14, $15, $16, $17, $18)""",
                session_id, instrument, timeframe, model_type, tag, skill_name,
                skill_id or "", subject_id or "", variant or "",
                int(quick_mode), max_iterations, max_budget_usd, focus_hint,
                workspace_path, manifest_json, manifest_path, manifest_hash, now,
            )
        finally:
            await self._release_short_lived(conn)
        log_research_event(
            logger,
            "research_session.created",
            research_id=session_id,
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
            status="running",
        )
        row = await self.get_session(session_id)
        assert row is not None  # just inserted
        return row

    async def update_session(
        self,
        session_id: str,
        *,
        lock_epoch: Optional[int] = None,
        **fields: Any,
    ) -> Optional[Dict[str, Any]]:
        """Update session fields.

        ``lock_epoch`` (P6-004 fence): when provided, the UPDATE is conditional
        on the current ``lock_epoch`` matching — 0 rows ⇒ the session was
        deauthorized while a command ran (stopped/timed-out on another worker).
        Callers should treat a ``None`` return + a non-empty ``fields`` as a
        stale-write discard and emit ``result.discarded.stale_worker`` audit.
        When omitted, the write is unconditional (SQLite parity).
        """
        if not fields:
            return await self.get_session(session_id)
        set_clause = ", ".join(f"{k} = ${i}" for i, k in enumerate(fields, start=1))
        values: list[Any] = list(fields.values())
        where = "id = $" + str(len(values) + 1)
        if lock_epoch is not None:
            where += " AND lock_epoch = $" + str(len(values) + 2)
            values.append(session_id)
            values.append(lock_epoch)
        else:
            values.append(session_id)
        conn = await self._conn()
        try:
            result = await conn.execute(
                f"UPDATE research_sessions SET {set_clause} WHERE {where}",
                *values,
            )
            affected = _parse_rowcount(result)
        finally:
            await self._release_short_lived(conn)
        if lock_epoch is not None and affected == 0:
            # Stale write — the session's epoch moved on under another worker.
            return None
        if any(key in fields for key in ("status", "current_phase", "next_action")):
            log_research_event(
                logger,
                "research_session.updated",
                research_id=session_id,
                phase=fields.get("current_phase"),
                status=fields.get("status"),
                next_action=fields.get("next_action"),
            )
        return await self.get_session(session_id)

    async def delete_session(self, session_id: str) -> bool:
        # Postgres FK ON DELETE is not CASCADE here, so delete children first
        # (mirrors SQLiteStateStore). Order matches the research_id FK graph.
        conn = await self._conn()
        try:
            async with conn.transaction():
                for child in (
                    "runtime_commands",
                    "iterations",
                    "planned_trials",
                    "promotions",
                    "hpo_studies",
                ):
                    await conn.execute(
                        f"DELETE FROM {child} WHERE research_id = $1", session_id,
                    )
                result = await conn.execute(
                    "DELETE FROM research_sessions WHERE id = $1", session_id,
                )
            return _parse_rowcount(result) > 0
        finally:
            await self._release_short_lived(conn)

    # ------------------------------------------------------------------
    # Runtime commands
    # ------------------------------------------------------------------

    async def record_runtime_command(
        self,
        *,
        research_id: str,
        turn: Optional[int],
        tool_name: str,
        command: Optional[str] = None,
        normalized_command: Optional[str] = None,
        policy_operation: Optional[str] = None,
        timeout_s: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = (
            json.dumps(metadata, sort_keys=True) if metadata is not None else None
        )
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                """INSERT INTO runtime_commands
                   (research_id, turn, tool_name, command, normalized_command,
                    policy_operation, timeout_s, status, started_at, metadata_json)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, 'running', $8, $9)
                   RETURNING id""",
                research_id, turn, tool_name, command, normalized_command,
                policy_operation, timeout_s, now, metadata_json,
            )
            command_id = row["id"] if row else None
        finally:
            await self._release_short_lived(conn)
        log_research_event(
            logger,
            "runtime_command.started",
            research_id=research_id,
            turn=turn,
            tool_name=tool_name,
            policy_operation=policy_operation,
            runtime_command_id=command_id,
        )
        return {
            "id": command_id,
            "research_id": research_id,
            "turn": turn,
            "tool_name": tool_name,
            "command": command,
            "normalized_command": normalized_command,
            "policy_operation": policy_operation,
            "timeout_s": timeout_s,
            "status": "running",
            "started_at": now,
            "metadata": metadata,
        }

    async def finish_runtime_command(
        self,
        command_id: int,
        *,
        status: str,
        returncode: Optional[int] = None,
        timed_out: bool = False,
        output_preview: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = (
            json.dumps(metadata, sort_keys=True) if metadata is not None else None
        )
        conn = await self._conn()
        try:
            await conn.execute(
                """UPDATE runtime_commands
                   SET status = $1,
                       completed_at = $2,
                       returncode = $3,
                       timed_out = $4,
                       output_preview = $5,
                       error_message = $6,
                       metadata_json = COALESCE($7, metadata_json)
                   WHERE id = $8""",
                status, now, returncode, int(timed_out), output_preview,
                error_message, metadata_json, command_id,
            )
        finally:
            await self._release_short_lived(conn)
        rows = await self.list_runtime_commands(command_id=command_id)
        row = rows[0] if rows else {}
        metadata_payload = row.get("metadata") or metadata or {}
        log_research_event(
            logger,
            "runtime_command.finished",
            research_id=row.get("research_id") or metadata_payload.get("research_id"),
            phase=metadata_payload.get("phase"),
            trial_id=metadata_payload.get("trial_id"),
            runtime_command_id=command_id,
            status=status,
            returncode=returncode,
            timed_out=timed_out,
            policy_operation=metadata_payload.get("policy_operation"),
        )
        return rows[0] if rows else None

    async def interrupt_runtime_commands(
        self,
        *,
        research_id: str,
        reason: str,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        conn = await self._conn()
        try:
            result = await conn.execute(
                """UPDATE runtime_commands
                   SET status = 'interrupted',
                       completed_at = $1,
                       error_message = $2
                   WHERE research_id = $3 AND status = 'running'""",
                now, reason, research_id,
            )
            return _parse_rowcount(result)
        finally:
            await self._release_short_lived(conn)

    # ------------------------------------------------------------------
    # Iterations
    # ------------------------------------------------------------------

    async def add_iteration(
        self,
        *,
        research_id: str,
        iteration: int,
        primary_metric: Optional[float],
        metric_name: Optional[str],
        all_gates_passed: Optional[bool],
        decision: Optional[str],
        description: Optional[str],
        config_snapshot: Optional[str],
        metrics_json: Optional[str],
        training_time_s: Optional[float],
        api_cost_usd: float = 0.0,
        mlflow_run_id: Optional[str] = None,
        canonical_config_hash: Optional[str] = None,
        trial_identity_hash: Optional[str] = None,
        trial_identity_json: Optional[str] = None,
        duplicate_of_research_id: Optional[str] = None,
        duplicate_of_iteration: Optional[int] = None,
        duplicate_reason: Optional[str] = None,
        attempt_snapshot_json: Optional[str] = None,
        attempt_snapshot_path: Optional[str] = None,
        attempt_snapshot_hash: Optional[str] = None,
        consistency_report_json: Optional[str] = None,
        search_phase: Optional[str] = None,
        metric_improvement_epsilon: float = 0.0,
        lock_epoch: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record an iteration. ``metrics_json``/``all_gates_passed`` are
        normalized exactly as in SQLiteStateStore (see
        :func:`_normalized_iteration_metrics_json`-equivalent logic lives in
        the shared module — re-imported here for parity).

        ``lock_epoch`` (P6-004): when provided, the follow-on ``best_*`` update
        is conditional on the epoch; a stale worker's iteration row is still
        inserted (it's an immutable record of what the command produced) but
        the session's ``best_iteration``/``best_metric`` do not advance.
        """
        # Defer the metrics-normalization to the shared helper so behavior is
        # byte-identical to SQLiteStateStore (avoids a parity drift).
        from src.core.state_store import _normalized_iteration_metrics_json

        metrics_json, all_gates_passed = _normalized_iteration_metrics_json(
            metrics_json=metrics_json,
            all_gates_passed=all_gates_passed,
            consistency_report_json=consistency_report_json,
            context=f"{research_id} iteration {iteration}",
        )
        mlflow_run_id = normalize_optional_artifact_ref(mlflow_run_id)
        now = datetime.now(timezone.utc).isoformat()
        conn = await self._conn()
        try:
            await conn.execute(
                """INSERT INTO iterations
                   (research_id, iteration, primary_metric, metric_name,
                    all_gates_passed, decision, description, config_snapshot,
                    canonical_config_hash, trial_identity_hash,
                    trial_identity_json, duplicate_of_research_id,
                    duplicate_of_iteration, duplicate_reason, metrics_json,
                    attempt_snapshot_json, attempt_snapshot_path,
                    attempt_snapshot_hash, consistency_report_json,
                    training_time_s, api_cost_usd, created_at, mlflow_run_id,
                    search_phase)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                           $13, $14, $15, $16, $17, $18, $19, $20, $21, $22,
                           $23, $24)""",
                research_id, iteration, primary_metric, metric_name,
                int(all_gates_passed) if all_gates_passed is not None else None,
                decision, description, config_snapshot, canonical_config_hash,
                trial_identity_hash, trial_identity_json, duplicate_of_research_id,
                duplicate_of_iteration, duplicate_reason, metrics_json,
                attempt_snapshot_json, attempt_snapshot_path,
                attempt_snapshot_hash, consistency_report_json,
                training_time_s, api_cost_usd, now, mlflow_run_id, search_phase,
            )

            # Best-metric advancement mirrors SQLiteStateStore; the epoch fence
            # (when supplied) prevents a stale worker from advancing the bar.
            if decision == "keep":
                best_row = await conn.fetchrow(
                    "SELECT best_metric FROM research_sessions WHERE id = $1",
                    research_id,
                )
                best_metric = best_row["best_metric"] if best_row else None
                if primary_metric is not None and (
                    best_metric is None
                    or primary_metric > best_metric + metric_improvement_epsilon
                ):
                    set_sql = (
                        "best_iteration = $1, best_metric = $2 WHERE id = $3"
                    )
                    args: list[Any] = [iteration, primary_metric, research_id]
                    if lock_epoch is not None:
                        set_sql += " AND lock_epoch = $4"
                        args.append(lock_epoch)
                    await conn.execute(
                        f"UPDATE research_sessions SET {set_sql}", *args
                    )
        finally:
            await self._release_short_lived(conn)

        from src.core.state_store import _attempt_outcome, _json_object

        metrics_payload = _json_object(metrics_json)
        trial_identity = _json_object(trial_identity_json)
        log_research_event(
            logger,
            "iteration.recorded",
            research_id=research_id,
            phase=metrics_payload.get("search_phase"),
            trial_id=(
                metrics_payload.get("trial_id")
                or metrics_payload.get("planned_trial_id")
                or trial_identity.get("trial_id")
            ),
            iteration=iteration,
            outcome=_attempt_outcome(
                {
                    "decision": decision,
                    "primary_metric": primary_metric,
                    "all_gates_passed": all_gates_passed,
                    "duplicate_reason": duplicate_reason,
                },
                metrics_payload,
            ),
            decision=decision,
            metric_name=metric_name,
            primary_metric=primary_metric,
        )
        return {
            "research_id": research_id,
            "iteration": iteration,
            "primary_metric": primary_metric,
            "metric_name": metric_name,
            "all_gates_passed": all_gates_passed,
            "decision": decision,
            "description": description,
            "canonical_config_hash": canonical_config_hash,
            "trial_identity_hash": trial_identity_hash,
            "trial_identity_json": trial_identity_json,
            "duplicate_of_research_id": duplicate_of_research_id,
            "duplicate_of_iteration": duplicate_of_iteration,
            "duplicate_reason": duplicate_reason,
            "attempt_snapshot_path": attempt_snapshot_path,
            "attempt_snapshot_hash": attempt_snapshot_hash,
            "consistency_report_json": consistency_report_json,
            "created_at": now,
        }

    async def update_iteration(
        self,
        research_id: str,
        iteration: int,
        marker: Dict[str, Any],
    ) -> None:
        fields: Dict[str, Any] = {}
        for key in (
            "primary_metric", "metric_name", "decision", "description",
            "training_time_s", "canonical_config_hash",
        ):
            if key in marker:
                fields[key] = marker[key]
        if "all_gates_passed" in marker:
            value = marker["all_gates_passed"]
            fields["all_gates_passed"] = (
                int(value) if isinstance(value, bool) else value
            )
        if "api_cost_usd" in marker:
            fields["api_cost_usd"] = marker["api_cost_usd"]
        if "duplicate_of_research_id" in marker:
            fields["duplicate_of_research_id"] = marker["duplicate_of_research_id"]
        if "duplicate_of_iteration" in marker:
            fields["duplicate_of_iteration"] = marker["duplicate_of_iteration"]
        if "duplicate_reason" in marker:
            fields["duplicate_reason"] = marker["duplicate_reason"]
        if "training_time_s" in marker:
            fields["training_time_s"] = marker["training_time_s"]
        if "attempt_snapshot" in marker:
            fields["attempt_snapshot_json"] = json.dumps(
                marker["attempt_snapshot"], sort_keys=True,
            )
        if "attempt_snapshot_path" in marker:
            fields["attempt_snapshot_path"] = marker["attempt_snapshot_path"]
        if "attempt_snapshot_hash" in marker:
            fields["attempt_snapshot_hash"] = marker["attempt_snapshot_hash"]
        if "mlflow_run_id" in marker:
            fields["mlflow_run_id"] = normalize_optional_artifact_ref(
                marker["mlflow_run_id"]
            )
        if "consistency_report" in marker:
            fields["consistency_report_json"] = json.dumps(
                marker["consistency_report"], sort_keys=True,
            )
            report_passed = consistency_report_passed(marker["consistency_report"])
            if report_passed is not None:
                marker["consistency_report_passed"] = report_passed
        if "consistency_report_json" in marker:
            fields["consistency_report_json"] = marker["consistency_report_json"]
            report_passed = consistency_report_passed(marker["consistency_report_json"])
            if report_passed is not None:
                marker["consistency_report_passed"] = report_passed
        if "search_phase" in marker:
            fields["search_phase"] = marker["search_phase"]
        if marker:
            fields["metrics_json"] = json.dumps(marker)

        if not fields:
            return

        set_clause = ", ".join(f"{k} = ${i}" for i, k in enumerate(fields, start=1))
        values: list[Any] = list(fields.values())
        values.extend([research_id, iteration])
        conn = await self._conn()
        try:
            await conn.execute(
                f"UPDATE iterations SET {set_clause} "
                f"WHERE research_id = ${len(values) - 1} "
                f"AND iteration = ${len(values)}",
                *values,
            )
        finally:
            await self._release_short_lived(conn)

    # ------------------------------------------------------------------
    # HPO studies
    # ------------------------------------------------------------------

    async def add_hpo_study(
        self,
        *,
        research_id: str,
        iteration: int,
        n_trials: int,
        completed_trials: int,
        best_composite: Optional[float],
        training_time_s: Optional[float],
        top_trials_json: Optional[str],
        status: str = "completed",
        study_id: Optional[str] = None,
        max_trials: Optional[int] = None,
        search_space_json: Optional[str] = None,
        budget_json: Optional[str] = None,
        timeout_s: Optional[int] = None,
        quick_mode: bool = False,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                """INSERT INTO hpo_studies
                   (research_id, iteration, n_trials, study_id, max_trials,
                    completed_trials, best_composite, training_time_s,
                    top_trials_json, search_space_json, budget_json, timeout_s,
                    quick_mode, status, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                           $13, $14, $15)
                   RETURNING id""",
                research_id, iteration, n_trials, study_id, max_trials,
                completed_trials, best_composite, training_time_s,
                top_trials_json, search_space_json, budget_json, timeout_s,
                int(quick_mode), status, now,
            )
            study_row_id = row["id"] if row else None
        finally:
            await self._release_short_lived(conn)
        return {
            "id": study_row_id,
            "research_id": research_id,
            "iteration": iteration,
            "n_trials": n_trials,
            "study_id": study_id,
            "max_trials": max_trials,
            "completed_trials": completed_trials,
            "best_composite": best_composite,
            "status": status,
            "created_at": now,
        }

    async def record_hpo_study_plan(
        self,
        *,
        research_id: str,
        study_id: str,
        max_trials: int,
        search_space_json: str,
        budget_json: str,
        timeout_s: int,
        quick_mode: bool,
    ) -> Dict[str, Any]:
        return await self.add_hpo_study(
            research_id=research_id,
            iteration=0,
            n_trials=max_trials,
            completed_trials=0,
            best_composite=None,
            training_time_s=None,
            top_trials_json=None,
            status="planned" if max_trials else "disabled",
            study_id=study_id,
            max_trials=max_trials,
            search_space_json=search_space_json,
            budget_json=budget_json,
            timeout_s=timeout_s,
            quick_mode=quick_mode,
        )

    # ------------------------------------------------------------------
    # Planned trials
    # ------------------------------------------------------------------

    async def record_planned_trials(
        self,
        *,
        research_id: str,
        study_id: Optional[str],
        trials: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not trials:
            return []
        now = datetime.now(timezone.utc).isoformat()
        conn = await self._conn()
        try:
            async with conn.transaction():
                for trial in trials:
                    config_patch = trial.get("config_patch") or {}
                    await conn.execute(
                        """INSERT INTO planned_trials
                           (research_id, study_id, trial_id, trial_index,
                            search_phase, config_patch_json, config_hash,
                            canonical_config_hash, trial_identity_hash,
                            trial_identity_json, expected_command, status,
                            result_path, mlflow_run_id, train_config_path,
                            manual_review_reason, created_at, updated_at)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                                   $11, $12, $13, $14, $15, $16, $17, $18)
                           ON CONFLICT (research_id, trial_id) DO UPDATE SET
                               study_id = EXCLUDED.study_id,
                               trial_index = EXCLUDED.trial_index,
                               search_phase = EXCLUDED.search_phase,
                               config_patch_json = EXCLUDED.config_patch_json,
                               config_hash = EXCLUDED.config_hash,
                               canonical_config_hash = EXCLUDED.canonical_config_hash,
                               trial_identity_hash = EXCLUDED.trial_identity_hash,
                               trial_identity_json = EXCLUDED.trial_identity_json,
                               expected_command = EXCLUDED.expected_command,
                               status = EXCLUDED.status,
                               result_path = EXCLUDED.result_path,
                               mlflow_run_id = EXCLUDED.mlflow_run_id,
                               train_config_path = EXCLUDED.train_config_path,
                               manual_review_reason = EXCLUDED.manual_review_reason,
                               updated_at = EXCLUDED.updated_at""",
                        research_id,
                        trial.get("study_id") or study_id,
                        trial["trial_id"],
                        int(trial.get("trial_index") or 0),
                        trial.get("search_phase") or "hpo_screening",
                        json.dumps(config_patch, sort_keys=True),
                        trial["config_hash"],
                        trial.get("canonical_config_hash"),
                        trial.get("trial_identity_hash"),
                        (
                            json.dumps(trial.get("trial_identity"), sort_keys=True)
                            if trial.get("trial_identity") is not None
                            else trial.get("trial_identity_json")
                        ),
                        trial["expected_command"],
                        trial.get("status") or "planned",
                        trial.get("result_path"),
                        normalize_optional_artifact_ref(trial.get("mlflow_run_id")),
                        trial.get("train_config_path"),
                        trial.get("manual_review_reason"),
                        now,
                        now,
                    )
        finally:
            await self._release_short_lived(conn)
        phases = sorted(
            {str(trial.get("search_phase") or "hpo_screening") for trial in trials}
        )
        log_research_event(
            logger,
            "planned_trials.recorded",
            research_id=research_id,
            phase=",".join(phases) if phases else None,
            study_id=study_id,
            planned_trial_count=len(trials),
        )
        return await self.get_planned_trials(research_id)

    async def record_planned_trial_manual_review(
        self,
        *,
        research_id: str,
        study_id: Optional[str],
        expected_command: str,
        reason: str,
        search_phase: str = "manual_review",
        config_patch: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        import hashlib

        now = datetime.now(timezone.utc).isoformat()
        payload = config_patch or {"proposed_command": expected_command}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        config_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        trial_id = f"manual_review_{uuid.uuid4().hex[:12]}"
        conn = await self._conn()
        try:
            await conn.execute(
                """INSERT INTO planned_trials
                   (research_id, study_id, trial_id, trial_index, search_phase,
                    config_patch_json, config_hash, canonical_config_hash,
                    trial_identity_hash, trial_identity_json, expected_command,
                    status, result_path, mlflow_run_id, train_config_path,
                    manual_review_reason, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                           $13, $14, $15, $16, $17, $18)""",
                research_id, study_id, trial_id, -1, search_phase,
                json.dumps(payload, sort_keys=True), config_hash,
                None, None, None, expected_command, "manual_review",
                None, None, None, reason, now, now,
            )
        finally:
            await self._release_short_lived(conn)
        log_research_event(
            logger,
            "planned_trial.manual_review",
            research_id=research_id,
            phase=search_phase,
            trial_id=trial_id,
            study_id=study_id,
            status="manual_review",
        )
        row = await self.get_planned_trial(research_id, trial_id)
        return row or {
            "research_id": research_id,
            "study_id": study_id,
            "trial_id": trial_id,
            "status": "manual_review",
            "manual_review_reason": reason,
        }

    async def update_planned_trial_status(
        self,
        *,
        research_id: str,
        trial_id: str,
        status: str,
        result_path: Optional[str] = None,
        mlflow_run_id: Optional[str] = None,
        manual_review_reason: Optional[str] = None,
        train_config_path: Optional[str] = None,
        canonical_config_hash: Optional[str] = None,
        trial_identity_hash: Optional[str] = None,
        trial_identity: Optional[Dict[str, Any]] = None,
        trial_identity_json: Optional[str] = None,
        lock_epoch: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        fields: Dict[str, Any] = {"status": status, "updated_at": now}
        if result_path is not None:
            fields["result_path"] = result_path
        if mlflow_run_id is not None:
            fields["mlflow_run_id"] = normalize_optional_artifact_ref(mlflow_run_id)
        if manual_review_reason is not None:
            fields["manual_review_reason"] = manual_review_reason
        if train_config_path is not None:
            fields["train_config_path"] = train_config_path
        if canonical_config_hash is not None:
            fields["canonical_config_hash"] = canonical_config_hash
        if trial_identity_hash is not None:
            fields["trial_identity_hash"] = trial_identity_hash
        if trial_identity is not None:
            fields["trial_identity_json"] = json.dumps(trial_identity, sort_keys=True)
        elif trial_identity_json is not None:
            fields["trial_identity_json"] = trial_identity_json
        set_clause = ", ".join(f"{key} = ${i}" for i, key in enumerate(fields, start=1))
        values: list[Any] = list(fields.values())
        where = "research_id = $" + str(len(values) + 1)
        values.append(research_id)
        where += " AND trial_id = $" + str(len(values) + 1)
        values.append(trial_id)
        if lock_epoch is not None:
            # Fence via the session's epoch (join through research_sessions).
            where += (
                " AND (SELECT lock_epoch FROM research_sessions "
                "WHERE id = $" + str(len(values) + 1) + ") = $" + str(len(values) + 2)
            )
            values.extend([research_id, lock_epoch])
        conn = await self._conn()
        try:
            await conn.execute(
                f"UPDATE planned_trials SET {set_clause} WHERE {where}", *values
            )
        finally:
            await self._release_short_lived(conn)
        row = await self.get_planned_trial(research_id, trial_id)
        log_research_event(
            logger,
            "planned_trial.updated",
            research_id=research_id,
            phase=(row or {}).get("search_phase"),
            trial_id=trial_id,
            status=status,
        )
        return row

    # ------------------------------------------------------------------
    # Promotions
    # ------------------------------------------------------------------

    async def record_promotion(
        self,
        *,
        research_id: str,
        iteration: int,
        model_type: str,
        instrument: str,
        timeframe: str,
        target_path: str,
        config_yaml: str,
        previous_yaml: Optional[str],
        scope: str = "development",
        metadata_path: Optional[str] = None,
        promotion_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = (
            json.dumps(promotion_metadata, sort_keys=True)
            if promotion_metadata is not None
            else None
        )
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                """INSERT INTO promotions
                   (research_id, iteration, model_type, instrument, timeframe,
                    target_path, config_yaml, previous_yaml, scope, metadata_path,
                    promotion_metadata_json, promoted_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                   RETURNING id""",
                research_id, iteration, model_type, instrument, timeframe,
                target_path, config_yaml, previous_yaml, scope, metadata_path,
                metadata_json, now,
            )
            promotion_id = row["id"] if row else None
        finally:
            await self._release_short_lived(conn)
        log_research_event(
            logger,
            "promotion.recorded",
            research_id=research_id,
            promotion_id=promotion_id,
            iteration=iteration,
            scope=scope,
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
        )
        return {
            "id": promotion_id,
            "research_id": research_id,
            "iteration": iteration,
            "target_path": target_path,
            "scope": scope,
            "metadata_path": metadata_path,
            "promotion_metadata": promotion_metadata,
            "promoted_at": now,
        }

    async def record_promotion_rollback(
        self,
        *,
        promotion_id: int,
        rollback_metadata_path: str,
        rollback_metadata: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        rollback_metadata_json = json.dumps(rollback_metadata, sort_keys=True)
        conn = await self._conn()
        try:
            await conn.execute(
                """UPDATE promotions
                   SET rollback_metadata_path = $1,
                       rollback_metadata_json = $2,
                       rolled_back_at = $3
                   WHERE id = $4""",
                rollback_metadata_path, rollback_metadata_json, now, promotion_id,
            )
            row = await conn.fetchrow(
                "SELECT * FROM promotions WHERE id = $1", promotion_id,
            )
        finally:
            await self._release_short_lived(conn)
        if not row:
            return None
        result = _row_to_dict(row)
        self._decode_promotion_metadata(result)
        return result

    # ------------------------------------------------------------------
    # Pipelines
    # ------------------------------------------------------------------

    async def create_pipeline(
        self,
        *,
        pipeline_id: str,
        instrument: str,
        timeframe: str,
        tag: str,
        max_iterations: int,
        max_budget_usd: float,
        quick_mode: bool,
        timeout_s: int,
        focus_hint: Optional[str],
        phase_budgets: Optional[str],
        trading_mode: Optional[str],
        agent_strategy: Optional[str],
        initial_balance: Optional[float],
        enable_hpo: bool,
        hpo_trials: Optional[int],
        hpo_timesteps: Optional[int],
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        conn = await self._conn()
        try:
            await conn.execute(
                """INSERT INTO pipelines
                   (id, instrument, timeframe, tag, status, current_phase,
                    completed_phases, max_iterations, max_budget_usd, quick_mode,
                    timeout_s, focus_hint, phase_budgets, trading_mode,
                    agent_strategy, initial_balance, enable_hpo, hpo_trials,
                    hpo_timesteps, started_at)
                   VALUES ($1, $2, $3, $4, 'running', NULL, '[]', $5, $6, $7,
                           $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)""",
                pipeline_id, instrument, timeframe, tag, max_iterations,
                max_budget_usd, int(quick_mode), timeout_s, focus_hint,
                phase_budgets, trading_mode, agent_strategy, initial_balance,
                int(enable_hpo), hpo_trials, hpo_timesteps, now,
            )
        finally:
            await self._release_short_lived(conn)
        log_research_event(
            logger,
            "pipeline.created",
            pipeline_id=pipeline_id,
            instrument=instrument,
            timeframe=timeframe,
            status="running",
        )
        row = await self.get_pipeline(pipeline_id)
        assert row is not None  # just inserted
        return row

    async def update_pipeline(
        self,
        pipeline_id: str,
        **fields: Any,
    ) -> Optional[Dict[str, Any]]:
        if not fields:
            return await self.get_pipeline(pipeline_id)
        set_clause = ", ".join(f"{k} = ${i}" for i, k in enumerate(fields, start=1))
        values: list[Any] = list(fields.values())
        values.append(pipeline_id)
        conn = await self._conn()
        try:
            await conn.execute(
                f"UPDATE pipelines SET {set_clause} WHERE id = ${len(values)}",
                *values,
            )
        finally:
            await self._release_short_lived(conn)
        if any(
            key in fields
            for key in (
                "status",
                "current_phase",
                "promotion_blockers_json",
                "promotion_preview_json",
            )
        ):
            log_research_event(
                logger,
                "pipeline.updated",
                pipeline_id=pipeline_id,
                phase=fields.get("current_phase"),
                status=fields.get("status"),
                blocked=fields.get("promotion_blockers_json") is not None,
            )
        return await self.get_pipeline(pipeline_id)

    # ------------------------------------------------------------------
    # Read methods (P6-002b). 1:1 ports of SQLiteStateStore reads; the
    # dual-backend parity sweep (tests/conftest dual-backend parametrization)
    # is the gate that proves parity.
    # ------------------------------------------------------------------

    async def list_audit_events(
        self,
        *,
        limit: int = 100,
        action: Optional[str] = None,
        research_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if action:
            clauses.append("action = $" + str(len(params) + 1))
            params.append(action)
        if research_id:
            clauses.append("research_id = $" + str(len(params) + 1))
            params.append(research_id)
        if pipeline_id:
            clauses.append("pipeline_id = $" + str(len(params) + 1))
            params.append(pipeline_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(max(1, min(limit, 500)))
        conn = await self._conn()
        try:
            rows = await conn.fetch(
                f"SELECT * FROM audit_events{where} ORDER BY timestamp DESC "
                f"LIMIT ${len(params)}",
                *params,
            )
        finally:
            await self._release_short_lived(conn)
        result = [_row_to_dict(r) for r in rows]
        for row in result:
            raw_metadata = row.pop("request_metadata_json", None)
            try:
                row["request_metadata"] = json.loads(raw_metadata or "{}")
            except (json.JSONDecodeError, TypeError):
                row["request_metadata"] = {}
        return result

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM research_sessions WHERE id = $1", session_id,
            )
        finally:
            await self._release_short_lived(conn)
        return _row_to_dict(row) if row else None

    async def list_sessions(
        self,
        status: Optional[str] = None,
        model_type: Optional[str] = None,
        instrument: Optional[str] = None,
        status_in: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        cursor: Optional[tuple[Any, int]] = None,
        reverse: bool = False,
    ) -> List[Dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = $" + str(len(params) + 1))
            params.append(status)
        if status_in:
            placeholders = ", ".join(
                "$" + str(len(params) + i + 1) for i in range(len(status_in))
            )
            clauses.append(f"status IN ({placeholders})")
            params.extend(status_in)
        if model_type:
            clauses.append("model_type = $" + str(len(params) + 1))
            params.append(model_type)
        if instrument:
            clauses.append("instrument = $" + str(len(params) + 1))
            params.append(instrument)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        select = "SELECT * FROM research_sessions"
        if cursor is not None:
            if reverse:
                clauses.append(
                    f"(started_at, id) > (${len(params) + 1}, ${len(params) + 2})"
                )
                params.extend(cursor)
                order_and_limit = (
                    f" ORDER BY started_at ASC, id ASC LIMIT ${len(params) + 1}"
                )
                params.append(clamp_limit(limit))
                where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            else:
                clauses.append(
                    f"(started_at, id) < (${len(params) + 1}, ${len(params) + 2})"
                )
                params.extend(cursor)
                order_and_limit = (
                    f" ORDER BY started_at DESC, id DESC LIMIT ${len(params) + 1}"
                )
                params.append(clamp_limit(limit))
                where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            sql = f"{select}{where}{order_and_limit}"
        else:
            suffix = ""
            if limit is not None:
                suffix = f" LIMIT {int(limit)} OFFSET {int(offset)}"
            sql = f"{select}{where} ORDER BY started_at DESC, id DESC{suffix}"
        conn = await self._conn()
        try:
            rows = await conn.fetch(sql, *params)
        finally:
            await self._release_short_lived(conn)
        return [_row_to_dict(r) for r in rows]

    async def count_sessions(
        self,
        status: Optional[str] = None,
        model_type: Optional[str] = None,
        instrument: Optional[str] = None,
        status_in: Optional[Sequence[str]] = None,
    ) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = $" + str(len(params) + 1))
            params.append(status)
        if status_in:
            placeholders = ", ".join(
                "$" + str(len(params) + i + 1) for i in range(len(status_in))
            )
            clauses.append(f"status IN ({placeholders})")
            params.extend(status_in)
        if model_type:
            clauses.append("model_type = $" + str(len(params) + 1))
            params.append(model_type)
        if instrument:
            clauses.append("instrument = $" + str(len(params) + 1))
            params.append(instrument)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        conn = await self._conn()
        try:
            val = await conn.fetchval(
                f"SELECT COUNT(*) FROM research_sessions{where}", *params
            )
        finally:
            await self._release_short_lived(conn)
        return int(val) if val is not None else 0

    async def list_runtime_commands(
        self,
        *,
        research_id: Optional[str] = None,
        status: Optional[str] = None,
        command_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if research_id:
            clauses.append("research_id = $" + str(len(params) + 1))
            params.append(research_id)
        if status:
            clauses.append("status = $" + str(len(params) + 1))
            params.append(status)
        if command_id is not None:
            clauses.append("id = $" + str(len(params) + 1))
            params.append(command_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        conn = await self._conn()
        try:
            rows = await conn.fetch(
                f"SELECT * FROM runtime_commands{where} "
                f"ORDER BY started_at DESC, id DESC",
                *params,
            )
        finally:
            await self._release_short_lived(conn)
        result = [_row_to_dict(r) for r in rows]
        for row in result:
            raw = row.pop("metadata_json", None)
            if raw:
                try:
                    row["metadata"] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    row["metadata"] = {}
            else:
                row["metadata"] = {}
        return result

    async def get_iterations(
        self,
        research_id: str,
        limit: Optional[int] = None,
        cursor: Optional[tuple[Any, int]] = None,
        reverse: bool = False,
    ) -> List[Dict[str, Any]]:
        if limit is None:
            conn = await self._conn()
            try:
                rows = await conn.fetch(
                    "SELECT * FROM iterations WHERE research_id = $1 "
                    "ORDER BY iteration ASC, id ASC",
                    research_id,
                )
            finally:
                await self._release_short_lived(conn)
            return [_row_to_dict(r) for r in rows]
        clauses = ["research_id = $1"]
        params: list[Any] = [research_id]
        if cursor is not None:
            if reverse:
                clauses.append("(iteration, id) < ($2, $3)")
                params.extend(cursor)
                order = " ORDER BY iteration DESC, id DESC LIMIT $4"
            else:
                clauses.append("(iteration, id) > ($2, $3)")
                params.extend(cursor)
                order = " ORDER BY iteration ASC, id ASC LIMIT $4"
            params.append(clamp_limit(limit))
        else:
            order = " ORDER BY iteration ASC, id ASC LIMIT $2"
            params.append(clamp_limit(limit))
        where = " AND ".join(clauses)
        conn = await self._conn()
        try:
            rows = await conn.fetch(
                f"SELECT * FROM iterations WHERE {where}{order}", *params
            )
        finally:
            await self._release_short_lived(conn)
        return [_row_to_dict(r) for r in rows]

    async def get_cross_session_iteration_summary(
        self,
        *,
        instrument: str,
        timeframe: str,
        model_type: str,
        exclude_research_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        # Postgres translation of the SQLite GROUP_CONCAT/json_extract query.
        # STRING_AGG(DISTINCT ...) replaces GROUP_CONCAT; metrics_json::jsonb->>
        # replaces json_extract. No NULLIF wrapper: SQLite's GROUP_CONCAT keeps
        # empty-string values (emitting a leading separator), so Postgres must
        # too for parity. NULLs are skipped by both aggregates, so NULL handling
        # stays aligned.
        conn = await self._conn()
        try:
            rows = await conn.fetch(
                """
                SELECT
                  i.canonical_config_hash AS canonical_config_hash,
                  MAX(i.primary_metric) AS best_metric,
                  MIN(i.research_id) AS first_research_id,
                  COUNT(*) AS attempts,
                  STRING_AGG(DISTINCT
                    i.metrics_json::jsonb->>'adaptive_feature_noop_reason', ','
                  ) AS noop_reasons,
                  STRING_AGG(DISTINCT
                    i.metrics_json::jsonb->>'tsfm_adapter', ','
                  ) AS tsfm_adapters,
                  STRING_AGG(DISTINCT
                    i.metrics_json::jsonb->>'tsfm_fallback_validation', ','
                  ) AS tsfm_fallback_flags,
                  STRING_AGG(DISTINCT i.decision, ',') AS decisions,
                  COUNT(DISTINCT i.research_id) AS session_count,
                  MIN(i.config_snapshot) AS sample_config_snapshot
                FROM iterations i
                JOIN research_sessions s ON s.id = i.research_id
                WHERE s.instrument = $1
                  AND s.timeframe = $2
                  AND s.model_type = $3
                  AND i.research_id != COALESCE($4, '')
                  AND i.canonical_config_hash IS NOT NULL
                  AND i.canonical_config_hash != ''
                  AND i.duplicate_reason IS NULL
                GROUP BY i.canonical_config_hash
                ORDER BY best_metric DESC NULLS LAST, attempts DESC
                LIMIT $5
                """,
                instrument, timeframe, model_type, exclude_research_id, limit,
            )
        finally:
            await self._release_short_lived(conn)
        return [_row_to_dict(r) for r in rows]

    async def get_iteration(
        self, research_id: str, iteration: int,
    ) -> Optional[Dict[str, Any]]:
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM iterations WHERE research_id = $1 AND iteration = $2",
                research_id, iteration,
            )
        finally:
            await self._release_short_lived(conn)
        return _row_to_dict(row) if row else None

    async def find_duplicate_trial_identity(
        self,
        *,
        research_id: str,
        trial_identity_hash: str,
        instrument: str,
        timeframe: str,
        model_type: str,
        include_cross_session: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if not trial_identity_hash:
            return None
        if include_cross_session:
            scope_sql = (
                "(i.research_id = $2 OR "
                "(s.instrument = $3 AND s.timeframe = $4 AND s.model_type = $5))"
            )
            params: list[Any] = [
                trial_identity_hash, research_id, instrument, timeframe, model_type,
            ]
        else:
            scope_sql = "i.research_id = $2"
            params = [trial_identity_hash, research_id]
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                f"""SELECT i.*, s.instrument, s.timeframe, s.model_type
                    FROM iterations i
                    JOIN research_sessions s ON s.id = i.research_id
                    WHERE i.trial_identity_hash = $1
                      AND {scope_sql}
                    ORDER BY
                      CASE WHEN i.duplicate_reason IS NULL THEN 0 ELSE 1 END,
                      i.created_at
                    LIMIT 1""",
                *params,
            )
        finally:
            await self._release_short_lived(conn)
        return _row_to_dict(row) if row else None

    async def get_best_iteration(
        self, research_id: str,
    ) -> Optional[Dict[str, Any]]:
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                """SELECT * FROM iterations
                   WHERE research_id = $1 AND all_gates_passed = 1
                     AND primary_metric IS NOT NULL
                   ORDER BY primary_metric DESC LIMIT 1""",
                research_id,
            )
            if row is None:
                # ML-53 legacy fallback.
                row = await conn.fetchrow(
                    """SELECT * FROM iterations
                       WHERE research_id = $1 AND decision IN ('keep', 'improve')
                       ORDER BY primary_metric DESC LIMIT 1""",
                    research_id,
                )
        finally:
            await self._release_short_lived(conn)
        return _row_to_dict(row) if row else None

    async def get_latest_iteration_with_config_snapshot(
        self, research_id: str,
    ) -> Optional[Dict[str, Any]]:
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                "SELECT iteration, config_snapshot FROM iterations "
                "WHERE research_id = $1 AND config_snapshot IS NOT NULL "
                "ORDER BY iteration DESC LIMIT 1",
                research_id,
            )
        finally:
            await self._release_short_lived(conn)
        if not row:
            return None
        return {"iteration": row["iteration"], "config_snapshot": row["config_snapshot"]}

    async def get_first_iteration_with_config_snapshot(
        self, research_id: str,
    ) -> Optional[Dict[str, Any]]:
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                "SELECT iteration, config_snapshot FROM iterations "
                "WHERE research_id = $1 AND config_snapshot IS NOT NULL "
                "ORDER BY iteration ASC LIMIT 1",
                research_id,
            )
        finally:
            await self._release_short_lived(conn)
        if not row:
            return None
        return {"iteration": row["iteration"], "config_snapshot": row["config_snapshot"]}

    async def get_hpo_studies(self, research_id: str) -> List[Dict[str, Any]]:
        conn = await self._conn()
        try:
            rows = await conn.fetch(
                "SELECT * FROM hpo_studies WHERE research_id = $1 ORDER BY created_at",
                research_id,
            )
        finally:
            await self._release_short_lived(conn)
        return [_row_to_dict(r) for r in rows]

    async def get_planned_trials(self, research_id: str) -> List[Dict[str, Any]]:
        conn = await self._conn()
        try:
            rows = await conn.fetch(
                """SELECT * FROM planned_trials
                   WHERE research_id = $1
                   ORDER BY
                     CASE WHEN trial_index < 0 THEN 999999 ELSE trial_index END,
                     created_at""",
                research_id,
            )
        finally:
            await self._release_short_lived(conn)
        result = [_row_to_dict(r) for r in rows]
        for row in result:
            self._decode_planned_trial(row)
        return result

    async def get_planned_trial(
        self, research_id: str, trial_id: str,
    ) -> Optional[Dict[str, Any]]:
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM planned_trials WHERE research_id = $1 AND trial_id = $2",
                research_id, trial_id,
            )
        finally:
            await self._release_short_lived(conn)
        if not row:
            return None
        result = _row_to_dict(row)
        self._decode_planned_trial(result)
        return result

    async def get_planned_trial_for_command(
        self, research_id: str, expected_command: str,
    ) -> Optional[Dict[str, Any]]:
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                """SELECT * FROM planned_trials
                   WHERE research_id = $1
                     AND expected_command = $2
                     AND status != 'manual_review'
                   LIMIT 1""",
                research_id, expected_command,
            )
        finally:
            await self._release_short_lived(conn)
        if not row:
            return None
        result = _row_to_dict(row)
        self._decode_planned_trial(result)
        return result

    async def list_promotions(self) -> List[Dict[str, Any]]:
        conn = await self._conn()
        try:
            rows = await conn.fetch(
                "SELECT * FROM promotions ORDER BY promoted_at DESC"
            )
        finally:
            await self._release_short_lived(conn)
        result = [_row_to_dict(r) for r in rows]
        for row in result:
            self._decode_promotion_metadata(row)
        return result

    async def get_latest_development_promotion(
        self, *, model_type: str, instrument: str, timeframe: str,
    ) -> Optional[Dict[str, Any]]:
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                """SELECT * FROM promotions
                   WHERE model_type = $1 AND instrument = $2 AND timeframe = $3
                     AND scope = 'development'
                   ORDER BY promoted_at DESC LIMIT 1""",
                model_type, instrument, timeframe,
            )
        finally:
            await self._release_short_lived(conn)
        if not row:
            return None
        result = _row_to_dict(row)
        self._decode_promotion_metadata(result)
        return result

    async def get_latest_promotion(
        self, *, model_type: str, instrument: str, timeframe: str, scope: str,
    ) -> Optional[Dict[str, Any]]:
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                """SELECT * FROM promotions
                   WHERE model_type = $1 AND instrument = $2 AND timeframe = $3
                     AND scope = $4
                   ORDER BY promoted_at DESC LIMIT 1""",
                model_type, instrument, timeframe, scope,
            )
        finally:
            await self._release_short_lived(conn)
        if not row:
            return None
        result = _row_to_dict(row)
        self._decode_promotion_metadata(result)
        return result

    async def get_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        conn = await self._conn()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM pipelines WHERE id = $1", pipeline_id,
            )
        finally:
            await self._release_short_lived(conn)
        if not row:
            return None
        result = _row_to_dict(row)
        self._decode_pipeline_metadata(result)
        return result

    async def list_pipelines(
        self,
        status: Optional[str] = None,
        instrument: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        cursor: Optional[tuple[Any, int]] = None,
        reverse: bool = False,
    ) -> List[Dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = $" + str(len(params) + 1))
            params.append(status)
        if instrument:
            clauses.append("instrument = $" + str(len(params) + 1))
            params.append(instrument)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        select = "SELECT * FROM pipelines"
        if cursor is not None:
            if reverse:
                clauses.append(
                    f"(started_at, id) > (${len(params) + 1}, ${len(params) + 2})"
                )
                params.extend(cursor)
                order_and_limit = (
                    f" ORDER BY started_at ASC, id ASC LIMIT ${len(params) + 1}"
                )
                params.append(clamp_limit(limit))
                where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            else:
                clauses.append(
                    f"(started_at, id) < (${len(params) + 1}, ${len(params) + 2})"
                )
                params.extend(cursor)
                order_and_limit = (
                    f" ORDER BY started_at DESC, id DESC LIMIT ${len(params) + 1}"
                )
                params.append(clamp_limit(limit))
                where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            sql = f"{select}{where}{order_and_limit}"
        else:
            suffix = ""
            if limit is not None:
                suffix = f" LIMIT {int(limit)} OFFSET {int(offset)}"
            sql = f"{select}{where} ORDER BY started_at DESC, id DESC{suffix}"
        conn = await self._conn()
        try:
            rows = await conn.fetch(sql, *params)
        finally:
            await self._release_short_lived(conn)
        result = [_row_to_dict(r) for r in rows]
        for row in result:
            self._decode_pipeline_metadata(row)
        return result

    async def count_pipelines(
        self, status: Optional[str] = None, instrument: Optional[str] = None,
    ) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = $" + str(len(params) + 1))
            params.append(status)
        if instrument:
            clauses.append("instrument = $" + str(len(params) + 1))
            params.append(instrument)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        conn = await self._conn()
        try:
            val = await conn.fetchval(
                f"SELECT COUNT(*) FROM pipelines{where}", *params
            )
        finally:
            await self._release_short_lived(conn)
        return int(val) if val is not None else 0

    async def collect_observability_metrics(
        self, *, active_sessions: int = 0,
    ) -> Dict[str, Any]:
        # Defer to SQLiteStateStore's implementation by computing the same
        # aggregates over Postgres rows. The counters/aggregation logic is
        # backend-neutral (pure dict math); only the fetch differs. We import
        # the shared helpers and the SQLite impl's private pure functions.
        from collections import Counter, defaultdict

        from src.core.observability import OBSERVABILITY_SCHEMA_VERSION, alert_suggestions
        from src.core.state_store import (
            _attempt_outcome,
            _counter_rows,
            _json_list,
            _json_object,
            _reason_slug,
            _replay_status,
            _value_rows,
        )

        conn = await self._conn()
        try:
            sessions = [
                _row_to_dict(r) for r in await conn.fetch("SELECT * FROM research_sessions")
            ]
            pipelines = [
                _row_to_dict(r) for r in await conn.fetch("SELECT * FROM pipelines")
            ]
            planned_trials = [
                _row_to_dict(r) for r in await conn.fetch("SELECT * FROM planned_trials")
            ]
            iterations = [_row_to_dict(r) for r in await conn.fetch(
                """SELECT i.*, s.model_type AS session_model_type
                   FROM iterations i
                   LEFT JOIN research_sessions s ON s.id = i.research_id"""
            )]
            promotions = [
                _row_to_dict(r) for r in await conn.fetch("SELECT * FROM promotions")
            ]
            runtime_commands = [
                _row_to_dict(r) for r in await conn.fetch("SELECT * FROM runtime_commands")
            ]
            audit_events = [
                _row_to_dict(r) for r in await conn.fetch("SELECT * FROM audit_events")
            ]
        finally:
            await self._release_short_lived(conn)

        session_counts: Counter[tuple[Any, ...]] = Counter()
        session_model_counts: Counter[tuple[Any, ...]] = Counter()
        api_cost_total = 0.0
        api_cost_by_model: defaultdict[str, float] = defaultdict(float)
        for session in sessions:
            model_type = session.get("model_type") or "unknown"
            status = session.get("status") or "unknown"
            session_counts[(status, model_type)] += 1
            session_model_counts[(model_type,)] += 1
            cost = float(session.get("total_api_cost_usd") or 0.0)
            api_cost_total += cost
            api_cost_by_model[str(model_type)] += cost

        pipeline_counts: Counter[tuple[Any, ...]] = Counter()
        blocked_promotions: Counter[tuple[Any, ...]] = Counter()
        for pipeline in pipelines:
            status = pipeline.get("status") or "unknown"
            phase = pipeline.get("current_phase") or "none"
            pipeline_counts[(status, phase)] += 1
            if status == "promotion_blocked":
                blockers = _json_list(pipeline.get("promotion_blockers_json"))
                for blocker in blockers or ["unknown"]:
                    blocked_promotions[("development", _reason_slug(blocker))] += 1

        planned_counts: Counter[tuple[Any, ...]] = Counter()
        for trial in planned_trials:
            status = trial.get("status") or "unknown"
            phase = trial.get("search_phase") or "unknown"
            planned_counts[(status, phase)] += 1

        attempt_counts: Counter[tuple[Any, ...]] = Counter()
        training_duration: defaultdict[tuple[Any, ...], Dict[str, float]] = defaultdict(
            lambda: {"sum": 0.0, "count": 0.0}
        )
        rl_replay_counts: Counter[tuple[Any, ...]] = Counter()
        for iteration in iterations:
            metrics = _json_object(iteration.get("metrics_json"))
            model_type = iteration.get("session_model_type") or "unknown"
            outcome = _attempt_outcome(iteration, metrics)
            attempt_counts[(outcome, model_type)] += 1
            duration = iteration.get("training_time_s")
            if duration is not None:
                key = (model_type, outcome)
                training_duration[key]["sum"] += float(duration)
                training_duration[key]["count"] += 1
            if model_type == "rl":
                rl_replay_counts[(_replay_status(metrics), model_type)] += 1

        promotion_scope_counts: Counter[tuple[Any, ...]] = Counter()
        for promotion in promotions:
            promotion_scope_counts[(promotion.get("scope") or "development",)] += 1

        runtime_counts: Counter[tuple[Any, ...]] = Counter()
        for command in runtime_commands:
            runtime_counts[(command.get("status") or "unknown",)] += 1

        command_rejections: Counter[tuple[Any, ...]] = Counter()
        for event in audit_events:
            action = event.get("action")
            metadata = _json_object(event.get("request_metadata_json"))
            if action in {"command.reject", "structured_hpo.manual_review"}:
                operation = (
                    metadata.get("operation")
                    or metadata.get("policy_operation")
                    or action
                )
                command_rejections[(operation or "unknown",)] += 1
            if (
                isinstance(action, str)
                and action.startswith("promotion.")
                and event.get("outcome") == "failure"
            ):
                scope = metadata.get("scope") or "unknown"
                reason = _reason_slug(event.get("error_message"))
                blocked_promotions[(scope, reason)] += 1

        if not command_rejections:
            for command in runtime_commands:
                if command.get("status") != "rejected":
                    continue
                metadata = _json_object(command.get("metadata_json"))
                operation = (
                    command.get("policy_operation")
                    or metadata.get("policy_operation")
                    or "unknown"
                )
                command_rejections[(operation,)] += 1

        return {
            "schema_version": OBSERVABILITY_SCHEMA_VERSION,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "active_sessions": active_sessions,
            "sessions": {
                "by_status": _counter_rows(session_counts, ("status", "model_type")),
                "by_model_type": _counter_rows(session_model_counts, ("model_type",)),
            },
            "pipelines": {
                "by_status": _counter_rows(pipeline_counts, ("status", "phase")),
            },
            "planned_trials": {
                "by_status": _counter_rows(planned_counts, ("status", "search_phase")),
            },
            "attempts": {
                "by_outcome": _counter_rows(attempt_counts, ("outcome", "model_type")),
                "training_duration_seconds": [
                    {
                        "model_type": labels[0],
                        "outcome": labels[1],
                        "sum": values["sum"],
                        "count": int(values["count"]),
                    }
                    for labels, values in sorted(training_duration.items())
                ],
            },
            "api_cost": {
                "total_usd": api_cost_total,
                "by_model_type": _value_rows(api_cost_by_model, "model_type"),
            },
            "promotions": {
                "by_scope": _counter_rows(promotion_scope_counts, ("scope",)),
                "blocked_by_reason": _counter_rows(
                    blocked_promotions, ("scope", "reason")
                ),
            },
            "rl_replay": {
                "by_status": _counter_rows(rl_replay_counts, ("status", "model_type")),
            },
            "runtime_commands": {
                "by_status": _counter_rows(runtime_counts, ("status",)),
            },
            "command_policy": {
                "rejections_by_operation": _counter_rows(
                    command_rejections, ("operation",)
                ),
            },
            "alert_suggestions": alert_suggestions(),
        }

    # ------------------------------------------------------------------
    # Shared decode helpers (mirror SQLiteStateStore)
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_planned_trial(row: Dict[str, Any]) -> None:
        raw_patch = row.get("config_patch_json")
        if raw_patch and "config_patch" not in row:
            try:
                row["config_patch"] = json.loads(raw_patch)
            except (json.JSONDecodeError, TypeError):
                row["config_patch"] = {}
        raw_identity = row.get("trial_identity_json")
        if raw_identity and "trial_identity" not in row:
            try:
                row["trial_identity"] = json.loads(raw_identity)
            except (json.JSONDecodeError, TypeError):
                row["trial_identity"] = None

    @staticmethod
    def _decode_promotion_metadata(row: Dict[str, Any]) -> None:
        raw_metadata = row.get("promotion_metadata_json")
        if raw_metadata:
            try:
                row["promotion_metadata"] = json.loads(raw_metadata)
            except (json.JSONDecodeError, TypeError):
                row["promotion_metadata"] = None
        raw_rollback_metadata = row.get("rollback_metadata_json")
        if raw_rollback_metadata:
            try:
                row["rollback_metadata"] = json.loads(raw_rollback_metadata)
            except (json.JSONDecodeError, TypeError):
                row["rollback_metadata"] = None

    @staticmethod
    def _decode_pipeline_metadata(row: Dict[str, Any]) -> None:
        raw_blockers = row.get("promotion_blockers_json")
        if raw_blockers:
            try:
                parsed = json.loads(raw_blockers)
                row["promotion_blockers"] = (
                    parsed if isinstance(parsed, list) else []
                )
            except (json.JSONDecodeError, TypeError):
                row["promotion_blockers"] = []
        raw_preview = row.get("promotion_preview_json")
        if raw_preview:
            try:
                parsed = json.loads(raw_preview)
                row["promotion_preview"] = (
                    parsed if isinstance(parsed, dict) else None
                )
            except (json.JSONDecodeError, TypeError):
                row["promotion_preview"] = None


def _parse_rowcount(status: str) -> int:
    """Parse asyncpg's ``UPDATE N`` / ``DELETE N`` command-tag row count."""
    if not status:
        return 0
    parts = status.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        return int(parts[-1])
    return 0


def is_postgres_dsn(url: Optional[str]) -> bool:
    """True when ``url`` selects the Postgres backend (D-backend-by-config)."""
    if not url:
        return False
    lowered = url.lower()
    return lowered.startswith("postgresql://") or lowered.startswith(
        "postgresql+asyncpg://"
    )


def build_state_store(  # type: ignore[no-untyped-def]
    settings: Any,
) -> Any:
    """Factory selecting the store backend from ``settings.database_url``.

    ARC-011 P6-002a (D-backend-by-config). ``None`` / sqlite URL →
    :class:`SQLiteStateStore` (today's behavior, byte-identical); a Postgres
    DSN → :class:`PostgresStateStore`. Wired in ``src/main.py`` lifespan.
    """
    if is_postgres_dsn(getattr(settings, "database_url", None)):
        return PostgresStateStore(settings.database_url)
    from src.core.state_store import SQLiteStateStore

    return SQLiteStateStore(settings.db_path)
