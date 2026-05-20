"""SQLite-backed persistence for research sessions, iterations, and promotions."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import uuid
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

import aiosqlite

from src.core.artifact_reference import (
    normalize_artifact_references_in_mapping,
    normalize_optional_artifact_ref,
)
from src.core.gate_status import (
    consistency_report_passed,
    normalize_training_gate_aliases,
)
from src.core.observability import (
    OBSERVABILITY_SCHEMA_VERSION,
    alert_suggestions,
    log_research_event,
)

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_sessions (
    id TEXT PRIMARY KEY,
    instrument TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    model_type TEXT NOT NULL,
    tag TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    quick_mode INTEGER DEFAULT 0,
    max_iterations INTEGER DEFAULT 15,
    max_budget_usd REAL DEFAULT 10.0,
    focus_hint TEXT,
    workspace_path TEXT NOT NULL,
    manifest_json TEXT,
    manifest_path TEXT,
    manifest_hash TEXT,
    current_phase TEXT,
    next_action TEXT,
    phase_state_json TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    total_api_cost_usd REAL DEFAULT 0.0,
    best_iteration INTEGER,
    best_metric REAL,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS iterations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_id TEXT NOT NULL REFERENCES research_sessions(id),
    iteration INTEGER NOT NULL,
    primary_metric REAL,
    metric_name TEXT,
    all_gates_passed INTEGER,
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
    training_time_s REAL,
    api_cost_usd REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    UNIQUE(research_id, iteration)
);

CREATE TABLE IF NOT EXISTS promotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_id TEXT NOT NULL REFERENCES research_sessions(id),
    iteration INTEGER NOT NULL,
    study_id TEXT,
    n_trials INTEGER NOT NULL DEFAULT 0,
    max_trials INTEGER,
    completed_trials INTEGER NOT NULL DEFAULT 0,
    best_composite REAL,
    training_time_s REAL,
    top_trials_json TEXT,
    search_space_json TEXT,
    budget_json TEXT,
    timeout_s INTEGER,
    quick_mode INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS planned_trials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    max_budget_usd REAL DEFAULT 30.0,
    total_api_cost_usd REAL DEFAULT 0.0,
    phase_budgets TEXT,
    quick_mode INTEGER DEFAULT 0,
    timeout_s INTEGER DEFAULT 0,
    focus_hint TEXT,
    trading_mode TEXT,
    agent_strategy TEXT,
    initial_balance REAL,
    enable_hpo INTEGER DEFAULT 0,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    timed_out INTEGER DEFAULT 0,
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

CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp
    ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_events_action
    ON audit_events(action);
CREATE INDEX IF NOT EXISTS idx_audit_events_research_id
    ON audit_events(research_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor_timestamp
    ON audit_events(actor_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_research_timestamp
    ON audit_events(research_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_pipeline_id
    ON audit_events(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_planned_trials_research_id
    ON planned_trials(research_id);
CREATE INDEX IF NOT EXISTS idx_planned_trials_expected_command
    ON planned_trials(research_id, expected_command);
CREATE INDEX IF NOT EXISTS idx_runtime_commands_research_status
    ON runtime_commands(research_id, status);
"""

_CURRENT_SCHEMA_VERSION = 1

_MODEL_TO_SKILL = {
    "direction": "direction-autotuner",
    "volatility": "volatility-autotuner",
    "rl": "rl-autotuner",
}


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


def _json_list(raw: Any) -> List[Any]:
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _truthy_status(payload: Dict[str, Any]) -> bool:
    if not payload:
        return False
    for key in (
        "passed",
        "pass",
        "valid",
        "complete",
        "training_gates_passed",
        "all_gates_passed",
    ):
        value = payload.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.lower() in {"passed", "true", "yes"}:
            return True
    status = payload.get("status")
    return isinstance(status, str) and status.lower() in {"passed", "success", "completed"}


def _attempt_outcome(row: Dict[str, Any], metrics: Dict[str, Any]) -> str:
    status = str(metrics.get("status") or "").lower()
    if status in {"rejected_duplicate"} or row.get("duplicate_reason"):
        return "rejected_duplicate"
    if status in {"pruned"}:
        return "pruned"
    if status in {"failed", "error", "timeout", "timed_out", "crash"}:
        return "failed"
    # Issue 8: a trained-successfully iteration whose only failure mode is a
    # consistency-gate block is qualitatively different from a training
    # crash/timeout. Surface it with a distinct label so downstream retry/UI
    # logic can react (do NOT retry as transient; address the blocker)
    # without conflating it with real training failure. Fires regardless of
    # the keep/discard decision — the decision answers "did metric improve?",
    # outcome answers "did training succeed?".
    if status in {"completed", "success"} and _consistency_failed(row):
        return "consistency_blocked"
    if row.get("decision") == "discard":
        return "failed"
    if status in {"completed", "success"}:
        return "completed"
    if row.get("decision") in {"keep", "improve", "hpo_screening"}:
        return "completed"
    if row.get("primary_metric") is not None:
        return "completed" if row.get("all_gates_passed") else "failed"
    return "unknown"


def _consistency_failed(row: Dict[str, Any]) -> bool:
    """True iff the row's consistency_report explicitly recorded passed=False.

    Defensive: missing/malformed report returns False so the outcome path is
    unchanged from the pre-Issue-8 behavior for older rows.
    """
    raw = row.get("consistency_report_json")
    if not raw:
        return False
    if isinstance(raw, dict):
        report: Any = raw
    else:
        try:
            report = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return False
    return isinstance(report, dict) and report.get("passed") is False


