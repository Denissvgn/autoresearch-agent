"""Session manager — tracks active asyncio tasks for research sessions."""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from server.config import settings
from server.core.orchestrator import AgentOrchestrator, ResearchConfig
from server.core.results_store import ResultsStore

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
        self._active: Dict[str, ActiveSession] = {}

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
        )

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
        )

        # Archive any stale workspace from a previous session before spawning
        # so that DB session boundaries match artifact boundaries.  Prevents
        # old best_train.yaml, results.json, and training.log from bleeding
        # into a fresh research run.
        await self._archive_stale_workspace(workspace_path)

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
        """Gracefully cancel all active sessions (called during app shutdown)."""
        if not self._active:
            return
        logger.info("Shutting down %d active sessions...", len(self._active))
        for research_id in list(self._active):
            self._orchestrator.request_stop(research_id)
        # Wait a few seconds for graceful completion
        tasks = [s.task for s in self._active.values()]
        if tasks:
            await asyncio.wait(tasks, timeout=15)
            for task in tasks:
                if not task.done():
                    task.cancel()
        self._active.clear()
        logger.info("All sessions shut down")
