"""ML-63: Pipeline controller — orchestrates direction → volatility → rl in sequence."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config import settings
from src.core.config_promoter import ConfigPromoter
from src.core.gate_status import training_gates_passed_from_iteration
from src.core.results_store import ResultsStore
from src.ws.events import broadcaster

logger = logging.getLogger(__name__)

PHASES = ["direction", "volatility", "rl"]
DEFAULT_BUDGET_RATIOS = {"direction": 0.4, "volatility": 0.3, "rl": 0.3}
VALID_PHASES = set(PHASES)


def _promotion_blockers(
    preview: Optional[Dict[str, Any]],
    *,
    error: Optional[str] = None,
) -> list[str]:
    """Collect human-inspectable blockers from a ConfigPromoter preview."""
    blockers: list[str] = []

    def add(values: Any) -> None:
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            return
        for value in values:
            text = str(value).strip()
            if text and text not in blockers:
                blockers.append(text)

    if preview:
        add((preview.get("gate_bundle_evaluation") or {}).get("blockers"))
        add((preview.get("consistency_report") or {}).get("blockers"))
        add((preview.get("quality_baseline_evaluation") or {}).get("blockers"))
        add((preview.get("candidate_pool_record") or {}).get("blockers"))
        if (
            preview.get("training_gates_passed", preview.get("gates_passed"))
            is False
        ):
            add("best_iteration_failed_training_gates")
        if preview.get("promotion_allowed") is False and not blockers:
            add("promotion_not_allowed")
    if error:
        add(error)
    return blockers


def _promotion_preview_summary(
    preview: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Keep blocked-promotion diagnostics inspectable without storing configs."""
    if not preview:
        return None
    return {
        "research_id": preview.get("research_id"),
        "iteration": preview.get("iteration"),
        "model_type": preview.get("model_type"),
        "instrument": preview.get("instrument"),
        "timeframe": preview.get("timeframe"),
        "target_path": preview.get("target_path"),
        "best_metric": preview.get("best_metric"),
        "training_gates_passed": preview.get("training_gates_passed"),
        "gates_passed": preview.get("gates_passed"),
        "development_gate_bundle_passed": preview.get(
            "development_gate_bundle_passed"
        ),
        "consistency_report_passed": preview.get("consistency_report_passed"),
        "promotion_allowed": preview.get("promotion_allowed"),
        "config_snapshot_sha256": preview.get("config_snapshot_sha256"),
        "gate_bundle_evaluation": preview.get("gate_bundle_evaluation"),
        "candidate_pool_record": preview.get("candidate_pool_record"),
        "best_candidate_ownership": preview.get("best_candidate_ownership"),
        "consistency_report": preview.get("consistency_report"),
        "quality_baseline_evaluation": preview.get("quality_baseline_evaluation"),
        "development_promotion_metadata": preview.get(
            "development_promotion_metadata"
        ),
    }