def _replay_status(metrics: Dict[str, Any]) -> str:
    replay = (
        metrics.get("rl_economic_replay")
        if isinstance(metrics.get("rl_economic_replay"), dict)
        else metrics.get("economic_replay")
        if isinstance(metrics.get("economic_replay"), dict)
        else metrics.get("replay")
        if isinstance(metrics.get("replay"), dict)
        else {}
    )
    if not replay:
        return "missing"
    gates = replay.get("gates") if isinstance(replay.get("gates"), dict) else {}
    if _truthy_status(gates) or _truthy_status(replay):
        return "passed"
    return "failed"


def _reason_slug(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    if text.startswith("Cannot promote"):
        text = text.split("(", 1)[-1].rstrip(")")
    text = text.split(",", 1)[0].strip()
    text = text.replace(" ", "_").replace("-", "_").lower()
    return "".join(ch for ch in text if ch.isalnum() or ch == "_") or "unknown"


def _counter_rows(counter: Counter[tuple[Any, ...]], keys: tuple[str, ...]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for labels, count in sorted(counter.items()):
        row = {key: labels[index] for index, key in enumerate(keys)}
        row["count"] = count
        rows.append(row)
    return rows


def _value_rows(values: Dict[str, float], key: str) -> List[Dict[str, Any]]:
    return [
        {key: label, "value": value}
        for label, value in sorted(values.items())
    ]


def _normalized_iteration_metrics_json(
    *,
    metrics_json: Optional[str],
    all_gates_passed: Optional[bool],
    consistency_report_json: Optional[str],
    context: str,
) -> tuple[Optional[str], Optional[bool]]:
    """Normalize additive gate aliases inside an iteration metrics payload."""
    metrics_payload = _json_object(metrics_json)
    should_write_metrics = bool(metrics_payload)

    if (
        all_gates_passed is not None
        or "training_gates_passed" in metrics_payload
        or "all_gates_passed" in metrics_payload
    ):
        all_gates_passed = normalize_training_gate_aliases(
            metrics_payload,
            legacy_value=all_gates_passed,
            logger=logger,
            context=context,
        )
        should_write_metrics = True

    report_passed = consistency_report_passed(consistency_report_json)
    if report_passed is None:
        report_passed = consistency_report_passed(
            metrics_payload.get("consistency_report")
        )
    if report_passed is not None:
        metrics_payload["consistency_report_passed"] = report_passed
        should_write_metrics = True

    if should_write_metrics:
        normalize_artifact_references_in_mapping(metrics_payload)
        return json.dumps(metrics_payload, sort_keys=True), all_gates_passed
    if normalize_artifact_references_in_mapping(metrics_payload):
        return json.dumps(metrics_payload, sort_keys=True), all_gates_passed
    return metrics_json, all_gates_passed


async def _add_column_if_missing(
    db: aiosqlite.Connection,
    table: str,
    column_def: str,
) -> None:
    """Idempotent ``ALTER TABLE ADD COLUMN`` migration.

    Phase 1.3 hardening: previously each migration was wrapped in a bare
    ``try/except Exception: pass`` that silently swallowed real errors
    (disk full, permission denied, locked database). We now query
    ``PRAGMA table_info`` first and only ALTER when the column is missing,
    letting any genuine OperationalError propagate so startup fails loudly.
    """

    column_name = column_def.split()[0]
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    existing = {row[1] for row in rows}
    if column_name in existing:
        return
    await db.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


async def _get_schema_version(db: aiosqlite.Connection) -> int:
    cursor = await db.execute("SELECT version FROM schema_version WHERE id = 1")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def _set_schema_version(db: aiosqlite.Connection, version: int) -> None:
    await db.execute(
        """INSERT INTO schema_version (id, version, applied_at)
           VALUES (1, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             version = excluded.version,
             applied_at = excluded.applied_at""",
        (version, datetime.now(timezone.utc).isoformat()),
    )


async def _migrate_to_v1(db: aiosqlite.Connection) -> None:
    """Reconcile the current pre-versioned SQLite schema."""

    # Phase 1.3 hardening: idempotent column-add migrations driven by
    # PRAGMA table_info so we skip already-applied columns without
    # swallowing real OperationalErrors.
    iterations_columns = (
        # ML-52: MLflow run id
        "mlflow_run_id TEXT",
        # ML-59: HPO plan/result metadata
        "search_phase TEXT",
        "hpo_study_id INTEGER",
        # DPU-082: server-owned per-attempt snapshots
        "attempt_snapshot_json TEXT",
        "attempt_snapshot_path TEXT",
        "attempt_snapshot_hash TEXT",
        "consistency_report_json TEXT",
        # ARP-009: duplicate-safe config/seed trial identities
        "canonical_config_hash TEXT",
        "trial_identity_hash TEXT",
        "trial_identity_json TEXT",
        "duplicate_of_research_id TEXT",
        "duplicate_of_iteration INTEGER",
        "duplicate_reason TEXT",
    )
    for column_def in iterations_columns:
        await _add_column_if_missing(db, "iterations", column_def)

    research_session_columns = (
        # ML-60 / ML-62 / ML-63
        "insights TEXT",
        "resumed_from TEXT",
        "pipeline_id TEXT",
        # DPU-081: immutable research-session manifest
        "manifest_json TEXT",
        "manifest_path TEXT",
        "manifest_hash TEXT",
        # DPU-084 / DPU-087: operator-facing session phase state
        "current_phase TEXT",
        "next_action TEXT",
        "phase_state_json TEXT",
    )
    for column_def in research_session_columns:
        await _add_column_if_missing(db, "research_sessions", column_def)

    for column_def in (
        "canonical_config_hash TEXT",
        "trial_identity_hash TEXT",
        "trial_identity_json TEXT",
    ):
        await _add_column_if_missing(db, "planned_trials", column_def)

    # DPU-085: structured HPO plan/result metadata
    for column_def in (
        "study_id TEXT",
        "max_trials INTEGER",
        "search_space_json TEXT",
        "budget_json TEXT",
        "timeout_s INTEGER",
        "quick_mode INTEGER DEFAULT 0",
    ):
        await _add_column_if_missing(db, "hpo_studies", column_def)

    # DPU-070 / DPU-071: promotion decision + rollback metadata
    promotion_columns = (
        "scope TEXT NOT NULL DEFAULT 'development'",
        "metadata_path TEXT",
        "promotion_metadata_json TEXT",
        "rollback_metadata_path TEXT",
        "rollback_metadata_json TEXT",
        "rolled_back_at TEXT",
    )
    for column_def in promotion_columns:
        await _add_column_if_missing(db, "promotions", column_def)

    # ARP-005: pipeline-owned promotion diagnostics
    for column_def in (
        "promotion_blocked_phase TEXT",
        "promotion_blockers_json TEXT",
        "promotion_preview_json TEXT",
    ):
        await _add_column_if_missing(db, "pipelines", column_def)

    # CREATE INDEX IF NOT EXISTS is already idempotent at the SQL level.
    for statement in (
        "CREATE INDEX IF NOT EXISTS "
        "idx_iterations_trial_identity_hash "
        "ON iterations(trial_identity_hash)",
        "CREATE INDEX IF NOT EXISTS "
        "idx_planned_trials_trial_identity_hash "
        "ON planned_trials(trial_identity_hash)",
        "CREATE INDEX IF NOT EXISTS "
            "idx_runtime_commands_research_status "
            "ON runtime_commands(research_id, status)",
    ):
        await db.execute(statement)


async def _migrate_to_v2(db: aiosqlite.Connection) -> None:
    """Add API idempotency records and audit query covering indexes."""

    await db.execute(
        """CREATE TABLE IF NOT EXISTS idempotency_records (
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
        )"""
    )
    for statement in (
        "CREATE INDEX IF NOT EXISTS "
        "idx_audit_events_actor_timestamp "
        "ON audit_events(actor_id, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS "
        "idx_audit_events_research_timestamp "
        "ON audit_events(research_id, timestamp DESC)",
    ):
        await db.execute(statement)


async def _migrate_to_v3(db: aiosqlite.Connection) -> None:
    """F9: structured ``terminal_reason`` on ``research_sessions``.

    Replaces ad-hoc derivation of why a session ended (which previously
    required reading logs). Postmortems and the UI can now group runs by
    ``budget_exhausted`` / ``phase_plan_completed`` /
    ``agent_self_terminated_during_phase:<phase_id>`` etc.
    """
    await _add_column_if_missing(
        db,
        "research_sessions",
        "terminal_reason TEXT",
    )


async def _migrate_to_v4(db: aiosqlite.Connection) -> None:
    """Promotion waiver + effective-iteration counter on ``research_sessions``.

    ``terminate_request_received`` records whether the agent emitted an
    explicit ``TERMINATE_REQUEST:`` line (vs. an end_turn fallthrough or a
    crash). ``_try_auto_promote`` consults this flag to decide whether
    incomplete iteration-count phases can be waived.

    ``effective_iteration_count`` tracks real training attempts (excluding
    duplicate-rejected ones) so that the budget cap is not consumed by audit
    records.
    """
    await _add_column_if_missing(
        db,
        "research_sessions",
        "terminate_request_received INTEGER DEFAULT 0",
    )
    await _add_column_if_missing(
        db,
        "research_sessions",
        "terminate_request_body TEXT",
    )
    await _add_column_if_missing(
        db,
        "research_sessions",
        "effective_iteration_count INTEGER DEFAULT 0",
    )


_MIGRATIONS = (
    (1, _migrate_to_v1),
    (2, _migrate_to_v2),
    (3, _migrate_to_v3),
    (4, _migrate_to_v4),
)
_LATEST_SCHEMA_VERSION = _MIGRATIONS[-1][0]


class ResultsStore:
    """Async SQLite store for experiment data."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

    async def initialize(self) -> None:
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        if self._conn is not None:
            await self.close()
        db = await aiosqlite.connect(self._db_path)
        db.row_factory = aiosqlite.Row
        self._conn = db
        try:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("PRAGMA journal_mode = WAL")
            await db.execute("PRAGMA busy_timeout = 5000")
            await db.executescript(_SCHEMA_SQL)

            current_version = await _get_schema_version(db)
            if current_version > _LATEST_SCHEMA_VERSION:
                raise RuntimeError(
                    "ResultsStore schema version "
                    f"{current_version} is newer than supported "
                    f"v{_LATEST_SCHEMA_VERSION}"
                )
            for version, migration in _MIGRATIONS:
                if current_version < version:
                    logger.info("Applying ResultsStore schema migration v%s", version)
                    await migration(db)
                    await _set_schema_version(db, version)
                    current_version = version

            await db.commit()
        except Exception:
            await db.close()
            self._conn = None
            raise
        logger.info("Results store initialized at %s", self._db_path)

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """Yield the long-lived SQLite connection initialized at startup."""

        if self._conn is None:
            raise RuntimeError("ResultsStore is not initialized")
        yield self._conn

    async def close(self) -> None:
        """Flush and close the long-lived SQLite connection."""

        if self._conn is None:
            return
        conn = self._conn
        self._conn = None
        await conn.commit()
        await conn.close()

    async def ping(self) -> bool:
        """Return True when the persistent DB connection can answer a query."""

        try:
            async with self.connection() as db:
                async with await db.execute("SELECT 1") as cursor:
                    row = await cursor.fetchone()
            return bool(row and row[0] == 1)
        except Exception:
            logger.exception("ResultsStore ping failed")
            return False

    async def get_schema_version(self) -> int:
        async with self.connection() as db:
            return await _get_schema_version(db)

    # ------------------------------------------------------------------
    # Idempotency records
    # ------------------------------------------------------------------

    async def begin_idempotency_record(
        self,
        *,
        operation: str,
        parent_id: str,
        key_hash: str,
        request_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """Reserve an idempotency key or return the existing record."""

        now = datetime.now(timezone.utc).isoformat()
        async with self._write_lock:
            async with self.connection() as db:
                async with await db.execute(
                    """SELECT * FROM idempotency_records
                       WHERE operation = ? AND parent_id = ? AND key_hash = ?""",
                    (operation, parent_id, key_hash),
                ) as cursor:
                    row = await cursor.fetchone()
                if row:
                    return dict(row)
                await db.execute(
                    """INSERT INTO idempotency_records
                       (operation, parent_id, key_hash, request_hash, status, created_at)
                       VALUES (?, ?, ?, ?, 'running', ?)""",
                    (operation, parent_id, key_hash, request_hash, now),
                )
                await db.commit()
        return None

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
        async with self._write_lock:
            async with self.connection() as db:
                await db.execute(
                    """UPDATE idempotency_records
                       SET status = 'completed',
                           child_id = ?,
                           response_json = ?,
                           completed_at = ?
                       WHERE operation = ? AND parent_id = ? AND key_hash = ?""",
                    (child_id, response_json, now, operation, parent_id, key_hash),
                )
                await db.commit()

    async def delete_idempotency_record(
        self,
        *,
        operation: str,
        parent_id: str,
        key_hash: str,
    ) -> None:
        async with self._write_lock:
            async with self.connection() as db:
                await db.execute(
                    """DELETE FROM idempotency_records
                       WHERE operation = ? AND parent_id = ? AND key_hash = ?""",
                    (operation, parent_id, key_hash),
                )
                await db.commit()

    # ------------------------------------------------------------------
    # Audit events (ARP-002)
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
        async with self.connection() as db:
            await db.execute(
                """INSERT INTO audit_events
                   (event_id, timestamp, actor_id, action, research_id,
                    pipeline_id, request_metadata_json, outcome, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    timestamp,
                    actor_id,
                    action,
                    research_id,
                    pipeline_id,
                    metadata_json,
                    outcome,
                    error_message,
                ),
            )
            await db.commit()
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

    async def list_audit_events(
        self,
        *,
        limit: int = 100,
        action: Optional[str] = None,
        research_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if action:
            clauses.append("action = ?")
            params.append(action)
        if research_id:
            clauses.append("research_id = ?")
            params.append(research_id)
        if pipeline_id:
            clauses.append("pipeline_id = ?")
            params.append(pipeline_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(max(1, min(limit, 500)))
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT * FROM audit_events{where} ORDER BY timestamp DESC LIMIT ?",
                params,
            )
            rows = [dict(r) for r in await cursor.fetchall()]
        for row in rows:
            raw_metadata = row.pop("request_metadata_json", None)
            try:
                row["request_metadata"] = json.loads(raw_metadata or "{}")
            except (json.JSONDecodeError, TypeError):
                row["request_metadata"] = {}
        return rows

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
    ) -> Dict[str, Any]:
        skill_name = _MODEL_TO_SKILL[model_type]
        now = datetime.now(timezone.utc).isoformat()
        async with self.connection() as db:
            await db.execute(
                """INSERT INTO research_sessions
                   (id, instrument, timeframe, model_type, tag, skill_name,
                    status, quick_mode, max_iterations, max_budget_usd,
                    focus_hint, workspace_path, manifest_json, manifest_path,
                    manifest_hash, started_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id, instrument, timeframe, model_type, tag,
                    skill_name, int(quick_mode), max_iterations,
                    max_budget_usd, focus_hint, workspace_path,
                    manifest_json, manifest_path, manifest_hash, now,
                ),
            )
            await db.commit()
        log_research_event(
            logger,
            "research_session.created",
            research_id=session_id,
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
            status="running",
        )
        return await self.get_session(session_id)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM research_sessions WHERE id = ?", (session_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_sessions(
        self,
        status: Optional[str] = None,
        model_type: Optional[str] = None,
        instrument: Optional[str] = None,
        status_in: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: list = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if status_in:
            placeholders = ",".join("?" for _ in status_in)
            clauses.append(f"status IN ({placeholders})")
            params.extend(status_in)
        if model_type:
            clauses.append("model_type = ?")
            params.append(model_type)
        if instrument:
            clauses.append("instrument = ?")
            params.append(instrument)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        # Phase 5.1: pagination — bounded LIMIT/OFFSET so callers can't
        # accidentally pull tens of thousands of rows in one shot.
        suffix = ""
        if limit is not None:
            suffix = f" LIMIT {int(limit)} OFFSET {int(offset)}"
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT * FROM research_sessions{where} "
                f"ORDER BY started_at DESC{suffix}",
                params,
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def count_sessions(
        self,
        status: Optional[str] = None,
        model_type: Optional[str] = None,
        instrument: Optional[str] = None,
        status_in: Optional[Sequence[str]] = None,
    ) -> int:
        """Phase 5.1: total count for paginated listings."""

        clauses = []
        params: list = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if status_in:
            placeholders = ",".join("?" for _ in status_in)
            clauses.append(f"status IN ({placeholders})")
            params.extend(status_in)
        if model_type:
            clauses.append("model_type = ?")
            params.append(model_type)
        if instrument:
            clauses.append("instrument = ?")
            params.append(instrument)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        async with self.connection() as db:
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM research_sessions{where}", params,
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    # ------------------------------------------------------------------
    # Runtime commands (ARP-013)
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
            json.dumps(metadata, sort_keys=True)
            if metadata is not None
            else None
        )
        async with self.connection() as db:
            cursor = await db.execute(
                """INSERT INTO runtime_commands
                   (research_id, turn, tool_name, command, normalized_command,
                    policy_operation, timeout_s, status, started_at,
                    metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)""",
                (
                    research_id,
                    turn,
                    tool_name,
                    command,
                    normalized_command,
                    policy_operation,
                    timeout_s,
                    now,
                    metadata_json,
                ),
            )
            await db.commit()
            log_research_event(
                logger,
                "runtime_command.started",
                research_id=research_id,
                turn=turn,
                tool_name=tool_name,
                policy_operation=policy_operation,
                runtime_command_id=cursor.lastrowid,
            )
            return {
                "id": cursor.lastrowid,
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
            json.dumps(metadata, sort_keys=True)
            if metadata is not None
            else None
        )
        async with self.connection() as db:
            await db.execute(
                """UPDATE runtime_commands
                   SET status = ?,
                       completed_at = ?,
                       returncode = ?,
                       timed_out = ?,
                       output_preview = ?,
                       error_message = ?,
                       metadata_json = COALESCE(?, metadata_json)
                   WHERE id = ?""",
                (
                    status,
                    now,
                    returncode,
                    int(timed_out),
                    output_preview,
                    error_message,
                    metadata_json,
                    command_id,
                ),
            )
            await db.commit()
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

    async def list_runtime_commands(
        self,
        *,
        research_id: Optional[str] = None,
        status: Optional[str] = None,
        command_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if research_id:
            clauses.append("research_id = ?")
            params.append(research_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if command_id is not None:
            clauses.append("id = ?")
            params.append(command_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT * FROM runtime_commands{where} ORDER BY started_at DESC, id DESC",
                params,
            )
            rows = [dict(r) for r in await cursor.fetchall()]
            for row in rows:
                raw = row.pop("metadata_json", None)
                if raw:
                    try:
                        row["metadata"] = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        row["metadata"] = {}
                else:
                    row["metadata"] = {}
            return rows

    async def collect_observability_metrics(
        self,
        *,
        active_sessions: int = 0,
    ) -> Dict[str, Any]:
        """Collect production research metrics from persisted state."""

        async with self.connection() as db:
            db.row_factory = aiosqlite.Row

            async def fetch_all(sql: str) -> List[Dict[str, Any]]:
                cursor = await db.execute(sql)
                return [dict(row) for row in await cursor.fetchall()]

            sessions = await fetch_all("SELECT * FROM research_sessions")
            pipelines = await fetch_all("SELECT * FROM pipelines")
            planned_trials = await fetch_all("SELECT * FROM planned_trials")
            iterations = await fetch_all(
                """SELECT i.*, s.model_type AS session_model_type
                   FROM iterations i
                   LEFT JOIN research_sessions s ON s.id = i.research_id"""
            )
            promotions = await fetch_all("SELECT * FROM promotions")
            runtime_commands = await fetch_all("SELECT * FROM runtime_commands")
            audit_events = await fetch_all("SELECT * FROM audit_events")

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
                "by_status": _counter_rows(
                    session_counts,
                    ("status", "model_type"),
                ),
                "by_model_type": _counter_rows(
                    session_model_counts,
                    ("model_type",),
                ),
            },
            "pipelines": {
                "by_status": _counter_rows(
                    pipeline_counts,
                    ("status", "phase"),
                ),
            },
            "planned_trials": {
                "by_status": _counter_rows(
                    planned_counts,
                    ("status", "search_phase"),
                ),
            },
            "attempts": {
                "by_outcome": _counter_rows(
                    attempt_counts,
                    ("outcome", "model_type"),
                ),
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
                    blocked_promotions,
                    ("scope", "reason"),
                ),
            },
            "rl_replay": {
                "by_status": _counter_rows(
                    rl_replay_counts,
                    ("status", "model_type"),
                ),
            },
            "runtime_commands": {
                "by_status": _counter_rows(runtime_counts, ("status",)),
            },
            "command_policy": {
                "rejections_by_operation": _counter_rows(
                    command_rejections,
                    ("operation",),
                ),
            },
            "alert_suggestions": alert_suggestions(),
        }

    async def interrupt_runtime_commands(
        self,
        *,
        research_id: str,
        reason: str,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        async with self.connection() as db:
            cursor = await db.execute(
                """UPDATE runtime_commands
                   SET status = 'interrupted',
                       completed_at = ?,
                       error_message = ?
                   WHERE research_id = ?
                     AND status = 'running'""",
                (now, reason, research_id),
            )
            await db.commit()
            return cursor.rowcount

    async def update_session(
        self, session_id: str, **fields: Any,
    ) -> Optional[Dict[str, Any]]:
        if not fields:
            return await self.get_session(session_id)
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [session_id]
        async with self.connection() as db:
            await db.execute(
                f"UPDATE research_sessions SET {set_clause} WHERE id = ?",
                values,
            )
            await db.commit()
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
        async with self.connection() as db:
            await db.execute(
                "DELETE FROM runtime_commands WHERE research_id = ?", (session_id,),
            )
            await db.execute(
                "DELETE FROM iterations WHERE research_id = ?", (session_id,),
            )
            await db.execute(
                "DELETE FROM planned_trials WHERE research_id = ?", (session_id,),
            )
            await db.execute(
                "DELETE FROM promotions WHERE research_id = ?", (session_id,),
            )
            cursor = await db.execute(
                "DELETE FROM research_sessions WHERE id = ?", (session_id,),
            )
            await db.commit()
            return cursor.rowcount > 0

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
    ) -> Dict[str, Any]:
        # F2: persist the phase id the orchestrator believed was active when
        # this iteration ran. The `iterations.search_phase` column has existed
        # since v1 but was never written, which left phase-state derivation
        # blind to actual exploration coverage.
        metrics_json, all_gates_passed = _normalized_iteration_metrics_json(
            metrics_json=metrics_json,
            all_gates_passed=all_gates_passed,
            consistency_report_json=consistency_report_json,
            context=f"{research_id} iteration {iteration}",
        )
        mlflow_run_id = normalize_optional_artifact_ref(mlflow_run_id)
        now = datetime.now(timezone.utc).isoformat()
        async with self.connection() as db:
            await db.execute(
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
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    research_id, iteration, primary_metric, metric_name,
                    int(all_gates_passed) if all_gates_passed is not None else None,
                    decision, description, config_snapshot,
                    canonical_config_hash, trial_identity_hash,
                    trial_identity_json, duplicate_of_research_id,
                    duplicate_of_iteration, duplicate_reason, metrics_json,
                    attempt_snapshot_json, attempt_snapshot_path,
                    attempt_snapshot_hash, consistency_report_json,
                    training_time_s, api_cost_usd, now, mlflow_run_id,
                    search_phase,
                ),
            )
            await db.commit()

            # ML-53: Update session best for keep OR improve (research progress)
            if decision in ("keep", "improve"):
                session = await self.get_session(research_id)
                best_metric = session["best_metric"] if session else None
                if session and primary_metric is not None and (
                    best_metric is None
                    or primary_metric > best_metric + metric_improvement_epsilon
                ):
                    await self.update_session(
                        research_id,
                        best_iteration=iteration,
                        best_metric=primary_metric,
                    )

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

    async def get_iterations(
        self, research_id: str,
    ) -> List[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM iterations WHERE research_id = ? ORDER BY iteration",
                (research_id,),
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def get_cross_session_iteration_summary(
        self,
        *,
        instrument: str,
        timeframe: str,
        model_type: str,
        exclude_research_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Compact summary of iterations from OTHER sessions for the same
        (instrument, timeframe, model_type). Used by the iteration-context
        digest to warn the agent away from already-explored canonical configs
        and to surface server-side capability gaps observed across runs.

        Each row is keyed by ``canonical_config_hash`` and contains the
        best ``primary_metric`` observed for that hash, the originating
        session id, the count of attempts, a representative
        ``config_snapshot`` (YAML) for parameter-signature projection, and
        concatenated ``adaptive_feature_noop_reason`` / TSFM signals for
        the feature-availability observation pass.

        Filter: rows with ``duplicate_reason IS NOT NULL`` are excluded —
        those are the dedup engine's own collision audit records, not
        real exploration attempts. Decision (keep/discard) is NOT filtered:
        the agent collides with every prior canonical hash in the dedup
        index, not just kept ones, so the digest must surface all of them.

        Returns up to ``limit`` rows, ordered by best metric descending.
        The digest layer down-samples this population via parameter-space
        clustering (``_select_representative_clusters``) rather than showing
        a raw top-N slice, so ``limit`` is intentionally large to give the
        clustering a representative view of the explored space.
        """
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                  i.canonical_config_hash AS canonical_config_hash,
                  MAX(i.primary_metric) AS best_metric,
                  MIN(i.research_id) AS first_research_id,
                  COUNT(*) AS attempts,
                  GROUP_CONCAT(
                    DISTINCT json_extract(i.metrics_json,
                                          '$.adaptive_feature_noop_reason')
                  ) AS noop_reasons,
                  GROUP_CONCAT(
                    DISTINCT json_extract(i.metrics_json, '$.tsfm_adapter')
                  ) AS tsfm_adapters,
                  GROUP_CONCAT(
                    DISTINCT json_extract(i.metrics_json,
                                          '$.tsfm_fallback_validation')
                  ) AS tsfm_fallback_flags,
                  GROUP_CONCAT(DISTINCT i.decision) AS decisions,
                  COUNT(DISTINCT i.research_id) AS session_count,
                  MIN(i.config_snapshot) AS sample_config_snapshot
                FROM iterations i
                JOIN research_sessions s ON s.id = i.research_id
                WHERE s.instrument = ?
                  AND s.timeframe = ?
                  AND s.model_type = ?
                  AND i.research_id != COALESCE(?, '')
                  AND i.canonical_config_hash IS NOT NULL
                  AND i.canonical_config_hash != ''
                  AND i.duplicate_reason IS NULL
                GROUP BY i.canonical_config_hash
                ORDER BY best_metric DESC NULLS LAST,
                         attempts DESC
                LIMIT ?
                """,
                (
                    instrument, timeframe, model_type,
                    exclude_research_id, limit,
                ),
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def update_iteration(
        self,
        research_id: str,
        iteration: int,
        marker: Dict[str, Any],
    ) -> None:
        """Overwrite an existing iteration with richer data from an explicit
        ITERATION_RESULT marker.  Only updates non-None fields from marker."""
        marker = dict(marker)
        normalize_artifact_references_in_mapping(marker)
        if "training_gates_passed" in marker or "all_gates_passed" in marker:
            normalize_training_gate_aliases(
                marker,
                logger=logger,
                context=f"{research_id} iteration {iteration} update",
            )
        fields: Dict[str, Any] = {}
        if "primary_metric" in marker:
            fields["primary_metric"] = marker["primary_metric"]
        if "metric_name" in marker:
            fields["metric_name"] = marker["metric_name"]
        if "training_gates_passed" in marker or "all_gates_passed" in marker:
            v = marker["all_gates_passed"]
            fields["all_gates_passed"] = int(v) if isinstance(v, bool) else v
        if "decision" in marker:
            fields["decision"] = marker["decision"]
        if "description" in marker:
            fields["description"] = marker["description"]
        if "config_snapshot" in marker:
            fields["config_snapshot"] = marker["config_snapshot"]
        if "canonical_config_hash" in marker:
            fields["canonical_config_hash"] = marker["canonical_config_hash"]
        if "trial_identity_hash" in marker:
            fields["trial_identity_hash"] = marker["trial_identity_hash"]
        if "trial_identity" in marker:
            fields["trial_identity_json"] = json.dumps(
                marker["trial_identity"], sort_keys=True,
            )
        if "trial_identity_json" in marker:
            fields["trial_identity_json"] = marker["trial_identity_json"]
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

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [research_id, iteration]
        async with self.connection() as db:
            await db.execute(
                f"UPDATE iterations SET {set_clause} "
                f"WHERE research_id = ? AND iteration = ?",
                values,
            )
            await db.commit()

    async def get_iteration(
        self, research_id: str, iteration: int,
    ) -> Optional[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM iterations WHERE research_id = ? AND iteration = ?",
                (research_id, iteration),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

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
        """Return an existing attempt with the same trial identity hash."""

        if not trial_identity_hash:
            return None
        params: list[Any] = [trial_identity_hash]
        if include_cross_session:
            scope_sql = (
                "(i.research_id = ? OR "
                "(s.instrument = ? AND s.timeframe = ? AND s.model_type = ?))"
            )
            params.extend([research_id, instrument, timeframe, model_type])
        else:
            scope_sql = "i.research_id = ?"
            params.append(research_id)
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"""SELECT i.*, s.instrument, s.timeframe, s.model_type
                    FROM iterations i
                    JOIN research_sessions s ON s.id = i.research_id
                    WHERE i.trial_identity_hash = ?
                      AND {scope_sql}
                    ORDER BY
                      CASE WHEN i.duplicate_reason IS NULL THEN 0 ELSE 1 END,
                      i.created_at
                    LIMIT 1""",
                params,
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_best_iteration(
        self, research_id: str,
    ) -> Optional[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            # ML-53: Include 'improve' decisions (research progress)
            cursor = await db.execute(
                """SELECT * FROM iterations
                   WHERE research_id = ? AND decision IN ('keep', 'improve')
                   ORDER BY primary_metric DESC LIMIT 1""",
                (research_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_latest_iteration_with_config_snapshot(
        self, research_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent iteration row whose config_snapshot is non-null.

        Used by AR-3 inheritance logic in ``_record_iteration`` to propagate
        the last known config_snapshot into promotion-family phases that do not
        run a fresh training command, preventing ``missing_config_snapshot``
        consistency blockers on those phases.
        """
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT iteration, config_snapshot FROM iterations "
                "WHERE research_id = ? AND config_snapshot IS NOT NULL "
                "ORDER BY iteration DESC LIMIT 1",
                (research_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return {"iteration": row[0], "config_snapshot": row[1]}

    # ------------------------------------------------------------------
    # HPO Studies (ML-59)
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
        async with self.connection() as db:
            cursor = await db.execute(
                """INSERT INTO hpo_studies
                   (research_id, iteration, n_trials, study_id, max_trials,
                    completed_trials, best_composite, training_time_s,
                    top_trials_json, search_space_json, budget_json, timeout_s,
                    quick_mode, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    research_id, iteration, n_trials, study_id, max_trials,
                    completed_trials, best_composite, training_time_s,
                    top_trials_json, search_space_json, budget_json, timeout_s,
                    int(quick_mode), status, now,
                ),
            )
            await db.commit()
            return {
                "id": cursor.lastrowid,
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
        """Persist a planned structured HPO study before training starts."""
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

    async def get_hpo_studies(
        self, research_id: str,
    ) -> List[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM hpo_studies WHERE research_id = ? ORDER BY created_at",
                (research_id,),
            )
            return [dict(r) for r in await cursor.fetchall()]

    # ------------------------------------------------------------------
    # Planned structured HPO trials (ARP-008)
    # ------------------------------------------------------------------

    async def record_planned_trials(
        self,
        *,
        research_id: str,
        study_id: Optional[str],
        trials: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Persist server-owned planned trials before execution."""
        if not trials:
            return []
        now = datetime.now(timezone.utc).isoformat()
        async with self.connection() as db:
            for trial in trials:
                config_patch = trial.get("config_patch") or {}
                await db.execute(
                    """INSERT OR REPLACE INTO planned_trials
                       (research_id, study_id, trial_id, trial_index,
                        search_phase, config_patch_json, config_hash,
                        canonical_config_hash, trial_identity_hash,
                        trial_identity_json, expected_command, status,
                        result_path, mlflow_run_id,
                        train_config_path, manual_review_reason, created_at,
                        updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
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
                    ),
                )
            await db.commit()
        phases = sorted(
            {
                str(trial.get("search_phase") or "hpo_screening")
                for trial in trials
            }
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
        """Record an off-plan structured HPO proposal for operator review."""
        now = datetime.now(timezone.utc).isoformat()
        payload = config_patch or {"proposed_command": expected_command}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        config_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        trial_id = f"manual_review_{uuid.uuid4().hex[:12]}"
        async with self.connection() as db:
            await db.execute(
                """INSERT INTO planned_trials
                   (research_id, study_id, trial_id, trial_index, search_phase,
                    config_patch_json, config_hash, canonical_config_hash,
                    trial_identity_hash, trial_identity_json, expected_command,
                    status, result_path, mlflow_run_id, train_config_path,
                    manual_review_reason, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    research_id,
                    study_id,
                    trial_id,
                    -1,
                    search_phase,
                    json.dumps(payload, sort_keys=True),
                    config_hash,
                    None,
                    None,
                    None,
                    expected_command,
                    "manual_review",
                    None,
                    None,
                    None,
                    reason,
                    now,
                    now,
                ),
            )
            await db.commit()
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

    async def get_planned_trials(
        self, research_id: str,
    ) -> List[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM planned_trials
                   WHERE research_id = ?
                   ORDER BY
                     CASE WHEN trial_index < 0 THEN 999999 ELSE trial_index END,
                     created_at""",
                (research_id,),
            )
            rows = [dict(r) for r in await cursor.fetchall()]
        for row in rows:
            self._decode_planned_trial(row)
        return rows

    async def get_planned_trial(
        self,
        research_id: str,
        trial_id: str,
    ) -> Optional[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM planned_trials
                   WHERE research_id = ? AND trial_id = ?""",
                (research_id, trial_id),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        self._decode_planned_trial(result)
        return result

    async def get_planned_trial_for_command(
        self,
        research_id: str,
        expected_command: str,
    ) -> Optional[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM planned_trials
                   WHERE research_id = ?
                     AND expected_command = ?
                     AND status != 'manual_review'
                   LIMIT 1""",
                (research_id, expected_command),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        self._decode_planned_trial(result)
        return result

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
            fields["trial_identity_json"] = json.dumps(
                trial_identity,
                sort_keys=True,
            )
        elif trial_identity_json is not None:
            fields["trial_identity_json"] = trial_identity_json
        set_clause = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [research_id, trial_id]
        async with self.connection() as db:
            await db.execute(
                f"""UPDATE planned_trials
                    SET {set_clause}
                    WHERE research_id = ? AND trial_id = ?""",
                values,
            )
            await db.commit()
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
        async with self.connection() as db:
            cursor = await db.execute(
                """INSERT INTO promotions
                   (research_id, iteration, model_type, instrument, timeframe,
                    target_path, config_yaml, previous_yaml, scope, metadata_path,
                    promotion_metadata_json, promoted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    research_id, iteration, model_type, instrument, timeframe,
                    target_path, config_yaml, previous_yaml, scope, metadata_path,
                    metadata_json, now,
                ),
            )
            await db.commit()
            promotion_id = cursor.lastrowid
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

    async def list_promotions(self) -> List[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM promotions ORDER BY promoted_at DESC",
            )
            rows = [dict(r) for r in await cursor.fetchall()]
            for row in rows:
                self._decode_promotion_metadata(row)
            return rows

    async def get_latest_development_promotion(
        self,
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
    ) -> Optional[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM promotions
                   WHERE model_type = ?
                     AND instrument = ?
                     AND timeframe = ?
                     AND scope = 'development'
                   ORDER BY promoted_at DESC
                   LIMIT 1""",
                (model_type, instrument, timeframe),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            result = dict(row)
            self._decode_promotion_metadata(result)
            return result

    async def get_latest_promotion(
        self,
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
        scope: str,
    ) -> Optional[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM promotions
                   WHERE model_type = ?
                     AND instrument = ?
                     AND timeframe = ?
                     AND scope = ?
                   ORDER BY promoted_at DESC
                   LIMIT 1""",
                (model_type, instrument, timeframe, scope),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            result = dict(row)
            self._decode_promotion_metadata(result)
            return result

    async def record_promotion_rollback(
        self,
        *,
        promotion_id: int,
        rollback_metadata_path: str,
        rollback_metadata: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        rollback_metadata_json = json.dumps(rollback_metadata, sort_keys=True)
        async with self.connection() as db:
            await db.execute(
                """UPDATE promotions
                   SET rollback_metadata_path = ?,
                       rollback_metadata_json = ?,
                       rolled_back_at = ?
                   WHERE id = ?""",
                (
                    rollback_metadata_path,
                    rollback_metadata_json,
                    now,
                    promotion_id,
                ),
            )
            await db.commit()
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM promotions WHERE id = ?",
                (promotion_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            result = dict(row)
            self._decode_promotion_metadata(result)
            return result

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

    # ------------------------------------------------------------------
    # Pipelines (ML-63)
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
        async with self.connection() as db:
            await db.execute(
                """INSERT INTO pipelines
                   (id, instrument, timeframe, tag, status, current_phase,
                    completed_phases, max_iterations, max_budget_usd,
                    quick_mode, timeout_s, focus_hint, phase_budgets,
                    trading_mode, agent_strategy, initial_balance,
                    enable_hpo, hpo_trials, hpo_timesteps, started_at)
                   VALUES (?, ?, ?, ?, 'running', NULL, '[]',
                           ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pipeline_id, instrument, timeframe, tag,
                    max_iterations, max_budget_usd, int(quick_mode),
                    timeout_s, focus_hint, phase_budgets,
                    trading_mode, agent_strategy, initial_balance,
                    int(enable_hpo), hpo_trials, hpo_timesteps, now,
                ),
            )
            await db.commit()
        log_research_event(
            logger,
            "pipeline.created",
            pipeline_id=pipeline_id,
            instrument=instrument,
            timeframe=timeframe,
            status="running",
        )
        return await self.get_pipeline(pipeline_id)

    async def get_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM pipelines WHERE id = ?", (pipeline_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            result = dict(row)
            self._decode_pipeline_metadata(result)
            return result

    async def list_pipelines(
        self,
        status: Optional[str] = None,
        instrument: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: list = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if instrument:
            clauses.append("instrument = ?")
            params.append(instrument)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        suffix = ""
        if limit is not None:
            suffix = f" LIMIT {int(limit)} OFFSET {int(offset)}"
        async with self.connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT * FROM pipelines{where} "
                f"ORDER BY started_at DESC{suffix}",
                params,
            )
            rows = [dict(r) for r in await cursor.fetchall()]
            for row in rows:
                self._decode_pipeline_metadata(row)
            return rows

    async def count_pipelines(
        self,
        status: Optional[str] = None,
        instrument: Optional[str] = None,
    ) -> int:
        """Phase 5.1: total count for paginated pipeline listings."""

        clauses = []
        params: list = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if instrument:
            clauses.append("instrument = ?")
            params.append(instrument)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        async with self.connection() as db:
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM pipelines{where}", params,
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    async def update_pipeline(
        self, pipeline_id: str, **fields: Any,
    ) -> Optional[Dict[str, Any]]:
        if not fields:
            return await self.get_pipeline(pipeline_id)
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [pipeline_id]
        async with self.connection() as db:
            await db.execute(
                f"UPDATE pipelines SET {set_clause} WHERE id = ?",
                values,
            )
            await db.commit()
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
