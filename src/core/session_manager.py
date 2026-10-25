"""Session manager — tracks active asyncio tasks for research sessions."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import shutil
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.config import settings
from src.core import fs_safety
from src.core.comparison_context import build_comparison_context
from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.research_manifest import (
    build_research_manifest,
    load_persisted_manifest,
    manifest_pretty_json,
)
from src.core.run_restore import assess_recovery, raise_unless_ready
from src.core.service_preflight import (
    ServicePreflightTarget,
    require_preflight_ready,
    run_service_preflight,
)
from src.core.state_machine import (
    IllegalTransitionError,
    SessionEvent,
    SessionState,
    SessionStateMachine,
)
from src.core.state_store import BudgetExceeded, CapacityExceeded, StateStore
from src.ws.events import broadcaster

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "timed_out", "stopped", "cancelled"}
)


def _derive_workspace_path(
    *,
    skill_id: str,
    instrument: str,
    timeframe: str,
    model_type: str,
    research_id: str = "",
) -> str:
    """Session workspace path (ARC-012 P7-005 / D1).

    A session whose skill declares ``workspace.session_path_template`` gets
    its workspace from the template (rendered under ``workspace_root``) — the
    skill directory owns the layout. Sessions without a resolvable skill
    (the legacy ML path) keep the incumbent ``runs/autotuner`` derivation
    byte-identically.
    """
    from src.core.skill_paths import session_workspace_path

    if skill_id:
        try:
            from src.core.skill_registry import default_registry

            skill_manifest = default_registry.get(skill_id)
        except Exception:
            skill_manifest = None
        if skill_manifest is not None:
            rendered = session_workspace_path(
                skill_manifest,
                skill_id=skill_id,
                subject_id=instrument,
                variant=timeframe,
                research_id=research_id or None,
            )
            if rendered:
                return f"{settings.workspace_root}/{rendered}"
    base = f"{settings.runs_dir}/{instrument}_{timeframe}/{model_type}"
    # Run roots are unique per research session: a fresh run must never
    # share — or archive — an older run's workspace.
    return f"{base}/{research_id}" if research_id else base


def _hard_timeout_grace_s(soft_timeout_s: int) -> int:
    """Bound hard-timeout grace to 5% of the soft timeout, 3-10 minutes."""

    return min(600, max(180, int(soft_timeout_s * 0.05)))


@dataclass
class ActiveSession:
    research_id: str
    task: asyncio.Task
    config: ResearchConfig
    started_at: datetime


class SessionManager:
    """Manages the lifecycle of research sessions as asyncio tasks."""

    def __init__(
        self,
        store: StateStore,
        *,
        state_machine: Optional[SessionStateMachine] = None,
    ) -> None:
        self._store = store
        # ARC-011 P0-003: the state machine is the sole session-status writer.
        # Injected in production so SessionManager and its orchestrator share
        # one per-session lock registry; tests may omit it.
        self._sm = state_machine or SessionStateMachine(store, broadcaster)
        self._orchestrator = AgentOrchestrator(store, state_machine=self._sm)
        self._active: Dict[str, ActiveSession] = {}
        self._active_pipelines: Dict[str, asyncio.Task] = {}
        self._owner_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self._reservations: Dict[str, Dict[str, Any]] = {}
        self._lease_task: Optional[asyncio.Task] = None
        # ARC-012 P7-009: strong references to fire-and-forget crash
        # finalizer tasks (asyncio only keeps weak refs — an unreferenced
        # task can be GC'd mid-write).
        self._crash_finalizers: set[asyncio.Task] = set()
        self._session_spawn_lock = asyncio.Lock()
        self._pipeline_spawn_lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._active)

    def is_running(self, research_id: str) -> bool:
        return research_id in self._active

    # ------------------------------------------------------------------
    # Phase 1.2: observe spawned-task exceptions
    # ------------------------------------------------------------------

    def _attach_done_callback(
        self,
        task: asyncio.Task,
        *,
        research_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
    ) -> None:
        """Log + persist + broadcast any uncaught exception escaping a
        background task.

        The orchestrator's main ``run()`` catches and records exceptions
        inside its own try/except, so this callback is a safety net for
        failures in the wrapper coroutines (e.g. ``_run_and_cleanup``) or
        for code paths that raise before/after the orchestrator's own
        handler. Without this, such failures became silent
        ``Task exception was never retrieved`` warnings at GC time with no
        operator-visible signal.

        ARC-012 P7-009 (blocker B2): a research task that dies with the
        session still ``running``/``paused`` used to leave a zombie row —
        ``status="running"``, ``error_message=null`` — forever. The callback
        now schedules ``_finalize_crashed_session`` so the row reaches a
        terminal ``failed`` state within one event-loop turn (never
        overwriting a status the orchestrator already set). Pipeline tasks
        have no session row and keep the log+broadcast-only behaviour.
        """

        def _on_done(t: asyncio.Task) -> None:
            if t.cancelled():
                return
            exc = t.exception()
            if exc is None:
                return
            kind = "pipeline" if pipeline_id else "research"
            ident = pipeline_id or research_id or t.get_name()
            logger.error(
                "Background %s task %s crashed: %s",
                kind, ident, exc, exc_info=exc,
            )
            event = {
                "event": f"{kind}_failed",
                f"{kind}_id": ident,
                "error": str(exc)[:500],
                "source": "task_done_callback",
            }
            try:
                # Best-effort broadcast; we are inside a sync callback so
                # we schedule the coroutine on the running loop.
                loop = asyncio.get_running_loop()
                if research_id is not None:
                    finalizer = loop.create_task(
                        self._finalize_crashed_session(research_id, exc),
                        name=f"crash-finalize-{research_id}",
                    )
                    self._crash_finalizers.add(finalizer)
                    finalizer.add_done_callback(self._crash_finalizers.discard)
                    return  # the finalizer owns the failed-path broadcast
                loop.create_task(broadcaster.broadcast(event))
            except RuntimeError:
                # No running loop (interpreter shutdown) — drop silently.
                pass

        task.add_done_callback(_on_done)

    async def _finalize_crashed_session(
        self, research_id: str, exc: BaseException,
    ) -> None:
        """Persist a terminal ``failed`` state for a crashed background task.

        Routed through the state machine (the sole status writer) so the
        write carries the audit row and lifecycle broadcast. Terminal
        finality makes this a no-op when the orchestrator already set a
        status — the first writer owns it — and severity resolution lets
        ``fail`` legitimately win over an in-flight ``stopping``/
        ``completing`` intent (the task died; the session did not stop or
        complete). ``LookupError``/``IllegalTransitionError`` (no row /
        refused edge) and store failures fall back to the manual broadcast
        so clients still observe the crash.
        """
        error_text = str(exc)[:2000]
        # A crashed task's terminal state must be durable: transient store
        # failures are retried (bounded) before falling back to broadcast.
        for attempt in range(3):
            try:
                result = await self._sm.transition(
                    research_id,
                    SessionEvent.FAIL,
                    status_fields={
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "error_message": error_text,
                        "terminal_reason": (
                            f"background_task_crashed:{type(exc).__name__}"
                        ),
                    },
                    broadcast_fields={
                        "error": str(exc)[:500],
                        "source": "task_done_callback",
                    },
                )
                if not result.changed:
                    logger.info(
                        "Crashed task for research %s: status already %s — "
                        "not overwritten",
                        research_id, result.new_state.value,
                    )
                return
            except (IllegalTransitionError, LookupError) as tie:
                logger.warning(
                    "Crashed task for research %s could not finalize via the "
                    "state machine (%s); broadcasting only",
                    research_id, tie,
                )
                await broadcaster.broadcast({
                    "event": "research_failed",
                    "research_id": research_id,
                    "error": str(exc)[:500],
                    "source": "task_done_callback",
                })
                return
            except Exception:
                if attempt == 2:
                    break
                await asyncio.sleep(0.05 * (attempt + 1))
        logger.exception(
            "Failed to persist terminal state for crashed research %s",
            research_id,
        )
        await broadcaster.broadcast({
            "event": "research_failed",
            "research_id": research_id,
            "error": str(exc)[:500],
            "source": "task_done_callback",
        })

    async def _reserve_budget(self, config: ResearchConfig) -> None:
        """Reserve bounded spend before work starts.

        With an authorized cap the reservation is strict (atomic
        oversubscription refusal); without one it is recorded as advisory —
        labeled with its limits, never presented as a hard money ceiling.
        """
        cap = settings.authorized_spend_cap_usd
        enforcement = "strict" if cap is not None else "advisory"
        try:
            await self._store.reserve_budget(
                reservation_id=f"budget:{config.id}",
                research_id=config.id,
                amount_usd=float(
                    config.max_budget_usd or settings.max_budget_usd
                ),
                strict_cap_usd=cap,
                enforcement=enforcement,
                lease_seconds=settings.work_lease_seconds,
            )
        except BudgetExceeded as exc:
            raise RuntimeError(str(exc)) from exc

    async def _reconcile_budget(self, research_id: str) -> None:
        """Reconcile the reservation against recorded spend at the end."""
        try:
            row = await self._store.get_session(research_id)
            actual = float((row or {}).get("total_api_cost_usd") or 0.0)
            await self._store.reconcile_budget_reservation(
                f"budget:{research_id}", actual_usd=actual,
            )
        except Exception:
            logger.exception(
                "budget reconciliation failed for %s", research_id,
            )

    async def _reserve_work(self, config: "ResearchConfig") -> None:
        """Reserve logical work and a global capacity slot atomically.

        Runs before any bootstrap/filesystem effect so two workers can never
        both admit the same request or exceed the configured global limit.
        Duplicate-request semantics: the reservation key is the research id
        (unique per attempt), so retries of the same attempt map to the same
        reservation and never double-count capacity.
        """
        scope = f"{config.skill_id}/{config.subject_id}/{config.variant}"
        try:
            reservation = await self._store.reserve_work(
                reservation_key=config.id,
                scope_key=scope,
                owner_id=self._owner_id,
                capacity_limit=settings.max_concurrent_sessions,
                lease_seconds=settings.work_lease_seconds,
            )
        except CapacityExceeded as exc:
            raise RuntimeError(str(exc)) from exc
        self._reservations[config.id] = reservation
        self._ensure_lease_renewal()

    async def _commit_work(self, research_id: str) -> None:
        await self._store.commit_work(
            reservation_key=research_id, research_id=research_id,
        )

    async def _release_work(self, research_id: str) -> None:
        self._reservations.pop(research_id, None)
        await self._store.release_work(research_id)

    async def _release_uncommitted_work(self) -> None:
        """Release reservations whose attempt failed before the session row."""
        for research_id, reservation in list(self._reservations.items()):
            if reservation.get("state") == "reserved":
                await self._release_work(research_id)
        for research_id in list(self._reservations):
            await self._store.release_budget_reservation(
                f"budget:{research_id}"
            )

    def _ensure_lease_renewal(self) -> None:
        if self._lease_task is None or self._lease_task.done():
            self._lease_task = asyncio.create_task(self._lease_renewal_loop())

    async def _lease_renewal_loop(self) -> None:
        interval = max(1.0, float(settings.work_lease_seconds) / 3.0)
        while self._reservations:
            await asyncio.sleep(interval)
            for research_id in list(self._reservations):
                try:
                    renewed = await self._store.renew_work_lease(
                        reservation_key=research_id,
                        owner_id=self._owner_id,
                        lease_seconds=settings.work_lease_seconds,
                    )
                except Exception:
                    logger.exception(
                        "lease renewal failed for %s", research_id,
                    )
                    continue
                if not renewed:
                    logger.warning(
                        "lease lost for %s; ownership may have moved",
                        research_id,
                    )
                    self._reservations.pop(research_id, None)

    async def recover_orphaned_sessions(self) -> Dict[str, int]:
        """Classify sessions left active by a previous service process."""
        # Phase 4.5: filter at the SQL layer to only candidate statuses;
        # the prior implementation pulled every session ever recorded and
        # then short-circuited on terminal statuses in Python, which got
        # expensive once the DB had thousands of rows.
        sessions = await self._store.list_sessions(
            status_in=("running", "paused"),
        )
        summary = {
            "resumable": 0,
            "interrupted": 0,
            "stopped": 0,
            "failed": 0,
            "unchanged": 0,
        }
        for session in sessions:
            classification = await self._classify_orphaned_session(session)
            status = classification["status"]
            summary[status if status in summary else "unchanged"] += 1
            if not classification.get("orphaned"):
                continue
            await self._store.interrupt_runtime_commands(
                research_id=session["id"],
                reason=classification["reason"],
            )
            # ARC-011 P0-003: route recovery through the state machine (the
            # sole status writer). RESTART_RECOVER from running|paused resolves
            # to the caller-selected recovery-terminal; error_message rides in
            # status_fields. Recovery broadcasts nothing (additive audit only).
            recovery_target = (
                SessionState.INTERRUPTED
                if status == "interrupted"
                else SessionState.RESUMABLE
            )
            await self._sm.transition(
                session["id"],
                SessionEvent.RESTART_RECOVER,
                recovery_target=recovery_target,
                status_fields={"error_message": classification["reason"]},
            )
            logger.warning(
                "Recovered orphaned session %s as %s: %s",
                session["id"],
                status,
                classification["reason"],
            )
        return summary

    async def _classify_orphaned_session(
        self,
        session: Dict[str, Any],
    ) -> Dict[str, Any]:
        status = str(session.get("status") or "")
        reservation = await self._store.get_work_reservation(
            str(session.get("research_id") or session.get("id") or "")
        )
        if reservation and reservation.get("state") in (
            "reserved", "committed",
        ):
            lease = str(reservation.get("lease_expires_at") or "")
            if lease > datetime.now(timezone.utc).isoformat():
                return {
                    "status": "owned_elsewhere",
                    "orphaned": False,
                    "reason": "live lease held by another worker",
                }
        if status in {"stopped", "cancelled"}:
            return {"status": "stopped", "orphaned": False, "reason": None}
        if status in {"failed", "timed_out"}:
            return {"status": "failed", "orphaned": False, "reason": None}
        if status not in {"running", "paused"}:
            return {"status": "unchanged", "orphaned": False, "reason": None}

        runtime_commands = await self._store.list_runtime_commands(
            research_id=session["id"],
            status="running",
        )
        workspace_path = session.get("workspace_path")
        workspace_exists = bool(workspace_path and Path(workspace_path).exists())
        manifest_path = session.get("manifest_path")
        manifest_exists = bool(manifest_path and Path(manifest_path).exists())
        recoverable = workspace_exists or manifest_exists
        new_status = "resumable" if recoverable else "interrupted"
        running_detail = (
            f"; interrupted {len(runtime_commands)} running command(s)"
            if runtime_commands
            else ""
        )
        reason = (
            "Session interrupted by service restart while status was "
            f"{status}{running_detail}. Operator action is required to resume."
        )
        if not recoverable:
            reason += " Workspace/manifest evidence was not found."
        return {
            "status": new_status,
            "orphaned": True,
            "reason": reason,
            "running_commands": runtime_commands,
        }

    async def start_session(self, **kwargs: Any) -> Dict:
        workspace_path = self._workspace_path_from_kwargs(kwargs)
        async with self._session_spawn_lock:
            try:
                return await self._start_session_unlocked(**kwargs)
            except Exception as exc:
                if workspace_path and not isinstance(exc, RuntimeError):
                    await self._cleanup_failed_start_workspace(workspace_path)
                await self._release_uncommitted_work()
                raise

    async def _start_session_unlocked(
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
        manifest: Optional[Dict[str, Any]] = None,
        # ARC-011 implementation review C1 (2026-08-15): canonical start
        # shape, forwarded by the API after P3-013 validation.
        skill_id: Optional[str] = None,
        skill_params: Optional[Dict[str, Any]] = None,
        subject_id: Optional[str] = None,
        variant: Optional[str] = None,
    ) -> Dict:
        """Start a new research session. Returns the created session dict."""
        if self.active_count >= settings.max_concurrent_sessions:
            raise RuntimeError(
                f"Max concurrent sessions ({settings.max_concurrent_sessions}) reached"
            )

        # Block duplicate skill+subject+variant if already running. The
        # comparison key is the skill identity — for non-ML sessions
        # ``model_type`` is "" for every skill (D1), so comparing it directly
        # would falsely collide two different skills on the same subject.
        duplicate_key = skill_id or model_type
        for session in self._active.values():
            c = session.config
            if (
                c.instrument == instrument
                and c.timeframe == timeframe
                and (c.skill_id or c.model_type) == duplicate_key
            ):
                raise RuntimeError(
                    f"A {duplicate_key} session for {instrument} {timeframe} "
                    f"is already running (id={session.research_id})"
                )

        research_id = f"res_{uuid.uuid4().hex[:12]}"
        effective_tag = tag or f"run-{research_id[-8:]}"
        workspace_path = _derive_workspace_path(
            research_id=research_id,
            skill_id=skill_id or "",
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
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
            skill_id=skill_id or "",
            skill_params=skill_params or {},
            subject_id=subject_id or "",
            variant=variant or "",
        )

        # ARC-012 P7-010: fail fast — a session whose skill runtime cannot
        # materialize must not get a row or a background task (201-then-crash).
        self._validate_session_skill(config)

        await self._reserve_work(config)
        await self._reserve_budget(config)
        preflight = await self._run_preflight(config)
        manifest_overrides = dict(manifest or {})
        manifest_overrides["preflight"] = preflight
        manifest_json, manifest_hash, session_nonce = self._build_manifest_payload(
            config, overrides=manifest_overrides,
        )
        await self._persist_secret_refs(config.id, manifest_json)
        # ARC-011 P4-002: carry the nonce into the orchestrator so it reaches
        # the eval subprocess env and the marker verifier.
        config.session_nonce = session_nonce

        # Archive any stale workspace from a previous session before writing
        # the new manifest so DB session boundaries match artifact boundaries.
        await self._archive_stale_workspace(workspace_path)
        manifest_path = await self._write_manifest(config, manifest_json)

        # ARC-012 P7-011: render the session workspace via the skill's
        # bootstrap plugin — the auto-initialization step BootstrapRunner was
        # built for (P5-005) that nothing invoked until now, so a fresh
        # session had no prompt.yaml/eval_set for its evaluator to score.
        # Fail fast (P7-010 rule): a skill whose bootstrap cannot render its
        # workspace gets no row and no background task.
        await self._run_skill_bootstrap(config)
        # Generated-output readiness is evaluated AFTER bootstrap.
        await self._run_local_file_preflight(config, stage="generated")

        # Persist session to DB
        # Comparable-context identity: results rank only within one context
        # (objective/units + dataset/scorer/fidelity pins + subject/variant).
        try:
            _manifest_probe = json.loads(manifest_json or "{}")
        except Exception:
            _manifest_probe = {}
        _primary_metric = (
            (_manifest_probe.get("metric_schema") or {}).get("primary") or {}
        )
        comparison_context = build_comparison_context(
            objective=str(_primary_metric.get("field") or "primary_metric"),
            units=str(_primary_metric.get("units") or "unknown"),
            subject=subject_id or None,
            variant=variant or None,
            pins=skill_params or {},
        )
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
            # ARC-012 P7-005: persist the canonical identity natively so the
            # dual-shape surface (and promotion target resolution) reads it
            # from the row instead of reconstructing it from ``model_type``.
            skill_id=skill_id or "",
            subject_id=subject_id or "",
            variant=variant or "",
            comparison_context=comparison_context,
        )
        await self._commit_work(research_id)
        # Spawn background task
        task = asyncio.create_task(
            self._run_and_cleanup(research_id, config),
            name=f"research-{research_id}",
        )
        self._attach_done_callback(task, research_id=research_id)
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
        """Wrapper that ensures cleanup after the orchestrator finishes.

        Phase 2.1: enforce a hard wall-clock timeout via ``asyncio.wait_for``
        so a stuck tool call or hung Claude API request cannot keep the
        session alive past its budget. The hard cap is the soft cap plus a
        grace window so the orchestrator's per-turn timeout still has a
        chance to fire and finalize state cleanly first.

        ARC-011 P0-003: the hard-timeout path reclassifies to ``timed_out``
        via the state machine (``HARD_TIMEOUT`` resolves ``running|stopping|
        stopped → timed_out`` by severity and the documented ``stopped →
        timed_out`` carve-out). The initial ``running`` status remains a
        storage-layer default of ``create_session`` (out of the P0-003 grep
        scope; design §11); every transition thereafter is machine-authored.
        """
        soft_timeout = (
            config.timeout_s if config.timeout_s > 0
            else settings.experiment_timeout_s
        )
        grace_s = _hard_timeout_grace_s(int(soft_timeout))
        hard_timeout = soft_timeout + grace_s
        try:
            await asyncio.wait_for(
                self._orchestrator.run(config),
                timeout=hard_timeout,
            )
        except asyncio.TimeoutError:
            # Safety-net cancel, not an operator stop: reclassify to timed_out.
            # HARD_TIMEOUT resolves from any in-flight state by severity and
            # from terminal ``stopped`` via the documented carve-out (the
            # orchestrator's CancelledError branch writes no status itself).
            logger.warning(
                "Research %s exceeded hard timeout %ds — forcing timed_out",
                research_id, hard_timeout,
            )
            try:
                await self._sm.transition(
                    research_id,
                    SessionEvent.HARD_TIMEOUT,
                    status_fields={
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "error_message": (
                            f"Hard timeout ({hard_timeout}s, grace={grace_s}s) "
                            "exceeded; session was forcibly cancelled."
                        ),
                    },
                )
            except Exception:
                logger.exception(
                    "Failed to mark research %s as timed_out", research_id,
                )
        finally:
            self._active.pop(research_id, None)
            await self._reconcile_budget(research_id)
            await self._release_work(research_id)

    @staticmethod
    def _validate_session_skill(config: ResearchConfig) -> None:
        """Validate the session's skill runtime before anything is persisted.

        ARC-012 P7-010 (blocker B2 / S1): the orchestrator materializes the
        skill runtime on its first tick — outside its own exception handler —
        so an unresolvable skill used to 201 at the API and then crash the
        background task, leaving a zombie ``running`` row. Materializing here
        (registry lookup + manifest load — cheap, side-effect-free) makes the
        same ``SkillConfigError`` fire during ``start_session`` instead: no
        row, no workspace, no spawned task for a session that cannot run.
        """
        from src.core.skill_runtime import SkillConfigError, materialize_skill_runtime
        from src.core.support_matrix import validate_manifest_support

        runtime = materialize_skill_runtime(None, config)
        # Reject schema-valid but unimplemented declarations before any side
        # effects: schema parsing is never proof that a skill can execute.
        diagnostics = validate_manifest_support(getattr(runtime, "manifest", None))
        if diagnostics:
            details = "; ".join(
                f"{d['feature']}={d['declared']!r}: {d['reason']} ({d['remedy']})"
                for d in diagnostics
            )
            raise SkillConfigError(f"unsupported skill declaration(s): {details}")
        # Provider/model roles and capabilities must resolve before any side
        # effect: an unsupported model/context combination is refused here —
        # never surfaced as a first-call failure after the run exists. The
        # same router and capability rules the orchestrator applies validate
        # the request (fail-closed diagnostics, no silent model substitution).
        from src.core.llm_provider import (
            RequiredCapabilities,
            build_provider,
            resolve_effective_provider,
            resolve_model_roles,
        )

        llm_cfg = getattr(getattr(runtime, "manifest", None), "llm", None)
        if llm_cfg is not None:
            resolve_model_roles(llm_cfg)
            build_provider(
                resolve_effective_provider(llm_cfg),
                required_capabilities=RequiredCapabilities.from_llm_config(llm_cfg),
            )

    async def _run_skill_bootstrap(self, config: ResearchConfig) -> None:
        """Render the session workspace with the skill's ``bootstrap.py``
        (ARC-012 P7-011).

        The ARC-011 §5.4 lifecycle step the BootstrapRunner was built for
        (P5-005): the skill owns its workspace layout (prompt.yaml, eval
        sets, target files), so a fresh session has something for its
        evaluator to score. Skills without a ``bootstrap.py`` skip this step;
        a bootstrap that runs but fails refuses the start (``SkillConfigError``
        — nothing persisted, nothing spawned). Continuations do not
        re-bootstrap: the inherited workspace IS the continuation state.
        """
        from src.core.bootstrap_runner import BootstrapRunner
        from src.core.skill_loader import load_layout
        from src.core.skill_registry import DEFAULT_SKILLS_ROOT, default_registry
        from src.core.skill_runtime import SkillConfigError

        skill_dir = DEFAULT_SKILLS_ROOT / config.skill_id
        layout = load_layout(skill_dir)
        if not layout.has_bootstrap:
            return
        try:
            manifest = default_registry.get(config.skill_id)
        except Exception as exc:
            raise SkillConfigError(
                f"skill_id {config.skill_id!r} was rejected by the skill "
                f"registry while bootstrapping: {exc}"
            ) from exc
        from src.core.command_runner import CommandProcessRegistry

        proc_registry = CommandProcessRegistry()
        try:
            outcome = await BootstrapRunner().run(
                skill_dir=skill_dir,
                layout=layout,
                manifest=manifest,
                workspace=Path(config.workspace_path),
                skill_params=dict(config.skill_params or {}),
                timeout_s=30.0,
                proc_registry=proc_registry,
                research_id=config.id,
            )
        except asyncio.CancelledError:
            clean = proc_registry.kill_all(config.id)
            logger.warning(
                "bootstrap cancelled for %s — plugin tree cleanup %s",
                config.id,
                "complete" if clean else "INCOMPLETE (descendants survived the termination bound)",
            )
            raise
        if not outcome.ok:
            raise SkillConfigError(
                f"skill {config.skill_id!r} bootstrap failed to render the "
                f"session workspace: {outcome.error}"
            )

    async def _run_preflight(self, config: ResearchConfig) -> Dict[str, Any]:
        """Run the skill's declared dependency checks and raise before any
        LLM task is spawned. Skills with no ``preflight`` section (or unknown
        skill ids, which fail later at runtime materialization) run with an
        empty target list — trivially ready.
        """
        targets = self._skill_preflight_targets(getattr(config, "skill_id", ""))
        preflight = await run_service_preflight(targets=targets)
        require_preflight_ready(preflight)
        # Source-stage local-file prerequisites are evaluated BEFORE the
        # bootstrap renders the workspace (generated outputs are checked
        # after it — their earlier absence is never a failure).
        await self._run_local_file_preflight(config, stage="source")
        if preflight.get("status") == "degraded":
            logger.warning(
                "Service preflight degraded but override is enabled: %s",
                preflight.get("required_failures"),
            )
        else:
            logger.info(
                "Service preflight %s for %s",
                preflight.get("status"), config.skill_id or config.model_type,
            )
        return preflight

    async def _run_local_file_preflight(
        self, config: ResearchConfig, *, stage: str,
    ) -> None:
        """Run the declared local_file prerequisites for one stage, failing
        required misses before anything else proceeds.

        Optional (``required: false``) prerequisites are reported, never
        blocking; required misses raise with the specific path and stage.
        """
        from src.core.preflight import LocalFileCheck
        from src.core.skill_registry import default_registry
        from src.core.skill_runtime import SkillConfigError

        skill_id = getattr(config, "skill_id", "")
        if not skill_id:
            return
        try:
            manifest = default_registry.get(skill_id)
        except Exception:
            return
        if manifest is None:
            return
        failures: list[str] = []
        for entry in manifest.preflight:
            if entry.kind != "local_file" or entry.stage != stage:
                continue
            result = await LocalFileCheck(
                name=entry.name,
                path=entry.path or "",
                required=entry.required,
                stage=entry.stage,
                root=getattr(config, "workspace_path", None),
            ).check()
            if not result["passed"]:
                failures.append(
                    f"{entry.name}: {result['path']} (stage={stage}, required)"
                )
        if failures:
            raise SkillConfigError(
                f"preflight {stage}-stage local_file check(s) failed: "
                + "; ".join(failures)
            )

    @staticmethod
    def _skill_preflight_targets(skill_id: str) -> list[ServicePreflightTarget]:
        """Map the skill manifest's ``preflight`` section to check targets."""
        if not skill_id:
            return []
        try:
            from src.core.skill_registry import default_registry

            manifest = default_registry.get(skill_id)
        except Exception:
            return []
        if manifest is None:
            return []
        targets: list[ServicePreflightTarget] = []
        for entry in manifest.preflight:
            if entry.kind == "local_file":
                continue
            health_paths = (
                tuple(entry.health_paths) if entry.health_paths else ("/health",)
            )
            targets.append(
                ServicePreflightTarget(
                    name=entry.name,
                    url=entry.url or "",
                    health_paths=health_paths,
                    required=entry.required,
                    transport="tcp" if entry.kind == "tcp" else "http",
                )
            )
        return targets

    async def _archive_stale_workspace(self, workspace_path: str) -> None:
        """Move an existing model workspace to a timestamped archive directory.

        Called before each new session so that DB session boundaries align
        with filesystem artifact boundaries.  The archive directory sits
        alongside the session workspace directory:

            runs/<subject>_<variant>/archive/<skill>.<ts>/

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
        parent_snapshot: Optional[Dict[str, Any]] = None,
        pinned_run_spec_sections: Optional[Mapping[str, Any]] = None,
    ) -> tuple[str, str, str]:
        manifest = build_research_manifest(
            research_id=config.id,
            instrument=config.instrument,
            timeframe=config.timeframe,
            # ARC-012 P7-005: pass the canonical skill identity — the builder
            # derives the legacy ``model_type`` alias in one place instead of
            # each call site guessing (the two callers previously disagreed).
            model_type=config.model_type,
            skill_id=config.skill_id or None,
            tag=config.tag,
            quick_mode=config.quick_mode,
            max_iterations=config.max_iterations,
            max_budget_usd=config.max_budget_usd,
            timeout_s=config.timeout_s,
            focus_hint=config.focus_hint,
            skill_params=config.skill_params or None,
            parent_snapshot=parent_snapshot,
            pinned_run_spec_sections=pinned_run_spec_sections,
            overrides=overrides,
        )
        # ARC-011 P4-002, revised by review C3 (2026-08-15): the per-session
        # anti-forgery nonce is generated HERE, out-of-band, and returned to
        # the caller (who populates config.session_nonce). It is deliberately
        # never placed inside the manifest: the manifest artifact is written
        # into the agent-readable session workspace, and the W11 adversary is
        # the agent itself — embedding the nonce there (or leaking it into
        # every governed subprocess env) handed the adversary the secret.
        # The nonce lives only in process memory for the run's lifetime;
        # nothing ever needs to read it back (continues/resumes generate a
        # fresh nonce with their own manifest).
        session_nonce = secrets.token_hex(32)
        return (
            manifest_pretty_json(manifest),
            manifest.manifest_hash or "",
            session_nonce,
        )

    def _capture_parent_snapshot(
        self, parent_workspace: str,
    ) -> Optional[Dict[str, Any]]:
        """The retained parent reference: a bundle of the parent's candidate
        and result files, content-addressed so a continuation can never
        replace or lose the artifacts it builds on.
        """
        if not parent_workspace:
            return None
        root = Path(parent_workspace)
        if not root.is_dir():
            return None
        try:
            from src.core.run_artifacts import (
                ArtifactStore,
                default_artifact_root,
                snapshot_parent_workspace,
            )

            scratch_suffixes = (".tmp", ".partial", ".swp", ".log")
            includes = sorted(
                entry.name
                for entry in root.iterdir()
                if entry.is_file()
                and not entry.name.startswith(".")
                and not entry.name.endswith(scratch_suffixes)
            )
            if not includes:
                return None
            store = ArtifactStore(default_artifact_root())
            descriptor = snapshot_parent_workspace(
                root, store, includes=includes,
            )
            return {
                "bundle_digest": descriptor["digest"],
                "file_count": len(descriptor.get("files") or {}),
                "source_research_id": None,
            }
        except Exception as exc:  # noqa: BLE001 - snapshotting never blocks
            logger.warning("Parent snapshot capture failed: %s", exc)
            return None

    async def _persist_secret_refs(
        self, research_id: str, manifest_json: str
    ) -> None:
        """Persist the run spec's secret *references* — never any value."""
        add_ref = getattr(self._store, "add_secret_ref", None)
        if add_ref is None:
            return
        try:
            raw = json.loads(manifest_json or "{}")
            refs = ((raw.get("run_spec") or {}).get("secret_refs") or {})
            for name, ref in sorted(refs.items()):
                await add_ref(
                    research_id=research_id,
                    param_name=str(name),
                    env_var=str(ref.get("env_var") or ""),
                    rebind_policy=str(ref.get("rebind_policy") or ""),
                )
        except Exception as exc:  # noqa: BLE001 - references never block runs
            logger.warning("Secret reference persistence failed: %s", exc)

    @staticmethod
    @staticmethod
    def _manifest_integrity(parent: Mapping[str, Any]) -> Dict[str, Any]:
        """Whether the parent's manifest claims a pinned spec it cannot read.

        A manifest that carries ``run_spec`` but fails to parse or validate is
        an unreadable checkpoint — reported so the restore assessment can
        refuse it instead of treating it as a legacy parent.
        """
        raw_text = str(parent.get("manifest_json") or "")
        _, report = load_persisted_manifest(raw_text)
        claims_pinned_spec = False
        if raw_text:
            try:
                raw_claims = json.loads(raw_text)
                claims_pinned_spec = isinstance(raw_claims, dict) and (
                    "run_spec" in raw_claims
                )
            except (TypeError, ValueError):
                claims_pinned_spec = False
        return {
            "claims_pinned_spec": claims_pinned_spec,
            "manifest_error": report.get("error"),
        }

    @staticmethod
    def _parent_run_spec(
        parent: Mapping[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """The parent's pinned resolved spec for continuation.

        Returns ``(skill_params, secret_refs, run_spec)``. A legacy parent
        without a spec continues with empty parameters — reported, never
        back-filled from today's defaults.
        """
        manifest, _report = load_persisted_manifest(
            str(parent.get("manifest_json") or "")
        )
        run_spec = dict((getattr(manifest, "run_spec", None) or {}))
        params = dict(run_spec.get("skill_params") or {})
        refs = dict(run_spec.get("secret_refs") or {})
        return params, refs, run_spec

    @staticmethod
    def _rebind_secret_params(
        params: Dict[str, Any], secret_refs: Mapping[str, Any]
    ) -> None:
        """Re-bind secret parameters from their named environment variables.

        The rebinding policy demands an explicit operator-supplied value: a
        missing binding is an error naming the reference, never a silent
        default and never a value recovered from any artifact.
        """
        for name, ref in sorted(secret_refs.items()):
            env_var = str(ref.get("env_var") or "")
            value = os.environ.get(env_var) if env_var else None
            if value is None:
                raise RuntimeError(
                    f"continuation requires the secret binding for parameter "
                    f"{name!r} (environment variable {env_var!r}); the "
                    f"rebinding policy {ref.get('rebind_policy')!r} demands "
                    f"an explicit operator-supplied value"
                )
            params[name] = value

    @staticmethod
    def _installed_skill_pin(
        skill_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """The currently installed skill version and manifest digest."""
        try:
            from src.core.run_spec import package_digests, skill_package_dir
            from src.core.skill_registry import default_registry

            current = default_registry.get(skill_id)
            version = getattr(current, "version", None)
            digest = package_digests(
                skill_package_dir(skill_id)
            ).get("SKILL.yaml")
            return version, digest
        except Exception:  # noqa: BLE001 - unresolvable = unverifiable
            return None, None

    def _check_skill_pin(
        self,
        *,
        skill_id: str,
        run_spec: Mapping[str, Any],
        allow_skill_drift: bool,
    ) -> None:
        """Refuse to silently re-resolve a pinned run against a new skill.

        A recorded skill version or package digest that no longer matches the
        installed skill is an explicit incompatibility: continue only with
        ``allow_skill_drift=True`` (an operator's explicit migration choice).
        """
        pinned_version = run_spec.get("skill_version")
        pinned_digest = (run_spec.get("digests") or {}).get(
            "skill_manifest_sha256"
        )
        if not pinned_version and not pinned_digest:
            return
        if allow_skill_drift:
            return
        try:
            from src.core.run_spec import package_digests, skill_package_dir
            from src.core.skill_registry import default_registry

            current = default_registry.get(skill_id)
        except Exception:  # noqa: BLE001 - unresolvable = unverifiable
            return
        current_version = getattr(current, "version", None)
        drift = (
            pinned_version is not None
            and current_version is not None
            and pinned_version != current_version
        )
        current_digest = package_digests(
            skill_package_dir(skill_id)
        ).get("SKILL.yaml")
        if (
            not drift
            and pinned_digest
            and current_digest
            and pinned_digest != current_digest
        ):
            drift = True
        if drift:
            raise RuntimeError(
                f"skill {skill_id!r} has changed since the run was pinned "
                f"(recorded version {pinned_version!r}, installed "
                f"{current_version!r}); continuing would silently re-resolve "
                f"against today's skill — migrate explicitly by continuing "
                f"with allow_skill_drift=True"
            )

    async def inspect_run_spec(self, research_id: str) -> Dict[str, Any]:
        """Inspect one run's immutable resolved spec and provenance.

        Reads only the persisted artifact — independent of the current
        registry and settings — and reports unknown fields and missing
        provenance rather than inventing current facts.
        """
        row = await self._store.get_session(research_id)
        if not row:
            raise RuntimeError(f"session {research_id} not found")
        manifest, report = load_persisted_manifest(
            str(row.get("manifest_json") or "")
        )
        return {
            "research_id": research_id,
            "run_spec": dict((getattr(manifest, "run_spec", None) or {})),
            "provenance": report,
        }

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
        await asyncio.to_thread(
            fs_safety.safe_write_text,
            config.workspace_path,
            filename,
            manifest_json,
        )
        return str(path)

    async def continue_session(
        self,
        parent_id: str,
        *,
        allow_skill_drift: bool = False,
        recovery_kind: str = "continuation",
        **kwargs: Any,
    ) -> Dict:
        async with self._session_spawn_lock:
            return await self._continue_session_unlocked(
                parent_id,
                allow_skill_drift=allow_skill_drift,
                recovery_kind=recovery_kind,
                **kwargs,
            )

    async def _continue_session_unlocked(
        self,
        parent_id: str,
        *,
        recovery_kind: str = "continuation",
        max_iterations: Optional[int] = None,
        max_budget_usd: Optional[float] = None,
        timeout_minutes: Optional[int] = None,
        focus_hint: Optional[str] = None,
        allow_skill_drift: bool = False,
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
        if parent["status"] not in (
            "timed_out",
            "phase_failed",
            "promotion_blocked",
            "failed",
            "resumable",
            "interrupted",
        ):
            raise RuntimeError(
                "Can only continue sessions with status "
                "timed_out/phase_failed/promotion_blocked/failed/resumable/interrupted, "
                f"got: {parent['status']}"
            )

        instrument = parent["instrument"]
        timeframe = parent["timeframe"]
        model_type = parent["model_type"]
        # P7-005: a continuation keeps the parent's canonical identity — a
        # non-ML parent carries skill_id (model_type is "") and the continued
        # session must still name its skill to materialize a runtime.
        parent_skill_id = parent.get("skill_id") or ""
        parent_subject_id = parent.get("subject_id") or ""
        parent_variant = parent.get("variant") or ""

        if self.active_count >= settings.max_concurrent_sessions:
            raise RuntimeError(
                f"Max concurrent sessions ({settings.max_concurrent_sessions}) reached"
            )

        # Block duplicate if already running
        duplicate_key = parent_skill_id or model_type
        for session in self._active.values():
            c = session.config
            if (
                c.instrument == instrument
                and c.timeframe == timeframe
                and (c.skill_id or c.model_type) == duplicate_key
            ):
                raise RuntimeError(
                    f"A {duplicate_key} session for {instrument} {timeframe} "
                    f"is already running (id={session.research_id})"
                )

        # Compute remaining iterations (parent max - parent completed)
        parent_iterations = await self._store.get_iterations(parent_id)
        parent_iter_count = len(parent_iterations)
        parent_max = parent.get("max_iterations") or settings.max_iterations
        remaining = max(parent_max - parent_iter_count, 5)  # at least 5

        # Continue from the parent's pinned resolved spec — never from
        # today's registry or defaults. Secret parameters re-bind from their
        # named environment variables under the explicit rebinding policy.
        continuation_params, continuation_secret_refs, parent_run_spec = (
            self._parent_run_spec(parent)
        )
        # Explicit recovery assessment: a restore must satisfy the pinned
        # contract exactly. Blockers (registry drift, unbound credentials,
        # tampered or absent spec) raise RecoveryRequired with remediations
        # — never a silent fresh run and never a silent substitution of
        # today's defaults for the pinned ones.
        current_version, current_digest = self._installed_skill_pin(
            parent_skill_id or model_type
        )
        # The parent's retained snapshot bundle must resolve: a missing
        # content-addressed artifact is an actionable recovery state, never
        # a fresh run disguised as a resume.
        parent_snapshot = parent_run_spec.get("parent_snapshot") or {}
        snapshot_digest = (
            parent_snapshot.get("digest")
            if isinstance(parent_snapshot, Mapping)
            else None
        )
        artifact_store = None
        artifact_digests: List[str] = []
        if snapshot_digest:
            from src.core.run_artifacts import ArtifactStore, default_artifact_root

            artifact_store = ArtifactStore(default_artifact_root())
            artifact_digests = [str(snapshot_digest)]
        raise_unless_ready(
            assess_recovery(
                kind=recovery_kind,
                session_id=parent_id,
                run_spec=parent_run_spec,
                secret_refs=continuation_secret_refs,
                current_skill_version=current_version,
                current_skill_digest=current_digest,
                manifest_integrity=self._manifest_integrity(parent),
                allow_skill_drift=allow_skill_drift,
                artifact_digests=artifact_digests,
                artifact_store=artifact_store,
            )
        )
        self._rebind_secret_params(
            continuation_params, continuation_secret_refs,
        )
        self._check_skill_pin(
            skill_id=parent_skill_id or model_type,
            run_spec=parent_run_spec,
            allow_skill_drift=allow_skill_drift,
        )

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
            max_budget_usd=(
                max_budget_usd
                if max_budget_usd is not None
                else (parent.get("max_budget_usd") or settings.max_budget_usd)
            ),
            timeout_s=(
                timeout_minutes * 60
                if timeout_minutes
                else (parent.get("timeout_s") or 0)
            ),
            focus_hint=focus_hint or parent.get("focus_hint"),
            workspace_path=workspace_path,
            resumed_from=parent_id,
            skill_id=parent_skill_id,
            skill_params=continuation_params,
            subject_id=parent_subject_id,
            variant=parent_variant,
        )

        # ARC-012 P7-010: same fail-fast rule as a fresh start — a parent
        # without a resolvable skill (a pre-skill-era legacy row) cannot run,
        # so it must not be continued into a new zombie.
        self._validate_session_skill(config)

        await self._reserve_work(config)
        await self._reserve_budget(config)
        preflight = await self._run_preflight(config)
        manifest_overrides = {
            "runtime": {
                "resumed_from": parent_id,
                "recovery_kind": recovery_kind,
            },
            "preflight": preflight,
        }
        manifest_json, manifest_hash, session_nonce = self._build_manifest_payload(
            config,
            overrides=manifest_overrides,
            parent_snapshot=self._capture_parent_snapshot(
                parent.get("workspace_path") or "",
            ),
            pinned_run_spec_sections={
                "objective_policy": parent_run_spec.get("objective_policy"),
                "policy": parent_run_spec.get("policy"),
                "param_defaults_applied": parent_run_spec.get(
                    "param_defaults_applied"
                ),
            }
            if parent_run_spec
            else None,
        )
        await self._persist_secret_refs(config.id, manifest_json)
        # ARC-011 P4-002: carry the nonce into the orchestrator (continue path).
        config.session_nonce = session_nonce
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
            skill_id=parent_skill_id,
            subject_id=parent_subject_id,
            variant=parent_variant,
        )
        # Set resumed_from (not in create_session signature)
        await self._store.update_session(research_id, resumed_from=parent_id)

        # ML-62: Do NOT archive the workspace — it IS the continuation state.
        # The workspace contains train.yaml, best_train.yaml, results from
        # the parent session that the new session needs.

        # Spawn background task
        task = asyncio.create_task(
            self._run_and_cleanup(research_id, config),
            name=f"research-{research_id}",
        )
        self._attach_done_callback(task, research_id=research_id)
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

    async def resume_interrupted_session(
        self,
        parent_id: str,
        *,
        reason: str,
        allow_interrupted: bool = False,
        max_iterations: Optional[int] = None,
        max_budget_usd: Optional[float] = None,
        timeout_minutes: Optional[int] = None,
        focus_hint: Optional[str] = None,
    ) -> Dict:
        """Explicit operator-controlled continuation for restart recovery."""
        parent = await self._store.get_session(parent_id)
        if not parent:
            raise RuntimeError(f"Parent session {parent_id} not found")
        allowed_statuses = {"resumable"}
        if allow_interrupted:
            allowed_statuses.add("interrupted")
        if parent["status"] not in allowed_statuses:
            expected = "/".join(sorted(allowed_statuses))
            raise RuntimeError(
                f"Runtime resume requires parent status {expected}, "
                f"got: {parent['status']}"
            )
        # Duplicate-resume guard: a previous recovery child that is still
        # live means this call is a double trigger, not a new recovery.
        for row in await self._store.list_sessions():
            child_status = str(row.get("status") or "")
            if (
                row.get("resumed_from") == parent_id
                and child_status not in _TERMINAL_STATUSES
            ):
                raise RuntimeError(
                    f"duplicate resume: recovery child "
                    f"{row.get('research_id')!r} of {parent_id!r} is "
                    f"still {child_status!r}; resume is refused until "
                    f"it settles"
                )
        session = await self.continue_session(
            parent_id,
            recovery_kind="restart_recovery",
            max_iterations=max_iterations,
            max_budget_usd=max_budget_usd,
            timeout_minutes=timeout_minutes,
            focus_hint=focus_hint or f"Runtime resume: {reason}",
        )
        await self._store.update_session(
            parent_id,
            error_message=(
                f"{parent.get('error_message') or ''}\n"
                f"Runtime resume requested: {reason}"
            ).strip(),
        )
        return session

    # ------------------------------------------------------------------
    # Pipeline sessions (ML-63)
    # ------------------------------------------------------------------

    async def stop_session(self, research_id: str) -> bool:
        """Request a graceful stop for a running session.

        ARC-011 P0-003: records the stop *intent* by writing the transitional
        ``stopping`` status through the state machine (``running|paused →
        stopping``) under the per-session lock, so a racing orchestrator
        completion is refused (the W8 fix — stop beats complete). The
        orchestrator's exit/CancelledError path owns the ``stopping →
        stopped`` finalize; this method only records intent, requests the
        flag, and drains the task. Against a higher-severity in-flight event
        (timing_out/failing) the intent is refused and we return False;
        against an already-terminal session the transition is an idempotent
        no-op.

        ARC-011 review C5 (P6-004 / H3): the DB intent is written BEFORE the
        local-registry check. Under ``WEB_CONCURRENCY > 1`` with a non-sticky
        load balancer the stop may be routed to a worker that does not own
        the session (its ``_active`` registry is empty) — the previous early
        return meant no intent was ever written, so the owning worker's
        ``_should_stop_cross_worker`` DB poll never fired (the ADR §6.2
        assumption "worker B writes the transition" was unreachable). Now
        any worker records ``stopping``; the owner observes it on its turn
        poll and finalizes. When this worker DOES own the session it
        additionally sets the in-process flag and drains the task (the fast
        path — no poll latency).
        """
        active = self._active.get(research_id)
        # Record stop intent so a racing `complete` is refused under the lock.
        # Against a terminal session the transition is an idempotent no-op
        # (``new_state`` stays terminal, ``changed`` is False) — detect that and
        # decline; against a higher-severity in-flight event (timing_out/failing)
        # it raises ``IllegalTransitionError``. Either way there is nothing to
        # stop. Only when we land in ``stopping`` do we set the flag and drain.
        try:
            result = await self._sm.transition(
                research_id, SessionEvent.STOP_REQUESTED,
            )
        except IllegalTransitionError:
            return False
        except LookupError:
            # Unknown session id — nothing to stop on any worker.
            return False
        if result.new_state is not SessionState.STOPPING:
            return False
        if active is not None:
            self._orchestrator.request_stop(research_id)
            await self._drain_or_cancel_task(
                active.task,
                label=f"research {research_id}",
                active_dict=self._active,
                active_key=research_id,
            )
        else:
            logger.info(
                "Stop intent recorded for research %s on a non-owning worker; "
                "the owning worker will observe the DB status and finalize",
                research_id,
            )
        logger.info("Stop requested for research %s", research_id)
        return True

    async def _drain_or_cancel_task(
        self,
        task: asyncio.Task,
        *,
        label: str,
        active_dict: Dict[str, Any],
        active_key: str,
        grace_s: float = 5.0,
    ) -> None:
        """Wait briefly for graceful stop, then cancel and free the active slot."""

        done, _ = await asyncio.wait({task}, timeout=grace_s)
        if done:
            return
        logger.warning("%s did not stop within %.1fs; cancelling", label, grace_s)
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=grace_s)
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            logger.error("%s cancellation did not drain within %.1fs", label, grace_s)
        finally:
            active_dict.pop(active_key, None)

    @staticmethod
    def _workspace_path_from_kwargs(kwargs: Dict[str, Any]) -> Optional[str]:
        instrument = kwargs.get("instrument")
        timeframe = kwargs.get("timeframe")
        model_type = kwargs.get("model_type") or ""
        if not instrument or not timeframe:
            return None
        # Mirror _start_session_unlocked's derivation (including the
        # skill-template path for non-ML sessions) so failed-start cleanup
        # targets the workspace that would have been created.
        if not model_type and not kwargs.get("skill_id"):
            return None
        return _derive_workspace_path(
            skill_id=kwargs.get("skill_id") or "",
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
        )

    async def _cleanup_failed_start_workspace(self, workspace_path: str) -> None:
        path = Path(workspace_path)
        if not path.exists():
            return
        try:
            await asyncio.to_thread(shutil.rmtree, str(path), ignore_errors=True)
            logger.warning("Cleaned workspace after failed session start: %s", path)
        except Exception:
            logger.exception("Failed to clean workspace after start failure: %s", path)

    async def pause_session(self, research_id: str) -> bool:
        # ARC-011 review C5 (P6-004 / H3): the DB transition is written before
        # the local-registry check, mirroring stop_session — a pause routed to
        # a non-owning worker records ``paused`` so the owning worker's
        # ``_wait_while_paused`` DB poll observes it (previously the early
        # return made cross-worker pause a silent no-op).
        active = self._active.get(research_id)
        # ARC-011 P0-003: route through the state machine. (running, pause) →
        # paused; illegal against a winding-down session (stopping/completing/
        # timing_out/failing) or terminal — return False so the API 404s
        # rather than clobber an in-flight terminal (pause sibling-of-W8).
        try:
            result = await self._sm.transition(research_id, SessionEvent.PAUSE)
        except IllegalTransitionError:
            return False
        except LookupError:
            return False
        if result.new_state is not SessionState.PAUSED:
            return False
        if active is not None:
            self._orchestrator.request_pause(research_id)
        else:
            logger.info(
                "Pause recorded for research %s on a non-owning worker; the "
                "owning worker will observe the DB status",
                research_id,
            )
        logger.info("Paused research %s", research_id)
        return True

    async def resume_session(self, research_id: str) -> bool:
        # ARC-011 review C5: same restructure — a cross-worker resume writes
        # ``running``; the owning worker's pause poll honors the authoritative
        # DB status (and refreshes its captured lock_epoch after the wait).
        active = self._active.get(research_id)
        # ARC-011 P0-003: (paused, resume) → running; illegal from any other
        # state (a winding-down or terminal session cannot resume).
        try:
            result = await self._sm.transition(research_id, SessionEvent.RESUME)
        except IllegalTransitionError:
            return False
        except LookupError:
            return False
        if result.new_state is not SessionState.RUNNING:
            return False
        if active is not None:
            self._orchestrator.request_resume(research_id)
        else:
            logger.info(
                "Resume recorded for research %s on a non-owning worker; the "
                "owning worker will observe the DB status",
                research_id,
            )
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
        for research_id, active in list(self._active.items()):
            await self._drain_or_cancel_task(
                active.task,
                label=f"research {research_id}",
                active_dict=self._active,
                active_key=research_id,
                grace_s=5.0,
            )
        for pipeline_id, task in list(self._active_pipelines.items()):
            await self._drain_or_cancel_task(
                task,
                label=f"pipeline {pipeline_id}",
                active_dict=self._active_pipelines,
                active_key=pipeline_id,
                grace_s=5.0,
            )
        logger.info("All sessions shut down")
