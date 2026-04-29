"""Session manager — tracks active asyncio tasks for research sessions."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from server.config import settings
from server.core.orchestrator import AgentOrchestrator, ResearchConfig
from server.core.pipeline_controller import PipelineConfig, PipelineController
from server.core.research_manifest import build_research_manifest, manifest_pretty_json
from server.core.results_store import ResultsStore
from server.core.service_preflight import (
    require_preflight_ready,
    run_service_preflight,
)
from server.core.structured_hpo import build_structured_hpo_plan, hpo_plan_json

logger = logging.getLogger(__name__)


@dataclass
class ActiveSession:
    research_id: str
    task: asyncio.Task
    config: ResearchConfig
    started_at: datetime


class SessionManager:
    """Manages the lifecycle of research sessions as asyncio tasks."""

    def __init__(self, store: ResultsStore) -> None:
        self._store = store
        self._orchestrator = AgentOrchestrator(store)
        self._pipeline_ctrl = PipelineController(store, self)
        self._active: Dict[str, ActiveSession] = {}
        self._active_pipelines: Dict[str, asyncio.Task] = {}

    @property
    def active_count(self) -> int:
        return len(self._active)

    def is_running(self, research_id: str) -> bool:
        return research_id in self._active

    async def start_session(
        self,
        *,
        instrument: str,
        timeframe: str,
        model_type: str,
        tag: Optional[str] = None,
        quick_mode: Optional[bool] = None,
        max_iterations: Optional[int] = None,
        max_budget_usd: Optional[float] = None,
        timeout_minutes: Optional[int] = None,
        focus_hint: Optional[str] = None,
        trading_mode: Optional[str] = None,
        agent_strategy: Optional[str] = None,
        initial_balance: Optional[float] = None,
        enable_hpo: Optional[bool] = None,
        hpo_trials: Optional[int] = None,
        hpo_timesteps: Optional[int] = None,
        manifest: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Start a new research session. Returns the created session dict."""
        if self.active_count >= settings.max_concurrent_sessions:
            raise RuntimeError(
                f"Max concurrent sessions ({settings.max_concurrent_sessions}) reached"
            )

        # Block duplicate model+instrument if already running
        for session in self._active.values():
            c = session.config
            if (
                c.instrument == instrument
                and c.timeframe == timeframe
                and c.model_type == model_type
            ):
                raise RuntimeError(
                    f"A {model_type} session for {instrument} {timeframe} "
                    f"is already running (id={session.research_id})"
                )

        research_id = f"res_{uuid.uuid4().hex[:12]}"
        effective_tag = tag or f"run-{research_id[-8:]}"
        workspace_path = (
            f"{settings.runs_dir}/{instrument}_{timeframe}/{model_type}"
        )

        config = ResearchConfig(
            id=research_id,
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
            tag=effective_tag,
            quick_mode=quick_mode if quick_mode is not None else settings.default_quick_mode,
            max_iterations=max_iterations or settings.max_iterations,
            max_budget_usd=max_budget_usd or settings.max_budget_usd,
            timeout_s=timeout_minutes * 60 if timeout_minutes else 0,
            focus_hint=focus_hint,
            workspace_path=workspace_path,
            trading_mode=trading_mode,
            agent_strategy=agent_strategy,
            initial_balance=initial_balance,
            enable_hpo=enable_hpo or False,
            hpo_trials=hpo_trials or 20,
            hpo_timesteps=hpo_timesteps or 50000,
        )

        preflight = await self._run_preflight(config.model_type)
        hpo_plan = self._build_hpo_plan(config)
        manifest_overrides = self._merge_manifest_overrides(manifest, hpo_plan)
        manifest_overrides["preflight"] = preflight
        manifest_json, manifest_hash = self._build_manifest_payload(
            config, overrides=manifest_overrides,
        )

        # Archive any stale workspace from a previous session before writing
        # the new manifest so DB session boundaries match artifact boundaries.
        await self._archive_stale_workspace(workspace_path)
        manifest_path = await self._write_manifest(config, manifest_json)

        # Persist session to DB
        session_dict = await self._store.create_session(
            session_id=research_id,
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
            tag=effective_tag,
            quick_mode=config.quick_mode,
            max_iterations=config.max_iterations,
            max_budget_usd=config.max_budget_usd,
            focus_hint=focus_hint,
            workspace_path=workspace_path,
            manifest_json=manifest_json,
            manifest_path=manifest_path,
            manifest_hash=manifest_hash,
        )
        await self._record_hpo_plan(config, hpo_plan)

        # Spawn background task
        task = asyncio.create_task(
            self._run_and_cleanup(research_id, config),
            name=f"research-{research_id}",
        )
        self._active[research_id] = ActiveSession(
            research_id=research_id,
            task=task,
            config=config,
            started_at=datetime.now(timezone.utc),
        )

        logger.info(
            "Started research %s: %s %s %s (quick=%s, max_iter=%d)",
            research_id, model_type, instrument, timeframe,
            config.quick_mode, config.max_iterations,
        )
        return session_dict

    async def _run_and_cleanup(
        self, research_id: str, config: ResearchConfig,
    ) -> None:
        """Wrapper that ensures cleanup after the orchestrator finishes."""
        try:
            await self._orchestrator.run(config)
        finally:
            self._active.pop(research_id, None)

    async def _run_preflight(self, model_type: str) -> Dict[str, Any]:
        """Run dependency checks and raise before any LLM task is spawned."""
        preflight = await run_service_preflight(model_type=model_type)
        require_preflight_ready(preflight)
        if preflight.get("status") == "degraded":
            logger.warning(
                "Service preflight degraded but override is enabled: %s",
                preflight.get("required_failures"),
            )
        else:
            logger.info("Service preflight %s for %s", preflight.get("status"), model_type)
        return preflight

    async def _archive_stale_workspace(self, workspace_path: str) -> None:
        """Move an existing model workspace to a timestamped archive directory.

        Called before each new session so that DB session boundaries align
        with filesystem artifact boundaries.  The archive directory sits
        alongside the model directory:

            runs/autotuner/{instrument}_{timeframe}/archive/{model}.{ts}/

        Handles PermissionError gracefully (e.g. files created by docker exec
        as root while the server runs as appuser) by falling back to
        copytree+rmtree, then to a plain rmtree if archiving is impossible.
        """
        ws = Path(workspace_path)
        if not ws.exists():
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_dir = ws.parent / "archive" / f"{ws.name}.{ts}"
        archive_dir.parent.mkdir(parents=True, exist_ok=True)

        try:
            await asyncio.to_thread(shutil.move, str(ws), str(archive_dir))
            logger.info(
                "Archived stale workspace %s -> %s", ws, archive_dir,
            )
            return
        except PermissionError:
            logger.warning(
                "shutil.move failed (permission denied) for %s — "
                "falling back to copytree+rmtree",
                ws,
            )

        # Fallback: copy what we can, then remove the original
        try:
            await asyncio.to_thread(
                shutil.copytree, str(ws), str(archive_dir),
                dirs_exist_ok=True,
            )
            await asyncio.to_thread(
                shutil.rmtree, str(ws), ignore_errors=True,
            )
            logger.info(
                "Archived stale workspace (copy fallback) %s -> %s",
                ws, archive_dir,
            )
            return
        except Exception as exc:
            logger.warning(
                "copytree fallback also failed for %s: %s — "
                "removing stale workspace instead",
                ws, exc,
            )

        # Last resort: just remove it so the fresh session can proceed
        await asyncio.to_thread(shutil.rmtree, str(ws), ignore_errors=True)
        logger.warning("Removed stale workspace %s (could not archive)", ws)

    def _build_manifest_payload(
        self,
        config: ResearchConfig,
        *,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str]:
        manifest = build_research_manifest(
            research_id=config.id,
            instrument=config.instrument,
            timeframe=config.timeframe,
            model_type=config.model_type,
            tag=config.tag,
            quick_mode=config.quick_mode,
            max_iterations=config.max_iterations,
            max_budget_usd=config.max_budget_usd,
            timeout_s=config.timeout_s,
            focus_hint=config.focus_hint,
            trading_mode=config.trading_mode,
            agent_strategy=config.agent_strategy,
            initial_balance=config.initial_balance,
            enable_hpo=config.enable_hpo,
            hpo_trials=config.hpo_trials,
            hpo_timesteps=config.hpo_timesteps,
            overrides=overrides,
        )
        return manifest_pretty_json(manifest), manifest.manifest_hash or ""

    def _build_hpo_plan(self, config: ResearchConfig) -> Dict[str, Any]:
        return build_structured_hpo_plan(
            research_id=config.id,
            model_type=config.model_type,
            quick_mode=config.quick_mode,
            max_iterations=config.max_iterations,
            max_budget_usd=config.max_budget_usd,
            timeout_s=config.timeout_s,
            enable_hpo=config.enable_hpo,
            hpo_trials=config.hpo_trials,
            hpo_timesteps=config.hpo_timesteps,
        )

    @staticmethod
    def _merge_manifest_overrides(
        overrides: Optional[Dict[str, Any]],
        hpo_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = dict(overrides or {})
        hpo = dict(merged.get("hpo") or {})
        hpo.update(hpo_plan)
        merged["hpo"] = hpo
        return merged

    async def _record_hpo_plan(
        self,
        config: ResearchConfig,
        hpo_plan: Dict[str, Any],
    ) -> None:
        if not hpo_plan.get("enabled"):
            return
        await self._store.record_hpo_study_plan(
            research_id=config.id,
            study_id=hpo_plan["study_id"],
            max_trials=int(hpo_plan.get("max_trials") or 0),
            search_space_json=hpo_plan_json(hpo_plan.get("search_space") or {}),
            budget_json=hpo_plan_json(hpo_plan.get("budget") or {}),
            timeout_s=int(hpo_plan.get("timeout_s") or 0),
            quick_mode=bool(hpo_plan.get("quick_mode")),
        )

    async def _write_manifest(
        self,
        config: ResearchConfig,
        manifest_json: str,
    ) -> str:
        filename = (
            "research_manifest.json"
            if not config.resumed_from
            else f"research_manifest_{config.id}.json"
        )
        path = Path(config.workspace_path) / filename
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(
            path.write_text, manifest_json, encoding="utf-8",
        )
        return str(path)

    async def continue_session(
        self,
        parent_id: str,
        *,
        max_iterations: Optional[int] = None,
        max_budget_usd: Optional[float] = None,
        timeout_minutes: Optional[int] = None,
        focus_hint: Optional[str] = None,
    ) -> Dict:
        """ML-62: Continue a timed-out session as a new chained session.

        Creates a new session that inherits instrument/timeframe/model_type
        and all fixed settings from the parent. Crucially, it does NOT
        archive the workspace — the new session picks up where the parent
        left off with the same train.yaml, best_train.yaml, and results.
        """
        # Validate parent session
        parent = await self._store.get_session(parent_id)
        if not parent:
            raise RuntimeError(f"Parent session {parent_id} not found")
        if parent["status"] not in ("timed_out", "completed", "failed"):
            raise RuntimeError(
                f"Can only continue sessions with status timed_out/completed/failed, "
                f"got: {parent['status']}"
            )

        instrument = parent["instrument"]
        timeframe = parent["timeframe"]
        model_type = parent["model_type"]

        if self.active_count >= settings.max_concurrent_sessions:
            raise RuntimeError(
                f"Max concurrent sessions ({settings.max_concurrent_sessions}) reached"
            )

        # Block duplicate if already running
        for session in self._active.values():
            c = session.config
            if (
                c.instrument == instrument
                and c.timeframe == timeframe
                and c.model_type == model_type
            ):
                raise RuntimeError(
                    f"A {model_type} session for {instrument} {timeframe} "
                    f"is already running (id={session.research_id})"
                )

        # Compute remaining iterations (parent max - parent completed)
        parent_iterations = await self._store.get_iterations(parent_id)
        parent_iter_count = len(parent_iterations)
        parent_max = parent.get("max_iterations") or settings.max_iterations
        remaining = max(parent_max - parent_iter_count, 5)  # at least 5

        research_id = f"res_{uuid.uuid4().hex[:12]}"
        effective_tag = f"cont-{parent_id[-8:]}"
        workspace_path = parent["workspace_path"]

        config = ResearchConfig(
            id=research_id,
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
            tag=effective_tag,
            quick_mode=bool(parent.get("quick_mode")),
            max_iterations=max_iterations or remaining,
            max_budget_usd=max_budget_usd or settings.max_budget_usd,
            timeout_s=timeout_minutes * 60 if timeout_minutes else 0,
            focus_hint=focus_hint or parent.get("focus_hint"),
            workspace_path=workspace_path,
            resumed_from=parent_id,
        )

        preflight = await self._run_preflight(config.model_type)
        hpo_plan = self._build_hpo_plan(config)
        manifest_overrides = {
            "runtime": {"resumed_from": parent_id},
            "preflight": preflight,
        }
        manifest_json, manifest_hash = self._build_manifest_payload(
            config,
            overrides=self._merge_manifest_overrides(
                manifest_overrides, hpo_plan,
            ),
        )
        manifest_path = await self._write_manifest(config, manifest_json)

        # Persist session to DB with resumed_from link
        session_dict = await self._store.create_session(
            session_id=research_id,
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
            tag=effective_tag,
            quick_mode=config.quick_mode,
            max_iterations=config.max_iterations,
            max_budget_usd=config.max_budget_usd,
            focus_hint=config.focus_hint,
            workspace_path=workspace_path,
            manifest_json=manifest_json,
            manifest_path=manifest_path,
            manifest_hash=manifest_hash,
        )
        # Set resumed_from (not in create_session signature)
        await self._store.update_session(research_id, resumed_from=parent_id)
        await self._record_hpo_plan(config, hpo_plan)

        # ML-62: Do NOT archive the workspace — it IS the continuation state.
        # The workspace contains train.yaml, best_train.yaml, results from
        # the parent session that the new session needs.

        # Spawn background task
        task = asyncio.create_task(
            self._run_and_cleanup(research_id, config),
            name=f"research-{research_id}",
        )
        self._active[research_id] = ActiveSession(
            research_id=research_id,
            task=task,
            config=config,
            started_at=datetime.now(timezone.utc),
        )

        logger.info(
            "ML-62: Continuing session %s from parent %s: %s %s %s (remaining_iter=%d)",
            research_id, parent_id, model_type, instrument, timeframe,
            config.max_iterations,
        )
        # Re-fetch to include resumed_from in the response
        return await self._store.get_session(research_id)

    # ------------------------------------------------------------------
    # Pipeline sessions (ML-63)
    # ------------------------------------------------------------------

    async def start_pipeline(
        self,
        *,
        instrument: str,
        timeframe: str,
        tag: Optional[str] = None,
        quick_mode: Optional[bool] = None,
        max_iterations: Optional[int] = None,
        max_budget_usd: Optional[float] = None,
        timeout_minutes: Optional[int] = None,
        focus_hint: Optional[str] = None,
        phase_budgets: Optional[Dict] = None,
        trading_mode: Optional[str] = None,
        agent_strategy: Optional[str] = None,
        initial_balance: Optional[float] = None,
        enable_hpo: Optional[bool] = None,
        hpo_trials: Optional[int] = None,
        hpo_timesteps: Optional[int] = None,
    ) -> Dict:
        """Start a pipeline that trains direction → volatility → rl in sequence."""
        # Block duplicate pipeline for same instrument
        for pid, task in list(self._active_pipelines.items()):
            if not task.done():
                pipe = await self._store.get_pipeline(pid)
                if (
                    pipe
                    and pipe["instrument"] == instrument
                    and pipe["timeframe"] == timeframe
                    and pipe["status"] == "running"
                ):
                    raise RuntimeError(
                        f"A pipeline for {instrument} {timeframe} is already "
                        f"running (id={pid})"
                    )

        pipeline_id = f"pipe_{uuid.uuid4().hex[:12]}"
        effective_tag = tag or f"pipeline-{pipeline_id[-8:]}"

        config = PipelineConfig(
            id=pipeline_id,
            instrument=instrument,
            timeframe=timeframe,
            tag=effective_tag,
            quick_mode=quick_mode if quick_mode is not None else settings.default_quick_mode,
            max_iterations=max_iterations or settings.max_iterations,
            max_budget_usd=max_budget_usd or (settings.max_budget_usd * 3),
            timeout_s=timeout_minutes * 60 if timeout_minutes else 0,
            focus_hint=focus_hint,
            phase_budgets=phase_budgets,
            trading_mode=trading_mode,
            agent_strategy=agent_strategy,
            initial_balance=initial_balance,
            enable_hpo=enable_hpo or False,
            hpo_trials=hpo_trials or 20,
            hpo_timesteps=hpo_timesteps or 50000,
        )

        await self._run_preflight("pipeline")

        # Persist pipeline to DB
        pipeline_dict = await self._store.create_pipeline(
            pipeline_id=pipeline_id,
            instrument=instrument,
            timeframe=timeframe,
            tag=effective_tag,
            max_iterations=config.max_iterations,
            max_budget_usd=config.max_budget_usd,
            quick_mode=config.quick_mode,
            timeout_s=config.timeout_s,
            focus_hint=focus_hint,
            phase_budgets=json.dumps(phase_budgets) if phase_budgets else None,
            trading_mode=trading_mode,
            agent_strategy=agent_strategy,
            initial_balance=initial_balance,
            enable_hpo=config.enable_hpo,
            hpo_trials=config.hpo_trials if config.enable_hpo else None,
            hpo_timesteps=config.hpo_timesteps if config.enable_hpo else None,
        )

        # Spawn pipeline task
        task = asyncio.create_task(
            self._run_pipeline_and_cleanup(pipeline_id, config),
            name=f"pipeline-{pipeline_id}",
        )
        self._active_pipelines[pipeline_id] = task

        logger.info(
            "Started pipeline %s: %s %s (max_iter=%d, quick=%s)",
            pipeline_id, instrument, timeframe,
            config.max_iterations, config.quick_mode,
        )
        return pipeline_dict

    async def _run_pipeline_and_cleanup(
        self, pipeline_id: str, config: PipelineConfig,
    ) -> None:
        try:
            await self._pipeline_ctrl.run(config)
        finally:
            self._active_pipelines.pop(pipeline_id, None)

    async def start_phase_session(
        self,
        *,
        instrument: str,
        timeframe: str,
        model_type: str,
        tag: str,
        quick_mode: bool,
        max_iterations: int,
        max_budget_usd: float,
        timeout_minutes: int,
        focus_hint: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        trading_mode: Optional[str] = None,
        agent_strategy: Optional[str] = None,
        initial_balance: Optional[float] = None,
        enable_hpo: bool = False,
        hpo_trials: Optional[int] = None,
        hpo_timesteps: Optional[int] = None,
    ) -> Dict:
        """Start a sub-session for a pipeline phase.

        Unlike start_session(), this:
        - Does NOT check max_concurrent (pipeline manages concurrency)
        - Does NOT block on duplicate model+instrument (pipeline manages this)
        - Archives the workspace (fresh start per phase)
        - Sets pipeline_id on the session record for linkage
        """
        research_id = f"res_{uuid.uuid4().hex[:12]}"
        workspace_path = (
            f"{settings.runs_dir}/{instrument}_{timeframe}/{model_type}"
        )

        config = ResearchConfig(
            id=research_id,
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
            tag=tag,
            quick_mode=quick_mode,
            max_iterations=max_iterations,
            max_budget_usd=max_budget_usd,
            timeout_s=timeout_minutes * 60 if timeout_minutes else 0,
            focus_hint=focus_hint,
            workspace_path=workspace_path,
            trading_mode=trading_mode,
            agent_strategy=agent_strategy,
            initial_balance=initial_balance,
            enable_hpo=enable_hpo,
            hpo_trials=hpo_trials or 20,
            hpo_timesteps=hpo_timesteps or 50000,
            pipeline_id=pipeline_id,
        )

        preflight = await self._run_preflight(config.model_type)
        hpo_plan = self._build_hpo_plan(config)
        manifest_overrides = {
            "runtime": {"pipeline_id": pipeline_id},
            "preflight": preflight,
        }
        manifest_json, manifest_hash = self._build_manifest_payload(
            config,
            overrides=self._merge_manifest_overrides(
                manifest_overrides, hpo_plan,
            ),
        )

        await self._archive_stale_workspace(workspace_path)
        manifest_path = await self._write_manifest(config, manifest_json)

        session_dict = await self._store.create_session(
            session_id=research_id,
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
            tag=tag,
            quick_mode=quick_mode,
            max_iterations=max_iterations,
            max_budget_usd=max_budget_usd,
            focus_hint=focus_hint,
            workspace_path=workspace_path,
            manifest_json=manifest_json,
            manifest_path=manifest_path,
            manifest_hash=manifest_hash,
        )
        # Link to pipeline
        if pipeline_id:
            await self._store.update_session(
                research_id, pipeline_id=pipeline_id,
            )
        await self._record_hpo_plan(config, hpo_plan)

        # Spawn and track — the pipeline controller will wait for completion
        task = asyncio.create_task(
            self._run_and_cleanup(research_id, config),
            name=f"research-{research_id}",
        )
        self._active[research_id] = ActiveSession(
            research_id=research_id,
            task=task,
            config=config,
            started_at=datetime.now(timezone.utc),
        )

        logger.info(
            "Started phase session %s: %s %s %s (pipeline=%s, max_iter=%d)",
            research_id, model_type, instrument, timeframe,
            pipeline_id, max_iterations,
        )
        return await self._store.get_session(research_id)

    async def stop_pipeline(self, pipeline_id: str) -> bool:
        """Stop a running pipeline and its current phase session."""
        task = self._active_pipelines.get(pipeline_id)
        if not task or task.done():
            return False

        self._pipeline_ctrl.request_stop(pipeline_id)

        # Also stop the currently running phase session
        pipe = await self._store.get_pipeline(pipeline_id)
        if pipe:
            for phase in ("direction", "volatility", "rl"):
                sid = pipe.get(f"{phase}_session_id")
                if sid and self.is_running(sid):
                    self._orchestrator.request_stop(sid)

        await self._store.update_pipeline(pipeline_id, status="stopped")
        logger.info("Stop requested for pipeline %s", pipeline_id)
        return True

    async def continue_pipeline(
        self,
        pipeline_id: str,
        *,
        max_iterations: Optional[int] = None,
        max_budget_usd: Optional[float] = None,
        timeout_minutes: Optional[int] = None,
        focus_hint: Optional[str] = None,
    ) -> Dict:
        """Resume a timed_out or phase_failed pipeline from last incomplete phase."""
        pipe = await self._store.get_pipeline(pipeline_id)
        if not pipe:
            raise RuntimeError(f"Pipeline {pipeline_id} not found")
        if pipe["status"] not in ("timed_out", "phase_failed", "completed", "failed"):
            raise RuntimeError(
                f"Can only continue pipelines with terminal status, got: {pipe['status']}"
            )

        completed_phases = json.loads(pipe.get("completed_phases") or "[]")
        phase_budgets = (
            json.loads(pipe["phase_budgets"])
            if pipe.get("phase_budgets")
            else None
        )

        config = PipelineConfig(
            id=pipeline_id,
            instrument=pipe["instrument"],
            timeframe=pipe["timeframe"],
            tag=pipe["tag"],
            quick_mode=bool(pipe.get("quick_mode")),
            max_iterations=max_iterations or pipe.get("max_iterations", 30),
            max_budget_usd=max_budget_usd or pipe.get("max_budget_usd", 30.0),
            timeout_s=timeout_minutes * 60 if timeout_minutes else pipe.get("timeout_s", 0),
            focus_hint=focus_hint or pipe.get("focus_hint"),
            phase_budgets=phase_budgets,
            completed_phases=completed_phases,
            trading_mode=pipe.get("trading_mode"),
            agent_strategy=pipe.get("agent_strategy"),
            initial_balance=pipe.get("initial_balance"),
            enable_hpo=bool(pipe.get("enable_hpo")),
            hpo_trials=pipe.get("hpo_trials") or 20,
            hpo_timesteps=pipe.get("hpo_timesteps") or 50000,
        )

        await self._run_preflight("pipeline")

        await self._store.update_pipeline(
            pipeline_id, status="running", error_message=None,
        )

        task = asyncio.create_task(
            self._run_pipeline_and_cleanup(pipeline_id, config),
            name=f"pipeline-{pipeline_id}",
        )
        self._active_pipelines[pipeline_id] = task

        logger.info(
            "Continuing pipeline %s from phases %s",
            pipeline_id, completed_phases,
        )
        return await self._store.get_pipeline(pipeline_id)

    async def stop_session(self, research_id: str) -> bool:
        """Request a graceful stop for a running session."""
        active = self._active.get(research_id)
        if not active:
            return False
        self._orchestrator.request_stop(research_id)
        await self._store.update_session(research_id, status="stopped")
        logger.info("Stop requested for research %s", research_id)
        return True

    async def pause_session(self, research_id: str) -> bool:
        active = self._active.get(research_id)
        if not active:
            return False
        self._orchestrator.request_pause(research_id)
        await self._store.update_session(research_id, status="paused")
        logger.info("Paused research %s", research_id)
        return True

    async def resume_session(self, research_id: str) -> bool:
        active = self._active.get(research_id)
        if not active:
            return False
        self._orchestrator.request_resume(research_id)
        await self._store.update_session(research_id, status="running")
        logger.info("Resumed research %s", research_id)
        return True

    async def shutdown(self) -> None:
        """Gracefully cancel all active sessions and pipelines."""
        total = len(self._active) + len(self._active_pipelines)
        if not total:
            return
        logger.info("Shutting down %d active sessions/pipelines...", total)
        for research_id in list(self._active):
            self._orchestrator.request_stop(research_id)
        for pipeline_id in list(self._active_pipelines):
            self._pipeline_ctrl.request_stop(pipeline_id)
        # Wait a few seconds for graceful completion
        tasks = (
            [s.task for s in self._active.values()]
            + list(self._active_pipelines.values())
        )
        if tasks:
            await asyncio.wait(tasks, timeout=15)
            for task in tasks:
                if not task.done():
                    task.cancel()
        self._active.clear()
        self._active_pipelines.clear()
        logger.info("All sessions shut down")
