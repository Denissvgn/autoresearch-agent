"""Session manager — tracks active asyncio tasks for research sessions."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
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
        tag: str,
        quick_mode: Optional[bool] = None,
        max_iterations: Optional[int] = None,
        max_budget_usd: Optional[float] = None,
        focus_hint: Optional[str] = None,
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
        workspace_path = (
            f"{settings.runs_dir}/{instrument}_{timeframe}/{model_type}"
        )

        config = ResearchConfig(
            id=research_id,
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
            tag=tag,
            quick_mode=quick_mode if quick_mode is not None else settings.default_quick_mode,
            max_iterations=max_iterations or settings.max_iterations,
            max_budget_usd=max_budget_usd or settings.max_budget_usd,
            focus_hint=focus_hint,
            workspace_path=workspace_path,
        )

        # Persist session to DB
        session_dict = await self._store.create_session(
            session_id=research_id,
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
            tag=tag,
            quick_mode=config.quick_mode,
            max_iterations=config.max_iterations,
            max_budget_usd=config.max_budget_usd,
            focus_hint=focus_hint,
            workspace_path=workspace_path,
        )

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
