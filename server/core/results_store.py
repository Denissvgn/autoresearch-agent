"""SQLite-backed persistence for research sessions, iterations, and promotions."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
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
    metrics_json TEXT,
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
    promoted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hpo_studies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_id TEXT NOT NULL REFERENCES research_sessions(id),
    iteration INTEGER NOT NULL,
    n_trials INTEGER NOT NULL DEFAULT 0,
    completed_trials INTEGER NOT NULL DEFAULT 0,
    best_composite REAL,
    training_time_s REAL,
    top_trials_json TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    created_at TEXT NOT NULL
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
    error_message TEXT
);
"""

_MODEL_TO_SKILL = {
    "direction": "direction-autotuner",
    "volatility": "volatility-autotuner",
    "rl": "rl-autotuner",
}


class ResultsStore:
    """Async SQLite store for experiment data."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_SCHEMA_SQL)
            # ML-52: Add mlflow_run_id column (safe for existing DBs)
            try:
                await db.execute(
                    "ALTER TABLE iterations ADD COLUMN mlflow_run_id TEXT"
                )
            except Exception:
                pass  # Column already exists
            # ML-59: Add search_phase + hpo_study_id columns
            try:
                await db.execute(
                    "ALTER TABLE iterations ADD COLUMN search_phase TEXT"
                )
            except Exception:
                pass
            try:
                await db.execute(
                    "ALTER TABLE iterations ADD COLUMN hpo_study_id INTEGER"
                )
            except Exception:
                pass
            # ML-60: Add insights column for smart resume compaction
            try:
                await db.execute(
                    "ALTER TABLE research_sessions ADD COLUMN insights TEXT"
                )
            except Exception:
                pass
            # ML-62: Add resumed_from column for session chaining on timeout
            try:
                await db.execute(
                    "ALTER TABLE research_sessions ADD COLUMN resumed_from TEXT"
                )
            except Exception:
                pass
            # ML-63: Add pipeline_id column to research_sessions
            try:
                await db.execute(
                    "ALTER TABLE research_sessions ADD COLUMN pipeline_id TEXT"
                )
            except Exception:
                pass
            # DPU-070: versioned development-promotion decision metadata
            try:
                await db.execute(
                    "ALTER TABLE promotions "
                    "ADD COLUMN scope TEXT NOT NULL DEFAULT 'development'"
                )
            except Exception:
                pass
            try:
                await db.execute(
                    "ALTER TABLE promotions ADD COLUMN metadata_path TEXT"
                )
            except Exception:
                pass
            try:
                await db.execute(
                    "ALTER TABLE promotions ADD COLUMN promotion_metadata_json TEXT"
                )
            except Exception:
                pass
            await db.commit()
        logger.info("Results store initialized at %s", self._db_path)

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
    ) -> Dict[str, Any]:
        skill_name = _MODEL_TO_SKILL[model_type]
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """INSERT INTO research_sessions
                   (id, instrument, timeframe, model_type, tag, skill_name,
                    status, quick_mode, max_iterations, max_budget_usd,
                    focus_hint, workspace_path, started_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?)""",
                (
                    session_id, instrument, timeframe, model_type, tag,
                    skill_name, int(quick_mode), max_iterations,
                    max_budget_usd, focus_hint, workspace_path, now,
                ),
            )
            await db.commit()
        return await self.get_session(session_id)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self._db_path) as db:
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
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: list = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if model_type:
            clauses.append("model_type = ?")
            params.append(model_type)
        if instrument:
            clauses.append("instrument = ?")
            params.append(instrument)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT * FROM research_sessions{where} ORDER BY started_at DESC",
                params,
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def update_session(
        self, session_id: str, **fields: Any,
    ) -> Optional[Dict[str, Any]]:
        if not fields:
            return await self.get_session(session_id)
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [session_id]
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                f"UPDATE research_sessions SET {set_clause} WHERE id = ?",
                values,
            )
            await db.commit()
        return await self.get_session(session_id)

    async def delete_session(self, session_id: str) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "DELETE FROM iterations WHERE research_id = ?", (session_id,),
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
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """INSERT INTO iterations
                   (research_id, iteration, primary_metric, metric_name,
                    all_gates_passed, decision, description, config_snapshot,
                    metrics_json, training_time_s, api_cost_usd, created_at,
                    mlflow_run_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    research_id, iteration, primary_metric, metric_name,
                    int(all_gates_passed) if all_gates_passed is not None else None,
                    decision, description, config_snapshot, metrics_json,
                    training_time_s, api_cost_usd, now, mlflow_run_id,
                ),
            )
            await db.commit()

            # ML-53: Update session best for keep OR improve (research progress)
            if decision in ("keep", "improve"):
                session = await self.get_session(research_id)
                if session and (
                    session["best_metric"] is None
                    or (primary_metric is not None and primary_metric > session["best_metric"])
                ):
                    await self.update_session(
                        research_id,
                        best_iteration=iteration,
                        best_metric=primary_metric,
                    )

        return {
            "research_id": research_id,
            "iteration": iteration,
            "primary_metric": primary_metric,
            "metric_name": metric_name,
            "all_gates_passed": all_gates_passed,
            "decision": decision,
            "description": description,
            "created_at": now,
        }

    async def get_iterations(
        self, research_id: str,
    ) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM iterations WHERE research_id = ? ORDER BY iteration",
                (research_id,),
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
        fields: Dict[str, Any] = {}
        if "primary_metric" in marker:
            fields["primary_metric"] = marker["primary_metric"]
        if "metric_name" in marker:
            fields["metric_name"] = marker["metric_name"]
        if "all_gates_passed" in marker:
            v = marker["all_gates_passed"]
            fields["all_gates_passed"] = int(v) if isinstance(v, bool) else v
        if "decision" in marker:
            fields["decision"] = marker["decision"]
        if "description" in marker:
            fields["description"] = marker["description"]
        if "config_snapshot" in marker:
            fields["config_snapshot"] = marker["config_snapshot"]
        if "training_time_s" in marker:
            fields["training_time_s"] = marker["training_time_s"]
        if marker:
            fields["metrics_json"] = json.dumps(marker)

        if not fields:
            return

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [research_id, iteration]
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                f"UPDATE iterations SET {set_clause} "
                f"WHERE research_id = ? AND iteration = ?",
                values,
            )
            await db.commit()

    async def get_iteration(
        self, research_id: str, iteration: int,
    ) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM iterations WHERE research_id = ? AND iteration = ?",
                (research_id, iteration),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_best_iteration(
        self, research_id: str,
    ) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self._db_path) as db:
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
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """INSERT INTO hpo_studies
                   (research_id, iteration, n_trials, completed_trials,
                    best_composite, training_time_s, top_trials_json,
                    status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    research_id, iteration, n_trials, completed_trials,
                    best_composite, training_time_s, top_trials_json,
                    status, now,
                ),
            )
            await db.commit()
            return {
                "id": cursor.lastrowid,
                "research_id": research_id,
                "iteration": iteration,
                "n_trials": n_trials,
                "completed_trials": completed_trials,
                "best_composite": best_composite,
                "status": status,
                "created_at": now,
            }

    async def get_hpo_studies(
        self, research_id: str,
    ) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM hpo_studies WHERE research_id = ? ORDER BY created_at",
                (research_id,),
            )
            return [dict(r) for r in await cursor.fetchall()]

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
        async with aiosqlite.connect(self._db_path) as db:
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
            return {
                "id": cursor.lastrowid,
                "research_id": research_id,
                "iteration": iteration,
                "target_path": target_path,
                "scope": scope,
                "metadata_path": metadata_path,
                "promotion_metadata": promotion_metadata,
                "promoted_at": now,
            }

    async def list_promotions(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM promotions ORDER BY promoted_at DESC",
            )
            rows = [dict(r) for r in await cursor.fetchall()]
            for row in rows:
                raw_metadata = row.get("promotion_metadata_json")
                if raw_metadata:
                    try:
                        row["promotion_metadata"] = json.loads(raw_metadata)
                    except (json.JSONDecodeError, TypeError):
                        row["promotion_metadata"] = None
            return rows

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
        async with aiosqlite.connect(self._db_path) as db:
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
        return await self.get_pipeline(pipeline_id)

    async def get_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM pipelines WHERE id = ?", (pipeline_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_pipelines(
        self,
        status: Optional[str] = None,
        instrument: Optional[str] = None,
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
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT * FROM pipelines{where} ORDER BY started_at DESC",
                params,
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def update_pipeline(
        self, pipeline_id: str, **fields: Any,
    ) -> Optional[Dict[str, Any]]:
        if not fields:
            return await self.get_pipeline(pipeline_id)
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [pipeline_id]
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                f"UPDATE pipelines SET {set_clause} WHERE id = ?",
                values,
            )
            await db.commit()
        return await self.get_pipeline(pipeline_id)
