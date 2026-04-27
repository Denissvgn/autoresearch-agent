"""Config promoter — previews and writes winning configs to the host bind mount."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import yaml

from server.config import settings
from server.core.development_gate_bundle import (
    evaluate_development_gate_bundle,
    load_gate_bundle,
)
from server.core.development_inference_validation import (
    build_development_inference_validation,
)
from server.core.development_signal_health import build_development_signal_health
from server.core.results_store import ResultsStore

logger = logging.getLogger(__name__)

DEVELOPMENT_PROMOTION_METADATA_VERSION = "development_promotion_metadata.v1"
DEVELOPMENT_PROMOTION_SCOPE = "development"


class ConfigPromoter:
    """Handles preview and confirmation of config promotion to host."""

    def __init__(self, store: ResultsStore) -> None:
        self._store = store

    async def preview(self, research_id: str) -> Dict[str, Any]:
        """Dry-run promotion: returns the diff/preview without writing."""
        session = await self._store.get_session(research_id)
        if not session:
            raise ValueError(f"Session {research_id} not found")

        best = await self._store.get_best_iteration(research_id)
        if not best:
            raise ValueError(f"No winning iteration found for {research_id}")

        workspace_path = session["workspace_path"]
        model_type = session["model_type"]
        instrument = session["instrument"]
        timeframe = session["timeframe"]

        # Use the immutable config snapshot stored in the DB — not the
        # mutable workspace best_train.yaml which can diverge from the DB
        # best iteration when the agent mismanages checkpoints.
        config_snapshot = best.get("config_snapshot")
        if not config_snapshot:
            raise ValueError(
                f"Iteration {best['iteration']} for session {research_id} "
                f"has no stored config snapshot. Re-run a session with the "
                f"updated orchestrator to generate per-iteration snapshots."
            )
        best_yaml = config_snapshot
        config_snapshot_sha256 = self._sha256_text(best_yaml)

        # Determine target path on host (ML-67: extract strategy+market from config)
        _strategy, _market = self._extract_strategy_market(best_yaml)
        target_path = self._get_target_path(
            model_type, instrument, timeframe,
            strategy=_strategy, market_type=_market,
        )

        # Read current config if it exists
        previous_yaml: Optional[str] = None
        if os.path.exists(target_path):
            previous_yaml = Path(target_path).read_text(encoding="utf-8")

        metrics_payload = self._best_iteration_payload(best)
        attempt_snapshot = self._attempt_snapshot_payload(best, metrics_payload)
        artifact_hash = (
            attempt_snapshot.get("artifact_hash")
            or metrics_payload.get("artifact_hash")
            or metrics_payload.get("model_artifact_hash")
        )
        rollback_readiness = self._build_rollback_readiness(
            research_id=research_id,
            iteration=best["iteration"],
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
            target_path=target_path,
            previous_yaml=previous_yaml,
            metrics_payload=metrics_payload,
        )
        smoke_validation = self._build_smoke_validation(
            best_yaml=best_yaml,
            metrics_payload=metrics_payload,
            rollback_readiness=rollback_readiness,
        )
        signal_health = build_development_signal_health(metrics_payload)
        inference_reload_validation = build_development_inference_validation(
            metrics_payload=metrics_payload,
            rollback_readiness=rollback_readiness,
            smoke_validation=smoke_validation,
        )
        best_for_gate = self._best_iteration_with_preflight(
            best,
            rollback_readiness=rollback_readiness,
            smoke_validation=smoke_validation,
            signal_health=signal_health,
            inference_reload_validation=inference_reload_validation,
        )
        gate_bundle_evaluation = self._evaluate_gate_bundle(
            model_type, best_for_gate,
        )
        promotion_allowed = bool(best["all_gates_passed"]) and gate_bundle_evaluation.get(
            "passed",
            False,
        )
        candidate_pool_record = {
            "source": "autoresearch.iterations",
            "research_id": research_id,
            "iteration": best["iteration"],
            "iteration_row_id": best.get("id"),
            "config_snapshot_sha256": config_snapshot_sha256,
            "attempt_snapshot_hash": (
                best.get("attempt_snapshot_hash")
                or attempt_snapshot.get("snapshot_hash")
            ),
            "attempt_snapshot_path": best.get("attempt_snapshot_path"),
            "artifact_hash": artifact_hash,
            "status": "eligible" if promotion_allowed else "blocked",
            "blockers": gate_bundle_evaluation.get("blockers", []),
            "inspectable": True,
            "promotion_record_created": False,
        }
        development_promotion_metadata = self._build_development_promotion_metadata(
            research_id=research_id,
            iteration=best["iteration"],
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
            target_path=target_path,
            best_iteration=best,
            metrics_payload=metrics_payload,
            gates_passed=bool(best["all_gates_passed"]),
            gate_bundle_evaluation=gate_bundle_evaluation,
            candidate_pool_record=candidate_pool_record,
            promotion_allowed=promotion_allowed,
            rollback_readiness=rollback_readiness,
            smoke_validation=smoke_validation,
            signal_health=signal_health,
            inference_reload_validation=inference_reload_validation,
        )

        return {
            "research_id": research_id,
            "iteration": best["iteration"],
            "model_type": model_type,
            "instrument": instrument,
            "timeframe": timeframe,
            "target_path": target_path,
            "new_config": best_yaml,
            "config_snapshot_sha256": config_snapshot_sha256,
            "current_config": previous_yaml,
            "best_metric": best["primary_metric"],
            "gates_passed": bool(best["all_gates_passed"]),
            "gate_bundle_evaluation": gate_bundle_evaluation,
            "candidate_pool_record": candidate_pool_record,
            "best_candidate_ownership": development_promotion_metadata[
                "best_candidate_ownership"
            ],
            "development_promotion_metadata": development_promotion_metadata,
            "promotion_allowed": promotion_allowed,
        }

    async def confirm(self, research_id: str) -> Dict[str, Any]:
        """Execute the promotion: write best config to host bind mount."""
        preview = await self.preview(research_id)

        if not preview["gates_passed"]:
            raise ValueError(
                "Cannot promote: best iteration did not pass all gates"
            )
        gate_eval = preview.get("gate_bundle_evaluation") or {}
        if not gate_eval.get("passed", False):
            blockers = ", ".join(gate_eval.get("blockers") or ["unknown"])
            raise ValueError(
                "Cannot promote: development gate bundle failed "
                f"({blockers})"
            )
        metadata = dict(preview.get("development_promotion_metadata") or {})
        if metadata.get("scope") != DEVELOPMENT_PROMOTION_SCOPE:
            raise ValueError(
                "Cannot promote: development promotion metadata is not scoped "
                f"to {DEVELOPMENT_PROMOTION_SCOPE}"
            )
        if metadata.get("live_production_promotion_requested") is True:
            raise ValueError(
                "Cannot promote: live production promotion is forbidden by "
                "the development gate policy"
            )
        reload_validation = metadata.get("inference_reload_validation") or {}
        reload_gate_required = any(
            str(check.get("name", "")).startswith("inference_reload")
            for check in gate_eval.get("checks", [])
            if isinstance(check, dict)
        )
        if (
            reload_gate_required
            and reload_validation
            and reload_validation.get("passed") is not True
        ):
            failed = ", ".join(reload_validation.get("failed_checks") or ["unknown"])
            raise ValueError(
                "Cannot promote: inference reload validation failed "
                f"({failed})"
            )

        target_path = preview["target_path"]
        model_type = preview["model_type"]
        instrument = preview["instrument"]
        timeframe = preview["timeframe"]
        session = await self._store.get_session(research_id)
        workspace_path = session["workspace_path"]

        # Extract model metadata from best iteration for composite update
        best = await self._store.get_best_iteration(research_id)
        mlflow_run_id: Optional[str] = None
        model_version: Optional[str] = None
        model_registry_name: Optional[str] = None
        metric_name: Optional[str] = None
        metric_value: Optional[float] = None
        if best:
            mlflow_run_id = best.get("mlflow_run_id")
            metric_name = best.get("metric_name")
            metric_value = best.get("primary_metric")
            metrics_raw = best.get("metrics_json")
            if metrics_raw:
                try:
                    metrics = json.loads(metrics_raw) if isinstance(metrics_raw, str) else metrics_raw
                    mlflow_run_id = mlflow_run_id or metrics.get("mlflow_run_id")
                    model_version = metrics.get("model_version")
                    model_registry_name = metrics.get("model_registry_name")
                except (json.JSONDecodeError, TypeError):
                    pass

        rollback_readiness = dict(metadata.get("rollback_readiness") or {})
        previous_yaml = preview.get("current_config")
        if previous_yaml is not None:
            rollback_snapshot_path = rollback_readiness.get(
                "previous_config_snapshot_path"
            ) or self._rollback_snapshot_path(
                target_path=target_path,
                research_id=research_id,
                iteration=preview["iteration"],
            )
            await self._write_text_file(rollback_snapshot_path, previous_yaml)
            rollback_readiness.update(
                {
                    "previous_config_snapshot_path": rollback_snapshot_path,
                    "previous_development_version_addressable": True,
                    "rollback_target": rollback_snapshot_path,
                    "previous_config_sha256": self._sha256_text(previous_yaml),
                }
            )
            metadata["rollback_target"] = rollback_snapshot_path
            metadata["rollback_readiness"] = rollback_readiness

        # Use promote.py script if available, otherwise write directly
        promote_script = os.path.join(
            settings.autotuner_scripts_dir, "promote.py",
        )
        if os.path.exists(promote_script):
            # Write the DB config snapshot to a versioned, immutable path
            # so promote.py reads the server-confirmed config and never
            # touches the mutable workspace best_train.yaml.
            snap_filename = f"snapshot_iter_{preview['iteration']}.yaml"
            snap_path = os.path.join(workspace_path, snap_filename)
            await asyncio.to_thread(
                Path(snap_path).write_text,
                preview["new_config"],
                encoding="utf-8",
            )

            cmd = [
                settings.venv_python,
                promote_script,
                "--model", model_type,
                "--workspace", os.path.dirname(workspace_path),
                "--instrument", instrument,
                "--timeframe", timeframe,
                "--configs-dir", settings.host_configs_path,
                "--config-file", snap_path,
            ]
            if mlflow_run_id:
                cmd.extend(["--mlflow-run-id", mlflow_run_id])
            if metric_name:
                cmd.extend(["--metric-name", metric_name])
            if metric_value is not None:
                cmd.extend(["--metric-value", str(metric_value)])
            # ML-64: Pass model artifacts dir for stable model persistence
            artifacts_dir = self._resolve_artifacts_dir(
                workspace_path, model_type, instrument, timeframe,
            )
            if artifacts_dir:
                cmd.extend(["--model-artifacts-dir", artifacts_dir])
            cmd.extend([
                "--stable-models-dir",
                os.path.join(settings.workspace_root, "runs", "promoted_models"),
            ])
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                cwd=settings.workspace_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"promote.py failed (exit {result.returncode}): {result.stderr}"
                )
            logger.info("promote.py succeeded: %s", result.stdout[:500])
        else:
            # Direct write fallback
            await asyncio.to_thread(os.makedirs, os.path.dirname(target_path), exist_ok=True)
            await asyncio.to_thread(
                Path(target_path).write_text, preview["new_config"], encoding="utf-8",
            )
            logger.info("Wrote promoted config to %s", target_path)

        metadata_path = self._metadata_sidecar_path(target_path, preview["iteration"])
        metadata = self._finalize_development_promotion_metadata(
            metadata=metadata,
            metadata_path=metadata_path,
            promotion_record_created=True,
        )
        await asyncio.to_thread(
            os.makedirs, os.path.dirname(metadata_path), exist_ok=True
        )
        await asyncio.to_thread(
            Path(metadata_path).write_text,
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        # Record promotion
        promotion = await self._store.record_promotion(
            research_id=research_id,
            iteration=preview["iteration"],
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
            target_path=target_path,
            config_yaml=preview["new_config"],
            previous_yaml=preview["current_config"],
            scope=DEVELOPMENT_PROMOTION_SCOPE,
            metadata_path=metadata_path,
            promotion_metadata=metadata,
        )

        # ML-52: Update composite model versions in mlflow-service
        if model_registry_name and model_version:
            version_tag = f"{model_registry_name}:{model_version}"
            await self._update_composite_versions(
                instrument=instrument,
                model_type=model_type,
                version_tag=version_tag,
            )

        return promotion

    async def rollback(
        self,
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Restore the latest development promotion for an instrument/timeframe."""
        get_latest = getattr(
            self._store, "get_latest_development_promotion", None
        )
        if get_latest is None:
            raise ValueError("Promotion store does not support rollback lookup")
        promotion = await get_latest(
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
        )
        if not promotion:
            raise ValueError(
                "No development promotion found for "
                f"{model_type} {instrument}/{timeframe}"
            )

        previous_yaml = promotion.get("previous_yaml")
        promotion_metadata = promotion.get("promotion_metadata") or {}
        rollback_readiness = promotion_metadata.get("rollback_readiness") or {}
        snapshot_path = rollback_readiness.get("previous_config_snapshot_path")
        if previous_yaml is None and snapshot_path and os.path.exists(snapshot_path):
            previous_yaml = Path(snapshot_path).read_text(encoding="utf-8")
        if previous_yaml is None:
            raise ValueError(
                "Latest development promotion has no previous config snapshot "
                "to restore"
            )

        target_path = promotion["target_path"]
        current_yaml = (
            Path(target_path).read_text(encoding="utf-8")
            if os.path.exists(target_path)
            else None
        )
        await self._write_text_file(target_path, previous_yaml)

        rollback_metadata_path = self._rollback_metadata_sidecar_path(
            target_path, promotion["id"]
        )
        rollback_metadata = {
            "schema_version": "development_promotion_rollback.v1",
            "scope": DEVELOPMENT_PROMOTION_SCOPE,
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            "promotion_id": promotion["id"],
            "research_id": promotion["research_id"],
            "iteration": promotion["iteration"],
            "model_type": model_type,
            "instrument": instrument,
            "timeframe": timeframe,
            "target_path": target_path,
            "reason": reason,
            "restored_config_sha256": self._sha256_text(previous_yaml),
            "replaced_config_sha256": (
                self._sha256_text(current_yaml) if current_yaml is not None else None
            ),
            "previous_config_snapshot_path": snapshot_path,
            "rollback_method": "instrument_timeframe_development_config",
        }
        await self._write_text_file(
            rollback_metadata_path,
            json.dumps(rollback_metadata, indent=2, sort_keys=True) + "\n",
        )

        record_rollback = getattr(self._store, "record_promotion_rollback", None)
        if record_rollback is not None:
            await record_rollback(
                promotion_id=promotion["id"],
                rollback_metadata_path=rollback_metadata_path,
                rollback_metadata=rollback_metadata,
            )

        return {
            "rolled_back": True,
            "promotion_id": promotion["id"],
            "model_type": model_type,
            "instrument": instrument,
            "timeframe": timeframe,
            "target_path": target_path,
            "rollback_metadata_path": rollback_metadata_path,
            "rollback_metadata": rollback_metadata,
        }

    def _build_development_promotion_metadata(
        self,
        *,
        research_id: str,
        iteration: int,
        model_type: str,
        instrument: str,
        timeframe: str,
        target_path: str,
        best_iteration: Dict[str, Any],
        metrics_payload: Dict[str, Any],
        gates_passed: bool,
        gate_bundle_evaluation: Dict[str, Any],
        candidate_pool_record: Dict[str, Any],
        promotion_allowed: bool,
        rollback_readiness: Dict[str, Any],
        smoke_validation: Dict[str, Any],
        signal_health: Dict[str, Any],
        inference_reload_validation: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create the auditable development promotion decision artifact."""
        rollback_target = (
            rollback_readiness.get("rollback_target")
            or metrics_payload.get("rollback_target")
            or metrics_payload.get("previous_development_version")
        )
        attempt_snapshot = self._attempt_snapshot_payload(
            best_iteration, metrics_payload
        )
        config_snapshot = best_iteration.get("config_snapshot") or ""
        config_snapshot_sha256 = (
            self._sha256_text(config_snapshot) if config_snapshot else None
        )
        best_candidate_ownership = {
            "source": "autoresearch.iterations",
            "research_id": research_id,
            "iteration": iteration,
            "iteration_row_id": best_iteration.get("id"),
            "config_snapshot_sha256": config_snapshot_sha256,
            "attempt_snapshot_hash": (
                best_iteration.get("attempt_snapshot_hash")
                or attempt_snapshot.get("snapshot_hash")
            ),
            "attempt_snapshot_path": best_iteration.get("attempt_snapshot_path"),
            "artifact_hash": (
                attempt_snapshot.get("artifact_hash")
                or metrics_payload.get("artifact_hash")
                or metrics_payload.get("model_artifact_hash")
            ),
            "mlflow_run_id": (
                best_iteration.get("mlflow_run_id")
                or metrics_payload.get("mlflow_run_id")
            ),
        }
        return {
            "schema_version": DEVELOPMENT_PROMOTION_METADATA_VERSION,
            "scope": DEVELOPMENT_PROMOTION_SCOPE,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "research_id": research_id,
            "iteration": iteration,
            "model_type": model_type,
            "instrument": instrument,
            "timeframe": timeframe,
            "target_path": target_path,
            "best_metric": best_iteration.get("primary_metric"),
            "metric_name": best_iteration.get("metric_name"),
            "gates_passed": gates_passed,
            "promotion_allowed": promotion_allowed,
            "live_production_promotion_allowed": False,
            "live_production_promotion_requested": self._live_production_requested(
                metrics_payload
            ),
            "gate_bundle": {
                "gate_bundle_id": gate_bundle_evaluation.get("gate_bundle_id"),
                "version": gate_bundle_evaluation.get("version"),
                "scope": gate_bundle_evaluation.get("scope") or DEVELOPMENT_PROMOTION_SCOPE,
                "passed": gate_bundle_evaluation.get("passed"),
                "blockers": gate_bundle_evaluation.get("blockers", []),
                "checks": gate_bundle_evaluation.get("checks", []),
                "waivers": gate_bundle_evaluation.get("waivers", []),
            },
            "best_candidate_ownership": best_candidate_ownership,
            "candidate_pool_record": dict(candidate_pool_record),
            "decision_record": {
                "model_quality": self._check_statuses(
                    gate_bundle_evaluation,
                    "direction_quality",
                    "min_direction_auc",
                    "max_signal_rate",
                ),
                "calibration": self._check_statuses(
                    gate_bundle_evaluation,
                    "calibration",
                    "max_ece",
                    "ece",
                    "brier",
                    "reliability",
                    "threshold",
                    "signal_rate",
                    "per_regime",
                ),
                "economic_replay": self._check_statuses(
                    gate_bundle_evaluation, "economic_replay"
                ),
                "rl_oos": self._check_statuses(gate_bundle_evaluation, "rl_"),
                "inference_parity": self._check_statuses(
                    gate_bundle_evaluation, "inference_"
                ),
                "rollback": self._check_statuses(
                    gate_bundle_evaluation, "rollback"
                ),
                "smoke_validation": self._check_statuses(
                    gate_bundle_evaluation, "smoke"
                ),
                "signal_health": self._check_statuses(
                    gate_bundle_evaluation, "signal_health"
                ),
                "inference_reload": self._check_statuses(
                    gate_bundle_evaluation, "inference_reload"
                ),
            },
            "registry_metadata": self._registry_metadata(
                best_iteration, metrics_payload
            ),
            "composite_metadata": self._composite_metadata(metrics_payload),
            "rollback_target": (
                rollback_target
            ),
            "rollback_readiness": dict(rollback_readiness),
            "smoke_validation": dict(smoke_validation),
            "signal_health": dict(signal_health),
            "inference_reload_validation": dict(inference_reload_validation),
            "tsfm_fallback_validation": self._tsfm_fallback_validation(
                metrics_payload
            ),
        }

    def _finalize_development_promotion_metadata(
        self,
        *,
        metadata: Dict[str, Any],
        metadata_path: str,
        promotion_record_created: bool,
    ) -> Dict[str, Any]:
        finalized = dict(metadata)
        finalized["metadata_path"] = metadata_path
        finalized["promotion_record_created"] = promotion_record_created
        candidate_pool = dict(finalized.get("candidate_pool_record") or {})
        candidate_pool["promotion_record_created"] = promotion_record_created
        finalized["candidate_pool_record"] = candidate_pool
        return finalized

    @staticmethod
    def _best_iteration_payload(best_iteration: Dict[str, Any]) -> Dict[str, Any]:
        raw = best_iteration.get("metrics_json")
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def _attempt_snapshot_payload(
        best_iteration: Dict[str, Any],
        metrics_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        raw = best_iteration.get("attempt_snapshot_json")
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                return parsed
        if isinstance(raw, dict):
            return raw
        embedded = metrics_payload.get("attempt_snapshot")
        return embedded if isinstance(embedded, dict) else {}

    @staticmethod
    def _live_production_requested(payload: Dict[str, Any]) -> bool:
        request = payload.get("promotion_request") or payload.get("promotion") or {}
        if not isinstance(request, dict):
            request = {}
        for key in (
            "live_production",
            "live_production_requested",
            "live_production_promotion_requested",
            "production_promotion_requested",
        ):
            if request.get(key) is True or payload.get(key) is True:
                return True
        for container in (request, payload):
            for key in (
                "scope",
                "target_scope",
                "stage",
                "target_stage",
                "environment",
                "target_environment",
            ):
                value = container.get(key)
                if isinstance(value, str) and value.strip().lower() in {
                    "live",
                    "prod",
                    "production",
                }:
                    return True
        return False

    @staticmethod
    def _check_statuses(
        gate_bundle_evaluation: Dict[str, Any],
        *prefixes: str,
    ) -> list[dict[str, Any]]:
        checks = gate_bundle_evaluation.get("checks") or []
        return [
            check
            for check in checks
            if isinstance(check, dict)
            and any(str(check.get("name", "")).startswith(prefix) for prefix in prefixes)
        ]

    @staticmethod
    def _registry_metadata(
        best_iteration: Dict[str, Any],
        metrics_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "mlflow_run_id": (
                best_iteration.get("mlflow_run_id")
                or metrics_payload.get("mlflow_run_id")
            ),
            "model_registry_name": metrics_payload.get("model_registry_name"),
            "model_version": metrics_payload.get("model_version"),
            "artifact_uri": metrics_payload.get("artifact_uri"),
        }

    @staticmethod
    def _composite_metadata(metrics_payload: Dict[str, Any]) -> Dict[str, Any]:
        composite = metrics_payload.get("composite_metadata")
        if isinstance(composite, dict):
            return composite
        composite = metrics_payload.get("composite")
        return composite if isinstance(composite, dict) else {}

    @staticmethod
    def _metadata_sidecar_path(target_path: str, iteration: int) -> str:
        path = Path(target_path)
        return str(
            path.with_name(
                f"{path.name}.development-promotion.iter-{iteration}.json"
            )
        )

    @staticmethod
    def _rollback_snapshot_path(
        *,
        target_path: str,
        research_id: str,
        iteration: int,
    ) -> str:
        path = Path(target_path)
        safe_research_id = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in research_id
        )
        return str(
            path.with_name(
                f"{path.name}.development-rollback."
                f"{safe_research_id}.iter-{iteration}.yaml"
            )
        )

    @staticmethod
    def _rollback_metadata_sidecar_path(target_path: str, promotion_id: int) -> str:
        path = Path(target_path)
        return str(
            path.with_name(
                f"{path.name}.development-rollback.promotion-{promotion_id}.json"
            )
        )

    @staticmethod
    def _sha256_text(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    async def _write_text_file(path: str, content: str) -> None:
        await asyncio.to_thread(os.makedirs, os.path.dirname(path), exist_ok=True)
        await asyncio.to_thread(
            Path(path).write_text,
            content,
            encoding="utf-8",
        )

    def _build_rollback_readiness(
        self,
        *,
        research_id: str,
        iteration: int,
        model_type: str,
        instrument: str,
        timeframe: str,
        target_path: str,
        previous_yaml: Optional[str],
        metrics_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        raw = metrics_payload.get("rollback_readiness")
        readiness = dict(raw) if isinstance(raw, dict) else {}
        planned_snapshot_path = self._rollback_snapshot_path(
            target_path=target_path,
            research_id=research_id,
            iteration=iteration,
        )
        rollback_target = (
            readiness.get("rollback_target")
            or metrics_payload.get("rollback_target")
            or metrics_payload.get("previous_development_version")
            or (planned_snapshot_path if previous_yaml is not None else None)
        )
        previous_addressable = bool(
            readiness.get("previous_development_version_addressable")
            or rollback_target
            or previous_yaml is not None
        )
        readiness.update(
            {
                "model_type": model_type,
                "instrument": instrument,
                "timeframe": timeframe,
                "target_path": target_path,
                "previous_config_present": previous_yaml is not None,
                "previous_config_snapshot_path": (
                    planned_snapshot_path if previous_yaml is not None else None
                ),
                "previous_config_sha256": (
                    self._sha256_text(previous_yaml)
                    if previous_yaml is not None
                    else readiness.get("previous_config_sha256")
                ),
                "previous_development_version_addressable": previous_addressable,
                "rollback_by_instrument_timeframe_supported": True,
                "rollback_method": "instrument_timeframe_development_config",
                "rollback_target_recorded": bool(rollback_target),
                "rollback_target": rollback_target,
                "prior_version_left_intact_on_failure": True,
            }
        )
        return readiness

    def _build_smoke_validation(
        self,
        *,
        best_yaml: str,
        metrics_payload: Dict[str, Any],
        rollback_readiness: Dict[str, Any],
    ) -> Dict[str, Any]:
        raw = metrics_payload.get("smoke_validation")
        smoke = dict(raw) if isinstance(raw, dict) else {}
        if "passed" not in smoke and "smoke_validation_passed" in metrics_payload:
            smoke["passed"] = metrics_payload.get("smoke_validation_passed")

        config_parse_error: Optional[str] = None
        config_parse_passed = False
        try:
            parsed = yaml.safe_load(best_yaml)
            config_parse_passed = isinstance(parsed, dict)
        except Exception as exc:  # pragma: no cover - exact YAML errors vary
            config_parse_error = str(exc)

        composite = self._composite_metadata(metrics_payload)
        inference = self._inference_payload(metrics_payload)
        composite_reload_supported = any(
            container.get(key) is True
            for container in (smoke, composite, inference)
            for key in (
                "composite_reload_passed",
                "composite_reload_supported",
                "reload_supported",
            )
        )
        fallback_validation = self._tsfm_fallback_validation(metrics_payload)
        tsfm_fallback_required = bool(fallback_validation.get("required"))
        tsfm_fallback_passed = (
            bool(fallback_validation.get("passed"))
            if tsfm_fallback_required
            else True
        )
        evidence_passed = smoke.get("passed") is True
        passed = (
            evidence_passed
            and config_parse_passed
            and tsfm_fallback_passed
        )
        smoke.update(
            {
                "schema_version": "development_smoke_validation.v1",
                "passed": passed,
                "evidence_passed": evidence_passed,
                "config_parse_passed": config_parse_passed,
                "config_parse_error": config_parse_error,
                "composite_reload_supported": composite_reload_supported,
                "prior_version_left_intact_on_failure": bool(
                    rollback_readiness.get(
                        "prior_version_left_intact_on_failure"
                    )
                ),
                "tsfm_fallback_required": tsfm_fallback_required,
                "tsfm_fallback_passed": tsfm_fallback_passed,
                "source": "autoresearch_config_promoter",
            }
        )
        return smoke

    def _best_iteration_with_preflight(
        self,
        best_iteration: Dict[str, Any],
        *,
        rollback_readiness: Dict[str, Any],
        smoke_validation: Dict[str, Any],
        signal_health: Dict[str, Any],
        inference_reload_validation: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = self._best_iteration_payload(best_iteration)
        payload["rollback_readiness"] = rollback_readiness
        payload["smoke_validation"] = smoke_validation
        payload["signal_health"] = signal_health
        payload["development_signal_health"] = signal_health
        payload["inference_reload_validation"] = inference_reload_validation
        if rollback_readiness.get("rollback_target"):
            payload["rollback_target"] = rollback_readiness["rollback_target"]
        enriched = dict(best_iteration)
        enriched["metrics_json"] = json.dumps(payload)
        return enriched

    @staticmethod
    def _inference_payload(metrics_payload: Dict[str, Any]) -> Dict[str, Any]:
        for key in ("inference_parity", "inference_validation", "inference"):
            value = metrics_payload.get(key)
            if isinstance(value, dict):
                return value
        return {}

    def _tsfm_fallback_validation(
        self,
        metrics_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        inference = self._inference_payload(metrics_payload)
        adapter = inference.get("adapter") or inference.get("tsfm_adapter") or {}
        if not isinstance(adapter, dict):
            adapter = {}
        is_tsfm = any(
            value is True
            for value in (
                metrics_payload.get("is_tsfm_candidate"),
                metrics_payload.get("tsfm_candidate"),
                inference.get("is_tsfm_candidate"),
                inference.get("tsfm_candidate"),
            )
        )
        if not is_tsfm:
            for value in (
                metrics_payload.get("model_family"),
                metrics_payload.get("candidate_family"),
                inference.get("model_family"),
                inference.get("candidate_family"),
            ):
                if isinstance(value, str) and value.lower() in {
                    "tsfm",
                    "ts-fm",
                    "timesfm",
                }:
                    is_tsfm = True
                    break
        fallback_passed = any(
            container.get(key) is True
            for container in (inference, adapter)
            for key in (
                "fallback_check_passed",
                "tabular_fallback_passed",
                "fallback_available",
            )
        )
        return {
            "required": is_tsfm,
            "passed": fallback_passed if is_tsfm else None,
            "details": {
                "inference": inference,
                "adapter": adapter,
            },
        }

    def _evaluate_gate_bundle(
        self,
        model_type: str,
        best_iteration: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Evaluate the best iteration against the development gate bundle."""
        try:
            bundle = load_gate_bundle(settings.workspace_root)
        except Exception as exc:
            if model_type == "direction":
                return {
                    "gate_bundle_id": None,
                    "version": None,
                    "model_type": model_type,
                    "applicable": True,
                    "passed": False,
                    "checks": [],
                    "blockers": ["missing_development_gate_bundle"],
                    "error": str(exc),
                }
            return {
                "gate_bundle_id": None,
                "version": None,
                "model_type": model_type,
                "applicable": False,
                "passed": True,
                "checks": [],
                "blockers": [],
                "error": str(exc),
            }

        return evaluate_development_gate_bundle(
            bundle=bundle,
            model_type=model_type,
            best_iteration=best_iteration,
        )

    def _resolve_artifacts_dir(
        self,
        workspace_path: str,
        model_type: str,
        instrument: str,
        timeframe: str,
    ) -> Optional[str]:
        """Find the directory containing trained model .pkl files."""
        inst_under = instrument.replace("-", "_")

        # Check results.json for explicit model_path
        results_json = os.path.join(
            settings.workspace_root, "runs", "autotuner",
            f"{inst_under}_{timeframe}", model_type, "results.json",
        )
        if os.path.exists(results_json):
            try:
                with open(results_json) as f:
                    data = json.load(f)
                model_rel = data.get("model_path")
                if model_rel:
                    model_abs = os.path.join(settings.workspace_root, model_rel)
                    if os.path.exists(model_abs):
                        return os.path.dirname(model_abs)
            except Exception:
                pass

        # Fallback: workspace model_type subdir
        direct = os.path.join(
            settings.workspace_root, "runs", "autotuner",
            f"{inst_under}_{timeframe}", model_type,
        )
        if os.path.isdir(direct):
            return direct

        return None

    async def _update_composite_versions(
        self,
        instrument: str,
        model_type: str,
        version_tag: str,
    ) -> None:
        """PATCH the composite in mlflow-service with the new model version.

        Uses the unauthenticated PATCH /by-instrument/{instrument}/versions
        endpoint. If no composite exists (404), logs a warning and moves on.
        """
        version_key = {
            "direction": "direction_model_version",
            "volatility": "volatility_model_version",
            "rl": "rl_model_version",
        }.get(model_type)
        if not version_key:
            logger.warning(
                "Unknown model_type %r — skipping composite update", model_type,
            )
            return

        url = (
            f"{settings.mlflow_service_url}/api/v1/composites"
            f"/by-instrument/{instrument}/versions"
        )
        body = {version_key: version_tag}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.patch(url, json=body)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(
                    "Composite versions updated for %s: %s (updated %d composite(s))",
                    instrument, version_tag, data.get("updated", 0),
                )
            elif resp.status_code == 404:
                logger.warning(
                    "No composite found for %s — skipping composite update. "
                    "Create one via POST /api/v1/composites first.",
                    instrument,
                )
            else:
                logger.error(
                    "Failed to update composite for %s: %d %s",
                    instrument, resp.status_code, resp.text[:300],
                )
        except httpx.HTTPError as exc:
            logger.error(
                "HTTP error updating composite for %s: %s", instrument, exc,
            )

    @staticmethod
    def _extract_strategy_market(yaml_str: str) -> tuple:
        """Extract agent_strategy and trading_mode from a YAML config string.

        Returns (strategy, market_type) with defaults if not found.
        """
        try:
            import yaml as _yaml
            cfg = _yaml.safe_load(yaml_str)
            if not isinstance(cfg, dict):
                return "BALA", "stock"
            strategy = (cfg.get("agent_strategy") or "BALA").upper()
            env = cfg.get("environment") or {}
            market = (env.get("trading_mode") or cfg.get("trading_mode") or "stock").lower()
            return strategy, market
        except Exception:
            return "BALA", "stock"

    @staticmethod
    def _get_target_path(
        model_type: str, instrument: str, timeframe: str,
        strategy: str = "BALA", market_type: str = "stock",
    ) -> str:
        """Determine the host config file path for promotion.

        ML-67: RL configs include strategy + market_type in the filename.
        """
        host_configs = settings.host_configs_path
        if model_type in ("direction", "volatility"):
            return os.path.join(
                host_configs,
                "instrument_configs",
                f"{instrument}_{timeframe}.yaml",
            )
        elif model_type == "rl":
            strat = strategy.upper()
            mkt = market_type.lower()
            return os.path.join(
                host_configs,
                "rl",
                f"{instrument}_{timeframe}_{strat}_{mkt}_production.yaml",
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")