class PipelinePromotionBlocked(RuntimeError):
    """Raised when a phase trains successfully but promotion gates block it."""

    def __init__(
        self,
        *,
        phase: str,
        session_id: str,
        preview: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        self.phase = phase
        self.session_id = session_id
        self.preview = preview or {}
        self.error = error
        self.blockers = _promotion_blockers(self.preview, error=error)
        detail = ", ".join(self.blockers) if self.blockers else "unknown"
        super().__init__(f"{phase} promotion blocked: {detail}")


class PipelineConfig:
    """Configuration for a pipeline run."""

    def __init__(
        self,
        *,
        id: str,
        instrument: str,
        timeframe: str,
        tag: str = "",
        quick_mode: bool = False,
        max_iterations: int = 30,
        max_budget_usd: float = 30.0,
        timeout_s: int = 0,
        focus_hint: Optional[str] = None,
        phase_budgets: Optional[Dict[str, int]] = None,
        completed_phases: Optional[List[str]] = None,
        trading_mode: Optional[str] = None,
        agent_strategy: Optional[str] = None,
        initial_balance: Optional[float] = None,
        enable_hpo: bool = False,
        hpo_trials: int = 20,
        hpo_timesteps: int = 50000,
    ):
        self.id = id
        self.instrument = instrument
        self.timeframe = timeframe
        self.tag = tag
        self.quick_mode = quick_mode
        self.max_iterations = max_iterations
        self.max_budget_usd = max_budget_usd
        self.timeout_s = timeout_s
        self.focus_hint = focus_hint
        self.phase_budgets = self._validate_phase_budgets(phase_budgets)
        self.completed_phases = completed_phases or []
        self.trading_mode = trading_mode
        self.agent_strategy = agent_strategy
        self.initial_balance = initial_balance
        self.enable_hpo = enable_hpo
        self.hpo_trials = hpo_trials
        self.hpo_timesteps = hpo_timesteps

    @staticmethod
    def _validate_phase_budgets(
        phase_budgets: Optional[Dict[str, int]],
    ) -> Optional[Dict[str, int]]:
        if phase_budgets is None:
            return None
        unknown = sorted(set(phase_budgets) - VALID_PHASES)
        if unknown:
            raise ValueError(f"Unknown phase budget keys: {', '.join(unknown)}")
        invalid = {
            phase: budget
            for phase, budget in phase_budgets.items()
            if not isinstance(budget, (int, float)) or int(budget) < 1
        }
        if invalid:
            raise ValueError("phase_budgets values must be integers >= 1")
        return {phase: int(budget) for phase, budget in phase_budgets.items()}


class PipelineController:
    """Orchestrates sequential direction → volatility → rl research."""

    def __init__(self, store: ResultsStore, session_manager) -> None:
        self._store = store
        self._sm = session_manager
        self._stop_flags: Dict[str, bool] = {}

    def request_stop(self, pipeline_id: str) -> None:
        self._stop_flags[pipeline_id] = True

    def _should_stop(self, pipeline_id: str) -> bool:
        return self._stop_flags.get(pipeline_id, False)

    def _compute_phase_budgets(self, config: PipelineConfig) -> Dict[str, int]:
        if config.phase_budgets:
            return config.phase_budgets
        total = config.max_iterations
        return {
            phase: max(2, int(total * ratio))
            for phase, ratio in DEFAULT_BUDGET_RATIOS.items()
        }

    def _compute_phase_budget_usd(self, config: PipelineConfig) -> Dict[str, float]:
        total = config.max_budget_usd
        return {
            phase: total * ratio
            for phase, ratio in DEFAULT_BUDGET_RATIOS.items()
        }

    async def run(self, config: PipelineConfig) -> None:
        """Run the full pipeline: direction → volatility → enrich → rl."""
        pipeline_id = config.id
        start_time = time.monotonic()
        budgets = self._compute_phase_budgets(config)
        budget_usd = self._compute_phase_budget_usd(config)
        completed_phases = list(config.completed_phases)

        try:
            for phase in PHASES:
                if phase in completed_phases:
                    logger.info(
                        "Pipeline %s: skipping completed phase %s",
                        pipeline_id, phase,
                    )
                    continue

                if self._should_stop(pipeline_id):
                    await self._store.update_pipeline(
                        pipeline_id,
                        status="stopped",
                        completed_at=datetime.now(timezone.utc).isoformat(),
                    )
                    return

                # Check pipeline-level timeout
                elapsed = time.monotonic() - start_time
                _timeout = (
                    config.timeout_s
                    if config.timeout_s > 0
                    else settings.experiment_timeout_s * 3
                )
                if elapsed > _timeout:
                    await self._store.update_pipeline(
                        pipeline_id,
                        status="timed_out",
                        completed_phases=json.dumps(completed_phases),
                        completed_at=datetime.now(timezone.utc).isoformat(),
                    )
                    return

                # Update pipeline phase
                await self._store.update_pipeline(
                    pipeline_id, current_phase=phase,
                )
                await broadcaster.broadcast({
                    "event": "pipeline_phase_started",
                    "pipeline_id": pipeline_id,
                    "phase": phase,
                })

                # Pre-RL: enrichment step
                if phase == "rl":
                    await self._store.update_pipeline(
                        pipeline_id, current_phase="enrichment",
                    )
                    await self._run_enrichment(
                        config,
                        timeout_s=max(60.0, _timeout - elapsed),
                    )
                    await self._store.update_pipeline(
                        pipeline_id, current_phase="rl",
                    )

                # Compute per-phase timeout from remaining pipeline time
                remaining_phases = len(
                    [p for p in PHASES if p not in completed_phases]
                )
                phase_timeout_m = max(
                    30,
                    int((_timeout - elapsed) / max(remaining_phases, 1) / 60),
                )

                # Spawn sub-session for this phase
                session_dict = await self._start_phase(
                    config, phase, budgets.get(phase, 10), phase_timeout_m,
                    phase_budget_usd=budget_usd.get(phase, config.max_budget_usd / 3),
                )
                session_id = session_dict["id"]

                # Store child session ID on pipeline
                await self._store.update_pipeline(
                    pipeline_id,
                    **{f"{phase}_session_id": session_id},
                )

                # Wait for sub-session to finish
                await self._wait_for_session(
                    session_id, deadline=start_time + _timeout,
                )

                # Evaluate phase: did any iteration pass training gates?
                phase_passed = await self._evaluate_phase(session_id)

                if phase_passed:
                    try:
                        promotion, preview = await self._promote_phase(
                            session_id, phase,
                        )
                    except PipelinePromotionBlocked as exc:
                        await self._safe_mark_promotion_blocked(
                            pipeline_id=pipeline_id,
                            phase=phase,
                            session_id=session_id,
                            completed_phases=completed_phases,
                            exc=exc,
                        )
                        return

                    completed_phases.append(phase)
                    await self._store.update_pipeline(
                        pipeline_id,
                        completed_phases=json.dumps(completed_phases),
                        promotion_blocked_phase=None,
                        promotion_blockers_json=None,
                        promotion_preview_json=json.dumps(
                            _promotion_preview_summary(preview),
                            sort_keys=True,
                        ),
                    )
                    await broadcaster.broadcast({
                        "event": "pipeline_phase_completed",
                        "pipeline_id": pipeline_id,
                        "phase": phase,
                        "passed": True,
                        "session_id": session_id,
                        "promotion_id": promotion.get("id"),
                        "metadata_path": promotion.get("metadata_path"),
                    })
                    logger.info(
                        "Pipeline %s: phase %s completed + promoted",
                        pipeline_id, phase,
                    )
                else:
                    # Phase failed — stop pipeline
                    await self._store.update_pipeline(
                        pipeline_id,
                        status="phase_failed",
                        current_phase=phase,
                        completed_phases=json.dumps(completed_phases),
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        error_message=(
                            f"{phase} phase: no iteration passed training gates"
                        ),
                    )
                    await broadcaster.broadcast({
                        "event": "pipeline_phase_completed",
                        "pipeline_id": pipeline_id,
                        "phase": phase,
                        "passed": False,
                        "session_id": session_id,
                    })
                    logger.warning(
                        "Pipeline %s: phase %s failed gates — stopping",
                        pipeline_id, phase,
                    )
                    return

            # All phases completed successfully
            await self._store.update_pipeline(
                pipeline_id,
                status="completed",
                current_phase=None,
                completed_phases=json.dumps(completed_phases),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            await broadcaster.broadcast({
                "event": "pipeline_completed",
                "pipeline_id": pipeline_id,
                "status": "completed",
            })
            logger.info("Pipeline %s: all phases completed", pipeline_id)

        except asyncio.CancelledError:
            await self._store.update_pipeline(
                pipeline_id,
                status="stopped",
                completed_phases=json.dumps(completed_phases),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            raise

        except Exception as exc:
            logger.exception("Pipeline %s failed: %s", pipeline_id, exc)
            await self._store.update_pipeline(
                pipeline_id,
                status="failed",
                completed_phases=json.dumps(completed_phases),
                completed_at=datetime.now(timezone.utc).isoformat(),
                error_message=str(exc)[:2000],
            )

        finally:
            self._stop_flags.pop(pipeline_id, None)

    async def _start_phase(
        self,
        config: PipelineConfig,
        phase: str,
        phase_budget: int,
        phase_timeout_m: int,
        *,
        phase_budget_usd: float,
    ) -> Dict[str, Any]:
        """Start a single phase as a research sub-session."""
        is_rl = phase == "rl"
        return await self._sm.start_phase_session(
            instrument=config.instrument,
            timeframe=config.timeframe,
            model_type=phase,
            tag=f"pipe-{config.id[-8:]}-{phase[:3]}",
            quick_mode=config.quick_mode,
            max_iterations=phase_budget,
            max_budget_usd=phase_budget_usd,
            timeout_minutes=phase_timeout_m,
            focus_hint=config.focus_hint,
            pipeline_id=config.id,
            trading_mode=config.trading_mode if is_rl else None,
            agent_strategy=config.agent_strategy if is_rl else None,
            initial_balance=config.initial_balance if is_rl else None,
            enable_hpo=config.enable_hpo if is_rl else False,
            hpo_trials=config.hpo_trials if is_rl else None,
            hpo_timesteps=config.hpo_timesteps if is_rl else None,
        )

    async def _wait_for_session(self, session_id: str, *, deadline: float) -> None:
        """Poll until a session is no longer running or the deadline is exceeded."""
        while True:
            if not self._sm.is_running(session_id):
                return
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"Timed out waiting for phase session {session_id} to finish"
                )
            await asyncio.sleep(10)

    async def _evaluate_phase(self, session_id: str) -> bool:
        """Check if any iteration of a phase passed training gates."""
        iterations = await self._store.get_iterations(session_id)
        return any(training_gates_passed_from_iteration(it) for it in iterations)

    async def _promote_phase(
        self, session_id: str, phase: str,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Promote a completed phase through the audited ConfigPromoter path."""
        promoter = ConfigPromoter(self._store)
        preview: Optional[Dict[str, Any]] = None
        try:
            preview = await promoter.preview(session_id)
            if preview.get("promotion_allowed") is not True:
                raise PipelinePromotionBlocked(
                    phase=phase,
                    session_id=session_id,
                    preview=preview,
                )
            promotion = await promoter.confirm(session_id)
        except PipelinePromotionBlocked:
            raise
        except Exception as exc:
            raise PipelinePromotionBlocked(
                phase=phase,
                session_id=session_id,
                preview=preview,
                error=str(exc),
            ) from exc

        if not promotion.get("id"):
            raise PipelinePromotionBlocked(
                phase=phase,
                session_id=session_id,
                preview=preview,
                error="promotion_record_missing",
            )
        return promotion, preview or {}

    async def _mark_promotion_blocked(
        self,
        *,
        pipeline_id: str,
        phase: str,
        session_id: str,
        completed_phases: List[str],
        exc: PipelinePromotionBlocked,
    ) -> None:
        blocked_payload = {
            "schema_version": "pipeline_promotion_blocked.v1",
            "pipeline_id": pipeline_id,
            "phase": phase,
            "session_id": session_id,
            "blockers": exc.blockers,
            "error": exc.error,
            "preview": _promotion_preview_summary(exc.preview),
        }
        await self._store.update_pipeline(
            pipeline_id,
            status="promotion_blocked",
            current_phase=phase,
            completed_phases=json.dumps(completed_phases),
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=str(exc)[:2000],
            promotion_blocked_phase=phase,
            promotion_blockers_json=json.dumps(exc.blockers, sort_keys=True),
            promotion_preview_json=json.dumps(blocked_payload, sort_keys=True),
        )
        await broadcaster.broadcast({
            "event": "pipeline_promotion_blocked",
            "pipeline_id": pipeline_id,
            "phase": phase,
            "session_id": session_id,
            "blockers": exc.blockers,
            "error": exc.error,
        })
        logger.warning(
            "Pipeline %s: phase %s promotion blocked: %s",
            pipeline_id, phase, ", ".join(exc.blockers) or exc.error or "unknown",
        )

    async def _safe_mark_promotion_blocked(
        self,
        *,
        pipeline_id: str,
        phase: str,
        session_id: str,
        completed_phases: List[str],
        exc: PipelinePromotionBlocked,
    ) -> None:
        try:
            await self._mark_promotion_blocked(
                pipeline_id=pipeline_id,
                phase=phase,
                session_id=session_id,
                completed_phases=completed_phases,
                exc=exc,
            )
        except Exception as persist_exc:
            logger.exception(
                "Pipeline %s: failed to persist promotion_blocked state — "
                "falling back to promotion_blocked with error detail",
                pipeline_id,
            )
            await self._store.update_pipeline(
                pipeline_id,
                status="promotion_blocked",
                current_phase=phase,
                completed_phases=json.dumps(completed_phases),
                completed_at=datetime.now(timezone.utc).isoformat(),
                error_message=(
                    "promotion_blocked (persistence error): "
                    f"{persist_exc}"
                )[:2000],
                promotion_blocked_phase=phase,
                promotion_blockers_json=json.dumps(
                    ["persistence_failed"],
                    sort_keys=True,
                ),
                promotion_preview_json=json.dumps(
                    {
                        "schema_version": "pipeline_promotion_blocked.v1",
                        "pipeline_id": pipeline_id,
                        "phase": phase,
                        "session_id": session_id,
                        "reason": "persistence_failed",
                    },
                    sort_keys=True,
                ),
            )

    async def _run_enrichment(
        self, config: PipelineConfig, *, timeout_s: float
    ) -> None:
        """Run enrich_rl_dataset.py between volatility and rl phases."""
        instrument = config.instrument.replace("-", "_")
        cmd = [
            settings.venv_python,
            f"{settings.autotuner_scripts_dir}/enrich_rl_dataset.py",
            "--instrument", instrument,
            "--timeframe", config.timeframe,
        ]
        logger.info(
            "Pipeline %s: running RL enrichment for %s_%s",
            config.id, instrument, config.timeframe,
        )
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=settings.workspace_root,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_s
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError(
                f"RL enrichment timed out after {timeout_s:.0f}s"
            )
        if proc.returncode == 0:
            logger.info(
                "Pipeline %s: enrichment completed for %s_%s",
                config.id, instrument, config.timeframe,
            )
        else:
            raise RuntimeError(
                f"RL enrichment failed (rc={proc.returncode}): "
                f"{stderr.decode()[:500]}"
            )
