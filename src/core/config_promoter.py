"""Config promoter — previews and writes winning configs to the host bind mount."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import tempfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import yaml

from src.core.artifact_reference import (
    first_valid_artifact_ref,
    normalize_artifact_references_in_mapping,
    normalize_optional_artifact_ref,
)
from src.core.blocker_classifier import classify_blockers
from src.config import secret_value, settings
from src.core.consistency_validator import build_consistency_report
from src.core.development_gate_bundle import (
    apply_instrument_gate_overrides,
    evaluate_development_gate_bundle,
    load_gate_bundle,
    load_production_gate_bundle,
)
from src.core.development_inference_validation import (
    build_development_inference_validation,
)
from src.core.development_signal_health import build_development_signal_health
from src.core.gate_status import training_gates_passed_from_iteration
from src.core.research_phase_plan import build_phase_state
from src.core.results_store import ResultsStore

logger = logging.getLogger(__name__)


def _atomic_write_text(path: str, content: str) -> None:
    """Sync helper: tmp+fsync+os.replace atomic write.

    Phase 3.1 hardening for config/metadata promotion durability.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, str(target))
        # fsync the directory entry so the rename survives a power loss
        dir_fd = os.open(str(target.parent), os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        # Best-effort cleanup of the tmp file if the rename never happened
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise

DEVELOPMENT_PROMOTION_METADATA_VERSION = "development_promotion_metadata.v1"
SCOPED_PROMOTION_METADATA_VERSION = "scoped_promotion_decision.v1"
DEVELOPMENT_PROMOTION_SCOPE = "development"
PAPER_PROMOTION_SCOPE = "paper"
CANARY_PROMOTION_SCOPE = "canary"
PRODUCTION_PROMOTION_SCOPE = "production"
PROMOTION_SCOPES = (
    DEVELOPMENT_PROMOTION_SCOPE,
    PAPER_PROMOTION_SCOPE,
    CANARY_PROMOTION_SCOPE,
    PRODUCTION_PROMOTION_SCOPE,
)
MLFLOW_COMPOSITES_API_PREFIX = "/api/v1/composites"
QUALITY_BASELINE_MODE = "development_quality_baseline"
QUALITY_BASELINE_BLOCKER = "best_metric_below_development_baseline"


class ConfigPromoter:
    """Handles preview and confirmation of config promotion to host."""

    def __init__(self, store: ResultsStore) -> None:
        self._store = store

    async def preview(
        self,
        research_id: str,
        *,
        scope: str = DEVELOPMENT_PROMOTION_SCOPE,
        approval: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Dry-run promotion: returns the diff/preview without writing."""
        promotion_scope = self._normalize_promotion_scope(scope)
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
        phase_state = build_phase_state(
            session=session,
            iterations=await self._promotion_iterations(research_id, best),
        )

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
        training_gates_passed = training_gates_passed_from_iteration(best)
        metrics_payload["training_gates_passed"] = training_gates_passed
        metrics_payload["all_gates_passed"] = training_gates_passed
        attempt_snapshot = self._attempt_snapshot_payload(best, metrics_payload)
        artifact_hash = first_valid_artifact_ref(
            attempt_snapshot.get("artifact_hash"),
            metrics_payload.get("artifact_hash"),
            metrics_payload.get("model_artifact_hash"),
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
        consistency_report = build_consistency_report(
            research_id=research_id,
            iteration=best["iteration"],
            model_type=model_type,
            config_snapshot=best_yaml,
            metrics_payload=metrics_payload,
            attempt_snapshot=attempt_snapshot,
            preflight={
                "rollback_readiness": rollback_readiness,
                "smoke_validation": smoke_validation,
                "signal_health": signal_health,
                "inference_reload_validation": inference_reload_validation,
                "rollback_target": rollback_readiness.get("rollback_target"),
            },
            mode="promotion",
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
            instrument=instrument, timeframe=timeframe,
        )
        gate_bundle_evaluation, consistency_report = (
            self._apply_pipeline_feature_replay_policy(
                session=session,
                model_type=model_type,
                gate_bundle_evaluation=gate_bundle_evaluation,
                consistency_report=consistency_report,
            )
        )
        gate_bundle_evaluation = self._with_blocker_details(
            gate_bundle_evaluation,
            metrics_payload=metrics_payload,
            phase_state=phase_state,
            source="development_gate_bundle",
        )
        consistency_report = self._with_blocker_details(
            consistency_report,
            metrics_payload=metrics_payload,
            phase_state=phase_state,
            source="cross_service_consistency",
        )
        quality_baseline_evaluation = await self._build_quality_baseline_evaluation(
            research_id=research_id,
            best_iteration=best,
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
        )
        quality_baseline_evaluation = self._with_blocker_details(
            quality_baseline_evaluation,
            metrics_payload=metrics_payload,
            phase_state=phase_state,
            source=QUALITY_BASELINE_MODE,
        )
        preview_blocker_details = self._merge_blocker_details(
            gate_bundle_evaluation.get("blocker_details", []),
            consistency_report.get("blocker_details", []),
            quality_baseline_evaluation.get("blocker_details", []),
        )
        development_gate_bundle_passed = bool(
            gate_bundle_evaluation.get("passed", False)
        )
        consistency_report_passed = bool(consistency_report.get("passed", False))
        quality_baseline_passed = bool(
            quality_baseline_evaluation.get("passed", False)
        )
        promotion_allowed = (
            training_gates_passed
            and development_gate_bundle_passed
            and consistency_report_passed
            and quality_baseline_passed
        )
        candidate_pool_blockers = self._merge_blockers(
            gate_bundle_evaluation.get("blockers", []),
            quality_baseline_evaluation.get("blockers", []),
        )
        candidate_pool_blocker_details = self._merge_blocker_details(
            gate_bundle_evaluation.get("blocker_details", []),
            quality_baseline_evaluation.get("blocker_details", []),
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
            "consistency_passed": consistency_report.get("passed"),
            "consistency_blockers": consistency_report.get("blockers", []),
            "consistency_blocker_details": consistency_report.get(
                "blocker_details", []
            ),
            "quality_baseline_passed": quality_baseline_passed,
            "quality_baseline_blockers": quality_baseline_evaluation.get(
                "blockers", []
            ),
            "quality_baseline_blocker_details": quality_baseline_evaluation.get(
                "blocker_details", []
            ),
            "quality_baseline_evaluation": dict(quality_baseline_evaluation),
            "status": "eligible" if promotion_allowed else "blocked",
            "blockers": candidate_pool_blockers,
            "blocker_details": candidate_pool_blocker_details,
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
            gates_passed=training_gates_passed,
            training_gates_passed=training_gates_passed,
            development_gate_bundle_passed=development_gate_bundle_passed,
            consistency_report_passed=consistency_report_passed,
            quality_baseline_passed=quality_baseline_passed,
            gate_bundle_evaluation=gate_bundle_evaluation,
            candidate_pool_record=candidate_pool_record,
            promotion_allowed=promotion_allowed,
            rollback_readiness=rollback_readiness,
            smoke_validation=smoke_validation,
            signal_health=signal_health,
            inference_reload_validation=inference_reload_validation,
            consistency_report=consistency_report,
            quality_baseline_evaluation=quality_baseline_evaluation,
        )

        preview = {
            "research_id": research_id,
            "iteration": best["iteration"],
            "model_type": model_type,
            "instrument": instrument,
            "timeframe": timeframe,
            "scope": DEVELOPMENT_PROMOTION_SCOPE,
            "promotion_scope": DEVELOPMENT_PROMOTION_SCOPE,
            "target_path": target_path,
            "new_config": best_yaml,
            "config_snapshot_sha256": config_snapshot_sha256,
            "current_config": previous_yaml,
            "best_metric": best["primary_metric"],
            "training_gates_passed": training_gates_passed,
            "gates_passed": training_gates_passed,
            "development_gate_bundle_passed": development_gate_bundle_passed,
            "consistency_report_passed": consistency_report_passed,
            "quality_baseline_passed": quality_baseline_passed,
            "gate_bundle_evaluation": gate_bundle_evaluation,
            "candidate_pool_record": candidate_pool_record,
            "best_candidate_ownership": development_promotion_metadata[
                "best_candidate_ownership"
            ],
            "consistency_report": consistency_report,
            "quality_baseline_evaluation": quality_baseline_evaluation,
            "development_promotion_metadata": development_promotion_metadata,
            "promotion_allowed": promotion_allowed,
            "blocker_details": preview_blocker_details,
        }
        if promotion_scope == DEVELOPMENT_PROMOTION_SCOPE:
            return preview

        scoped_metadata = await self._build_scoped_promotion_metadata(
            preview=preview,
            session=session,
            metrics_payload=metrics_payload,
            scope=promotion_scope,
            approval=approval,
        )
        scoped_allowed = bool(scoped_metadata.get("promotion_allowed"))
        scoped_preview = dict(preview)
        scoped_preview.update(
            {
                "scope": promotion_scope,
                "promotion_scope": promotion_scope,
                "scope_promotion_allowed": scoped_allowed,
                "promotion_allowed": scoped_allowed,
                "scoped_promotion_metadata": scoped_metadata,
                "promotion_metadata": scoped_metadata,
                "scope_gate_evaluation": {
                    "scope": promotion_scope,
                    "passed": scoped_allowed,
                    "blockers": scoped_metadata.get("blockers", []),
                    "blocker_details": classify_blockers(
                        scoped_metadata.get("blockers", []),
                        checks=scoped_metadata.get("checks", []),
                        metrics_payload=metrics_payload,
                        phase_state=phase_state,
                        source=f"{promotion_scope}_promotion_scope",
                    ),
                    "checks": scoped_metadata.get("checks", []),
                },
            }
        )
        return scoped_preview

    async def confirm(
        self,
        research_id: str,
        *,
        scope: str = DEVELOPMENT_PROMOTION_SCOPE,
        approval: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute the promotion: write best config to host bind mount."""
        promotion_scope = self._normalize_promotion_scope(scope)
        if promotion_scope != DEVELOPMENT_PROMOTION_SCOPE:
            return await self._confirm_scoped_promotion(
                research_id,
                scope=promotion_scope,
                approval=approval,
            )

        preview = await self.preview(research_id)

        if not preview["training_gates_passed"]:
            raise ValueError(
                "Cannot promote: best iteration did not pass training gates"
            )
        gate_eval = preview.get("gate_bundle_evaluation") or {}
        if not gate_eval.get("passed", False):
            blockers = ", ".join(gate_eval.get("blockers") or ["unknown"])
            raise ValueError(
                "Cannot promote: development gate bundle failed "
                f"({blockers})"
            )
        consistency_report = preview.get("consistency_report") or {}
        if not consistency_report.get("passed", False):
            blockers = ", ".join(
                consistency_report.get("blockers") or ["unknown"]
            )
            raise ValueError(
                "Cannot promote: cross-service consistency failed "
                f"({blockers})"
            )
        quality_baseline = preview.get("quality_baseline_evaluation") or {}
        if not quality_baseline.get("passed", False):
            blockers = ", ".join(
                quality_baseline.get("blockers") or ["unknown"]
            )
            raise ValueError(
                "Cannot promote: development quality baseline failed "
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
        best_metrics_payload: Dict[str, Any] = {}
        best_attempt_snapshot: Dict[str, Any] = {}
        if best:
            mlflow_run_id = normalize_optional_artifact_ref(
                best.get("mlflow_run_id")
            )
            metric_name = best.get("metric_name")
            metric_value = best.get("primary_metric")
            best_metrics_payload = self._best_iteration_payload(best)
            best_attempt_snapshot = self._attempt_snapshot_payload(
                best,
                best_metrics_payload,
            )
            mlflow_run_id = mlflow_run_id or normalize_optional_artifact_ref(
                best_metrics_payload.get("mlflow_run_id")
            )
            model_registry_name, model_version = self._model_version_components(
                best_metrics_payload
            )

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
        metadata_already_written = False
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
                workspace_path,
                model_type,
                instrument,
                timeframe,
                metrics_payload=best_metrics_payload,
                attempt_snapshot=best_attempt_snapshot,
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
            # Direct write fallback — Phase 3.1: write metadata sidecar
            # first so a crash mid-promotion never leaves an active config
            # without provenance metadata; then atomically swap the config.
            metadata_path = self._metadata_sidecar_path(target_path, preview["iteration"])
            metadata = self._finalize_development_promotion_metadata(
                metadata=metadata,
                metadata_path=metadata_path,
                promotion_record_created=True,
            )
            await self._write_text_file(
                metadata_path,
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            )
            await self._write_text_file(target_path, preview["new_config"])
            logger.info("Wrote promoted config to %s", target_path)
            metadata_already_written = True

        if not metadata_already_written:
            metadata_path = self._metadata_sidecar_path(target_path, preview["iteration"])
            metadata = self._finalize_development_promotion_metadata(
                metadata=metadata,
                metadata_path=metadata_path,
                promotion_record_created=True,
            )
            await self._write_text_file(
                metadata_path,
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
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

    async def _confirm_scoped_promotion(
        self,
        research_id: str,
        *,
        scope: str,
        approval: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Record a paper/canary/production stage decision without rewriting dev config."""
        preview = await self.preview(
            research_id,
            scope=scope,
            approval=approval,
        )
        if not preview["training_gates_passed"]:
            raise ValueError(
                "Cannot promote: best iteration did not pass training gates"
            )
        gate_eval = preview.get("gate_bundle_evaluation") or {}
        if not gate_eval.get("passed", False):
            blockers = ", ".join(gate_eval.get("blockers") or ["unknown"])
            raise ValueError(
                "Cannot promote: development gate bundle failed "
                f"({blockers})"
            )
        consistency_report = preview.get("consistency_report") or {}
        if not consistency_report.get("passed", False):
            blockers = ", ".join(
                consistency_report.get("blockers") or ["unknown"]
            )
            raise ValueError(
                "Cannot promote: cross-service consistency failed "
                f"({blockers})"
            )
        quality_baseline = preview.get("quality_baseline_evaluation") or {}
        if not quality_baseline.get("passed", False):
            blockers = ", ".join(
                quality_baseline.get("blockers") or ["unknown"]
            )
            raise ValueError(
                "Cannot promote: development quality baseline failed "
                f"({blockers})"
            )

        metadata = dict(preview.get("scoped_promotion_metadata") or {})
        if not metadata.get("promotion_allowed"):
            blockers = ", ".join(metadata.get("blockers") or ["unknown"])
            raise ValueError(
                f"Cannot promote to {scope}: scoped promotion policy failed "
                f"({blockers})"
            )

        best = await self._store.get_best_iteration(research_id)
        metrics_payload = self._best_iteration_payload(best or {})
        if scope == PRODUCTION_PROMOTION_SCOPE:
            metadata["mlflow_service"] = await self._promote_production_composite(
                preview=preview,
                metrics_payload=metrics_payload,
                approval=approval,
            )

        metadata_path = self._metadata_sidecar_path(
            preview["target_path"],
            preview["iteration"],
            scope=scope,
        )
        metadata = self._finalize_scoped_promotion_metadata(
            metadata=metadata,
            metadata_path=metadata_path,
            promotion_record_created=True,
        )
        await self._write_text_file(
            metadata_path,
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        )

        return await self._store.record_promotion(
            research_id=research_id,
            iteration=preview["iteration"],
            model_type=preview["model_type"],
            instrument=preview["instrument"],
            timeframe=preview["timeframe"],
            target_path=preview["target_path"],
            config_yaml=preview["new_config"],
            previous_yaml=preview["current_config"],
            scope=scope,
            metadata_path=metadata_path,
            promotion_metadata=metadata,
        )

    def _mlflow_service_auth_headers(self, *, require_token: bool) -> dict[str, str] | None:
        token = secret_value(settings.mlflow_service_auth_token)
        if not token:
            if require_token:
                raise ValueError(
                    "Production-scope promotion requires "
                    "AUTORESEARCH_MLFLOW_SERVICE_AUTH_TOKEN, "
                    "MLFLOW_SERVICE_AUTH_TOKEN, SERVICE_AUTH_TOKEN, or "
                    "ML_ADMIN_TOKEN"
                )
            return None
        return {
            "Authorization": f"Bearer {token}",
            "X-Service-Name": settings.service_name,
        }

    @staticmethod
    def _composite_version_key(model_type: str) -> str | None:
        return {
            "direction": "direction_model_version",
            "volatility": "volatility_model_version",
            "rl": "rl_model_version",
        }.get(model_type)

    @staticmethod
    def _model_version_components(
        metrics_payload: Dict[str, Any],
    ) -> tuple[str | None, Any]:
        base_registry = (
            metrics_payload.get("model_registry_name")
            or metrics_payload.get("registered_model_name")
        )
        ensemble_version = metrics_payload.get("ensemble_model_version")
        ensemble_registry = metrics_payload.get("ensemble_model_registry_name")
        if ensemble_version and not ensemble_registry and base_registry:
            ensemble_registry = f"{base_registry}_ensemble"
        registry_name = (
            metrics_payload.get("serving_model_registry_name")
            or metrics_payload.get("serving_registered_model_name")
            or ensemble_registry
            or base_registry
        )
        model_version = (
            metrics_payload.get("serving_model_version")
            or metrics_payload.get("serving_registered_model_version")
            or ensemble_version
            or metrics_payload.get("model_version")
            or metrics_payload.get("registered_model_version")
        )
        return registry_name, model_version

    @classmethod
    def _model_version_tag(cls, metrics_payload: Dict[str, Any]) -> str:
        registry_name, model_version = cls._model_version_components(metrics_payload)
        if not registry_name or model_version in (None, ""):
            raise ValueError(
                "Production-scope promotion requires winning iteration "
                "serving, ensemble, or base model registry name and version"
            )
        return f"{registry_name}:{model_version}"

    async def _promote_production_composite(
        self,
        *,
        preview: Dict[str, Any],
        metrics_payload: Dict[str, Any],
        approval: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Promote the authoritative mlflow-service composite to production."""
        headers = self._mlflow_service_auth_headers(require_token=True)
        model_type = str(preview["model_type"])
        version_key = self._composite_version_key(model_type)
        if not version_key:
            raise ValueError(f"Unknown model_type {model_type!r}")
        version_tag = self._model_version_tag(metrics_payload)

        base_url = settings.mlflow_service_url.rstrip("/")
        list_url = f"{base_url}{MLFLOW_COMPOSITES_API_PREFIX}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                list_resp = await client.get(
                    list_url,
                    headers=headers,
                    params={
                        "instrument": preview["instrument"],
                        "page_size": 100,
                    },
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(
                "Failed to list mlflow-service composites for production "
                f"promotion: {exc}"
            ) from exc

        if list_resp.status_code != 200:
            raise RuntimeError(
                "Failed to list mlflow-service composites for production "
                f"promotion: HTTP {list_resp.status_code} {list_resp.text[:300]}"
            )

        composites_payload = list_resp.json()
        if isinstance(composites_payload, list):
            composites = composites_payload
        elif isinstance(composites_payload, dict):
            composites = composites_payload.get("items") or composites_payload.get("composites") or []
        else:
            composites = []

        matches = [
            composite
            for composite in composites
            if isinstance(composite, dict)
            and str(composite.get("status") or "").lower() != "retired"
            and str(composite.get(version_key) or "") == version_tag
        ]
        if not matches:
            raise ValueError(
                "No non-retired mlflow-service composite matches "
                f"{version_key}={version_tag} for {preview['instrument']}"
            )
        if len(matches) > 1:
            ids = ", ".join(str(match.get("id")) for match in matches)
            raise ValueError(
                "Multiple non-retired mlflow-service composites match "
                f"{version_key}={version_tag}: {ids}"
            )

        selected = matches[0]
        composite_id = str(selected.get("id") or "")
        if not composite_id:
            raise RuntimeError("Matched mlflow-service composite has no id")
        prior_status = str(selected.get("status") or "")
        composite_url = f"{list_url}/{composite_id}"
        if prior_status.lower() == PRODUCTION_PROMOTION_SCOPE:
            return {
                "outcome": "already_production",
                "composite_id": composite_id,
                "prior_status": prior_status,
                "final_status": prior_status,
                "promoted_at": selected.get("promoted_at"),
                "url": composite_url,
            }

        reason = (approval or {}).get("reason") or "autoresearch production promotion"
        promote_payload: dict[str, Any] = {
            "target_stage": PRODUCTION_PROMOTION_SCOPE,
            "reason": reason,
        }
        if "rollup_score" in metrics_payload and metrics_payload.get("rollup_score") is not None:
            rollup_score = self._numeric_value(metrics_payload.get("rollup_score"))
            if rollup_score is None:
                raise ValueError("metrics.rollup_score must be numeric when present")
            promote_payload["rollup_score"] = rollup_score

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                promote_resp = await client.post(
                    f"{composite_url}/promote",
                    headers=headers,
                    json=promote_payload,
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(
                "Failed to promote mlflow-service composite to production: "
                f"{exc}"
            ) from exc

        if promote_resp.status_code not in {200, 201}:
            raise RuntimeError(
                "Failed to promote mlflow-service composite to production: "
                f"HTTP {promote_resp.status_code} {promote_resp.text[:300]}"
            )
        promoted = promote_resp.json()
        return {
            "outcome": "promoted",
            "composite_id": composite_id,
            "prior_status": prior_status,
            "final_status": promoted.get("status") or PRODUCTION_PROMOTION_SCOPE,
            "promoted_at": promoted.get("promoted_at"),
            "url": composite_url,
        }

    async def _build_scoped_promotion_metadata(
        self,
        *,
        preview: Dict[str, Any],
        session: Dict[str, Any],
        metrics_payload: Dict[str, Any],
        scope: str,
        approval: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create an auditable decision artifact for non-development scopes."""
        model_type = preview["model_type"]
        instrument = preview["instrument"]
        timeframe = preview["timeframe"]
        required_prior_scopes = self._required_prior_scopes(scope)
        prior_promotions: dict[str, Optional[Dict[str, Any]]] = {}
        for prior_scope in required_prior_scopes:
            prior_promotions[prior_scope] = await self._latest_promotion_record(
                model_type=model_type,
                instrument=instrument,
                timeframe=timeframe,
                scope=prior_scope,
            )

        approval_record = self._approval_record(approval, scope=scope)
        production_bundle = self._production_gate_bundle_summary(scope)
        development_metadata = dict(
            preview.get("development_promotion_metadata") or {}
        )
        rollback_target = (
            development_metadata.get("rollback_target")
            or development_metadata.get("rollback_readiness", {}).get(
                "rollback_target"
            )
        )
        evidence = self._promotion_scope_evidence(
            metrics_payload=metrics_payload,
            development_metadata=development_metadata,
            production_bundle=production_bundle,
        )

        checks: list[dict[str, Any]] = []
        blockers: list[str] = []

        def add_check(
            name: str,
            passed: bool,
            reason: str,
            details: Any = None,
        ) -> None:
            checks.append(
                {
                    "name": name,
                    "status": "passed" if passed else "failed",
                    "reason": None if passed else reason,
                    "details": details,
                }
            )
            if not passed and reason not in blockers:
                blockers.append(reason)

        add_check(
            "development_candidate_allowed",
            bool(preview.get("development_promotion_metadata", {}).get("promotion_allowed")),
            "development_promotion_not_allowed",
            {
                "development_gate_bundle_passed": (
                    preview.get("gate_bundle_evaluation") or {}
                ).get("passed"),
                "consistency_passed": (
                    preview.get("consistency_report") or {}
                ).get("passed"),
                "quality_baseline_passed": (
                    preview.get("quality_baseline_evaluation") or {}
                ).get("passed"),
            },
        )
        for prior_scope, promotion in prior_promotions.items():
            add_check(
                f"{prior_scope}_promotion_record",
                promotion is not None,
                f"missing_{prior_scope}_promotion",
                self._compact_promotion_record(promotion),
            )
        add_check(
            "scope_approval",
            bool(approval_record.get("satisfied")),
            f"missing_{scope}_approval",
            approval_record,
        )
        add_check(
            "rollback_target_addressable",
            bool(rollback_target),
            "missing_rollback_target",
            {"rollback_target": rollback_target},
        )

        if scope in {CANARY_PROMOTION_SCOPE, PRODUCTION_PROMOTION_SCOPE}:
            add_check(
                "paper_validation_passed",
                bool(evidence["paper_validation"].get("passed")),
                "missing_paper_validation",
                evidence["paper_validation"],
            )
        if scope == PRODUCTION_PROMOTION_SCOPE:
            add_check(
                "production_gate_bundle_loaded",
                bool(production_bundle.get("loaded")),
                "missing_production_gate_bundle",
                production_bundle,
            )
            add_check(
                "model_card_present",
                bool(evidence["model_card"].get("passed")),
                "missing_model_card",
                evidence["model_card"],
            )
            add_check(
                "supervised_feature_readiness",
                bool(evidence["feature_readiness"].get("passed")),
                "missing_feature_readiness",
                evidence["feature_readiness"],
            )
            add_check(
                "inference_parity_reload_passed",
                bool(evidence["inference_parity_reload"].get("passed")),
                "inference_reload_failed",
                evidence["inference_parity_reload"],
            )
            add_check(
                "canary_duration_passed",
                bool(evidence["canary_validation"].get("passed")),
                "missing_canary_duration",
                evidence["canary_validation"],
            )
            add_check(
                "live_risk_limits_configured",
                bool(evidence["live_risk_limits"].get("passed")),
                "missing_live_risk_limits",
                evidence["live_risk_limits"],
            )
            add_check(
                "monitoring_alerts_configured",
                bool(evidence["monitoring_alerts"].get("passed")),
                "missing_monitoring_alerts",
                evidence["monitoring_alerts"],
            )
            if model_type == "rl":
                add_check(
                    "rl_oos_provenance_passed",
                    bool(evidence["rl_oos"].get("passed")),
                    "missing_rl_oos_provenance",
                    evidence["rl_oos"],
                )
                add_check(
                    "rl_economic_replay_passed",
                    bool(evidence["rl_economic_replay"].get("passed")),
                    "missing_rl_economic_replay",
                    evidence["rl_economic_replay"],
                )

        promotion_allowed = not blockers
        prior_compact = {
            prior_scope: self._compact_promotion_record(promotion)
            for prior_scope, promotion in prior_promotions.items()
            if promotion is not None
        }
        decision_chain = self._decision_chain(
            development_metadata=development_metadata,
            prior_promotions=prior_promotions,
            current_scope=scope,
            current_allowed=promotion_allowed,
            current_blockers=blockers,
        )
        return {
            "schema_version": SCOPED_PROMOTION_METADATA_VERSION,
            "scope": scope,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "research_id": preview["research_id"],
            "iteration": preview["iteration"],
            "model_type": model_type,
            "instrument": instrument,
            "timeframe": timeframe,
            "target_path": preview["target_path"],
            "workspace_path": session.get("workspace_path"),
            "promotion_allowed": promotion_allowed,
            "blockers": blockers,
            "checks": checks,
            "required_prior_scopes": required_prior_scopes,
            "prior_promotions": prior_compact,
            "decision_chain": decision_chain,
            "approval": approval_record,
            "production_gate_bundle": production_bundle,
            "development_gate_bundle": development_metadata.get("gate_bundle"),
            "best_candidate_ownership": development_metadata.get(
                "best_candidate_ownership"
            ),
            "cross_service_consistency": preview.get("consistency_report"),
            "quality_baseline_evaluation": preview.get(
                "quality_baseline_evaluation"
            ),
            "rollback_target": rollback_target,
            "rollback_targets": self._rollback_targets(
                prior_promotions=prior_promotions,
                current_scope=scope,
                current_target=rollback_target,
            ),
            "evidence": evidence,
            "config_write_performed": False,
            "promotion_record_created": False,
        }

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
        training_gates_passed: bool,
        development_gate_bundle_passed: bool,
        consistency_report_passed: bool,
        quality_baseline_passed: bool,
        gate_bundle_evaluation: Dict[str, Any],
        candidate_pool_record: Dict[str, Any],
        promotion_allowed: bool,
        rollback_readiness: Dict[str, Any],
        smoke_validation: Dict[str, Any],
        signal_health: Dict[str, Any],
        inference_reload_validation: Dict[str, Any],
        consistency_report: Dict[str, Any],
        quality_baseline_evaluation: Dict[str, Any],
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
            "artifact_hash": first_valid_artifact_ref(
                attempt_snapshot.get("artifact_hash"),
                metrics_payload.get("artifact_hash"),
                metrics_payload.get("model_artifact_hash"),
            ),
            "mlflow_run_id": first_valid_artifact_ref(
                best_iteration.get("mlflow_run_id"),
                metrics_payload.get("mlflow_run_id"),
            ),
        }
        blocker_details = self._merge_blocker_details(
            gate_bundle_evaluation.get("blocker_details", []),
            consistency_report.get("blocker_details", []),
            quality_baseline_evaluation.get("blocker_details", []),
        )
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
            # R3: persist the formula version so the NEXT session's quality
            # baseline check can detect a cross-formula mismatch instead of
            # comparing incomparable numbers.
            "composite_formula_version": self._formula_version(metrics_payload),
            "training_gates_passed": training_gates_passed,
            "gates_passed": gates_passed,
            "development_gate_bundle_passed": development_gate_bundle_passed,
            "consistency_report_passed": consistency_report_passed,
            "quality_baseline_passed": quality_baseline_passed,
            "quality_baseline_usable": True,
            "promotion_allowed": promotion_allowed,
            "blocker_details": blocker_details,
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
                "blocker_details": gate_bundle_evaluation.get(
                    "blocker_details", []
                ),
                "checks": gate_bundle_evaluation.get("checks", []),
                "waivers": gate_bundle_evaluation.get("waivers", []),
            },
            "best_candidate_ownership": best_candidate_ownership,
            "candidate_pool_record": dict(candidate_pool_record),
            "cross_service_consistency": dict(consistency_report),
            "quality_baseline_evaluation": dict(quality_baseline_evaluation),
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
                "quality_baseline": self._check_statuses(
                    quality_baseline_evaluation,
                    "best_metric_not_below_development_baseline",
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

    def _finalize_scoped_promotion_metadata(
        self,
        *,
        metadata: Dict[str, Any],
        metadata_path: str,
        promotion_record_created: bool,
    ) -> Dict[str, Any]:
        finalized = dict(metadata)
        finalized["metadata_path"] = metadata_path
        finalized["promotion_record_created"] = promotion_record_created
        return finalized

    @staticmethod
    def _normalize_promotion_scope(scope: str | None) -> str:
        normalized = (scope or DEVELOPMENT_PROMOTION_SCOPE).strip().lower()
        if normalized in {"dev"}:
            normalized = DEVELOPMENT_PROMOTION_SCOPE
        if normalized in {"prod", "live"}:
            normalized = PRODUCTION_PROMOTION_SCOPE
        if normalized not in PROMOTION_SCOPES:
            allowed = ", ".join(PROMOTION_SCOPES)
            raise ValueError(f"Unknown promotion scope {scope!r}; expected one of {allowed}")
        return normalized

    @staticmethod
    def _required_prior_scopes(scope: str) -> list[str]:
        if scope == PAPER_PROMOTION_SCOPE:
            return [DEVELOPMENT_PROMOTION_SCOPE]
        if scope == CANARY_PROMOTION_SCOPE:
            return [DEVELOPMENT_PROMOTION_SCOPE, PAPER_PROMOTION_SCOPE]
        if scope == PRODUCTION_PROMOTION_SCOPE:
            return [
                DEVELOPMENT_PROMOTION_SCOPE,
                PAPER_PROMOTION_SCOPE,
                CANARY_PROMOTION_SCOPE,
            ]
        return []

    async def _latest_promotion_record(
        self,
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
        scope: str,
    ) -> Optional[Dict[str, Any]]:
        get_latest = getattr(self._store, "get_latest_promotion", None)
        if get_latest is not None:
            return await get_latest(
                model_type=model_type,
                instrument=instrument,
                timeframe=timeframe,
                scope=scope,
            )
        if scope == DEVELOPMENT_PROMOTION_SCOPE:
            get_latest_dev = getattr(
                self._store, "get_latest_development_promotion", None
            )
            if get_latest_dev is not None:
                return await get_latest_dev(
                    model_type=model_type,
                    instrument=instrument,
                    timeframe=timeframe,
                )
        list_promotions = getattr(self._store, "list_promotions", None)
        if list_promotions is None:
            return None
        rows = await list_promotions()
        for row in rows:
            if (
                row.get("model_type") == model_type
                and row.get("instrument") == instrument
                and row.get("timeframe") == timeframe
                and row.get("scope") == scope
            ):
                return row
        return None

    @staticmethod
    def _compact_promotion_record(
        promotion: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if promotion is None:
            return None
        metadata = promotion.get("promotion_metadata") or {}
        return {
            "id": promotion.get("id"),
            "scope": promotion.get("scope"),
            "research_id": promotion.get("research_id"),
            "iteration": promotion.get("iteration"),
            "promoted_at": promotion.get("promoted_at"),
            "target_path": promotion.get("target_path"),
            "metadata_path": promotion.get("metadata_path"),
            "rollback_target": (
                metadata.get("rollback_target")
                or metadata.get("rollback_readiness", {}).get("rollback_target")
            ),
            "promotion_allowed": metadata.get("promotion_allowed"),
        }

    def _decision_chain(
        self,
        *,
        development_metadata: Dict[str, Any],
        prior_promotions: Dict[str, Optional[Dict[str, Any]]],
        current_scope: str,
        current_allowed: bool,
        current_blockers: list[str],
    ) -> list[Dict[str, Any]]:
        chain: list[Dict[str, Any]] = []
        development_record = prior_promotions.get(DEVELOPMENT_PROMOTION_SCOPE)
        if development_record is not None:
            compact = self._compact_promotion_record(development_record)
            if compact:
                chain.append(compact)
        elif development_metadata:
            chain.append(
                {
                    "scope": DEVELOPMENT_PROMOTION_SCOPE,
                    "research_id": development_metadata.get("research_id"),
                    "iteration": development_metadata.get("iteration"),
                    "target_path": development_metadata.get("target_path"),
                    "rollback_target": development_metadata.get("rollback_target"),
                    "promotion_allowed": development_metadata.get(
                        "promotion_allowed"
                    ),
                    "gate_bundle": development_metadata.get("gate_bundle"),
                }
            )
        for prior_scope in (PAPER_PROMOTION_SCOPE, CANARY_PROMOTION_SCOPE):
            compact = self._compact_promotion_record(
                prior_promotions.get(prior_scope)
            )
            if compact:
                chain.append(compact)
        chain.append(
            {
                "scope": current_scope,
                "promotion_allowed": current_allowed,
                "blockers": list(current_blockers),
                "decision_artifact_schema": SCOPED_PROMOTION_METADATA_VERSION,
            }
        )
        return chain

    def _rollback_targets(
        self,
        *,
        prior_promotions: Dict[str, Optional[Dict[str, Any]]],
        current_scope: str,
        current_target: Optional[str],
    ) -> Dict[str, Optional[str]]:
        targets: dict[str, Optional[str]] = {}
        for scope, promotion in prior_promotions.items():
            compact = self._compact_promotion_record(promotion)
            targets[scope] = compact.get("rollback_target") if compact else None
        targets[current_scope] = current_target
        return targets

    @staticmethod
    def _approval_record(
        approval: Optional[Dict[str, Any]],
        *,
        scope: str,
    ) -> Dict[str, Any]:
        raw: Dict[str, Any]
        if approval is None:
            raw = {}
        elif hasattr(approval, "model_dump"):
            raw = approval.model_dump(exclude_none=True)
        elif hasattr(approval, "dict"):
            raw = approval.dict(exclude_none=True)
        elif isinstance(approval, dict):
            raw = dict(approval)
        else:
            raw = {}
        approver = str(raw.get("approver") or raw.get("approved_by") or "").strip()
        reason = str(raw.get("reason") or raw.get("comment") or "").strip()
        signature = str(raw.get("signature") or raw.get("signed_approval") or "").strip()
        method = str(raw.get("method") or raw.get("approval_type") or "").strip().lower()
        if not method:
            method = "signed" if signature else "manual" if approver else None
        approved_flag = raw.get("approved") is True or raw.get("approval") is True
        signed_ok = bool(approver and signature)
        manual_ok = bool(approver and (reason or approved_flag))
        satisfied = bool(signed_ok or manual_ok)
        return {
            "required": scope != DEVELOPMENT_PROMOTION_SCOPE,
            "provided": bool(raw),
            "satisfied": satisfied,
            "method": method,
            "approver": approver or None,
            "reason": reason or None,
            "approved": approved_flag or satisfied,
            "signature_present": bool(signature),
            "signature_sha256": (
                ConfigPromoter._sha256_text(signature) if signature else None
            ),
        }

    @staticmethod
    def _production_gate_bundle_summary(scope: str) -> Dict[str, Any]:
        if scope != PRODUCTION_PROMOTION_SCOPE:
            return {"loaded": None, "applicable": False}
        try:
            bundle = load_production_gate_bundle(settings.workspace_root)
        except Exception as exc:
            return {
                "loaded": False,
                "applicable": True,
                "gate_bundle_id": None,
                "version": None,
                "scope": PRODUCTION_PROMOTION_SCOPE,
                "error": str(exc),
            }
        policy = bundle.get("promotion_policy", {})
        return {
            "loaded": True,
            "applicable": True,
            "gate_bundle_id": bundle.get("gate_bundle_id"),
            "version": bundle.get("version"),
            "scope": bundle.get("scope") or PRODUCTION_PROMOTION_SCOPE,
            "promotion_policy": policy,
            "gate_tiers": bundle.get("gate_tiers", {}),
            "promotion_blockers": bundle.get("promotion_blockers", []),
        }

    def _promotion_scope_evidence(
        self,
        *,
        metrics_payload: Dict[str, Any],
        development_metadata: Dict[str, Any],
        production_bundle: Dict[str, Any],
    ) -> Dict[str, Any]:
        evidence = self._promotion_evidence_container(metrics_payload)
        paper = self._paper_validation_evidence(metrics_payload, evidence)
        canary = self._canary_validation_evidence(
            metrics_payload,
            evidence,
            production_bundle=production_bundle,
        )
        return {
            "model_card": self._model_card_evidence(metrics_payload, evidence),
            "feature_readiness": self._feature_readiness_evidence(
                metrics_payload, evidence
            ),
            "paper_validation": paper,
            "canary_validation": canary,
            "inference_parity_reload": self._inference_scope_evidence(
                development_metadata
            ),
            "live_risk_limits": self._live_risk_limits_evidence(
                metrics_payload, evidence
            ),
            "monitoring_alerts": self._monitoring_alerts_evidence(
                metrics_payload, evidence
            ),
            "rl_oos": self._rl_oos_scope_evidence(
                metrics_payload, development_metadata
            ),
            "rl_economic_replay": self._rl_economic_replay_scope_evidence(
                metrics_payload
            ),
        }

    @staticmethod
    def _promotion_evidence_container(metrics_payload: Dict[str, Any]) -> Dict[str, Any]:
        for key in ("promotion_evidence", "deployment_evidence", "production_evidence"):
            value = metrics_payload.get(key)
            if isinstance(value, dict):
                return value
        return {}

    @staticmethod
    def _first_mapping(*values: Any) -> Dict[str, Any]:
        for value in values:
            if isinstance(value, dict):
                return value
        return {}

    @staticmethod
    def _truthy_status(container: Dict[str, Any]) -> bool:
        if any(
            container.get(key) is True
            for key in (
                "passed",
                "pass",
                "valid",
                "validated",
                "approved",
                "complete",
                "configured",
                "duration_passed",
                "min_duration_passed",
            )
        ):
            return True
        status = container.get("status")
        return isinstance(status, str) and status.strip().lower() in {
            "pass",
            "passed",
            "success",
            "succeeded",
            "approved",
            "complete",
            "configured",
        }

    @staticmethod
    def _model_card_evidence(
        metrics_payload: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        value = (
            metrics_payload.get("model_card")
            or evidence.get("model_card")
            or metrics_payload.get("model_card_path")
            or metrics_payload.get("model_card_uri")
            or evidence.get("model_card_path")
            or evidence.get("model_card_uri")
        )
        if isinstance(value, str):
            return {"passed": bool(value.strip()), "reference": value.strip() or None}
        card = value if isinstance(value, dict) else {}
        present = bool(
            card.get("path")
            or card.get("uri")
            or card.get("model_card_id")
            or card.get("content_hash")
            or card.get("complete") is True
            or card.get("approved") is True
        )
        blocked = any(card.get(key) is False for key in ("complete", "approved", "reviewed"))
        return {"passed": present and not blocked, "details": card}

    @staticmethod
    def _feature_readiness_evidence(
        metrics_payload: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        readiness = ConfigPromoter._first_mapping(
            metrics_payload.get("supervised_feature_readiness"),
            metrics_payload.get("feature_readiness"),
            metrics_payload.get("feature_readiness_report"),
            evidence.get("supervised_feature_readiness"),
            evidence.get("feature_readiness"),
        )
        direction = ConfigPromoter._first_mapping(
            readiness.get("direction"),
            readiness.get("direction_model"),
            metrics_payload.get("direction_feature_readiness"),
        )
        volatility = ConfigPromoter._first_mapping(
            readiness.get("volatility"),
            readiness.get("volatility_model"),
            metrics_payload.get("volatility_feature_readiness"),
        )
        passed = bool(
            metrics_payload.get("feature_readiness_passed") is True
            or readiness.get("passed") is True
            or (
                ConfigPromoter._truthy_status(direction)
                and ConfigPromoter._truthy_status(volatility)
            )
        )
        return {
            "passed": passed,
            "details": readiness,
            "direction": direction,
            "volatility": volatility,
        }

    @staticmethod
    def _paper_validation_evidence(
        metrics_payload: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        paper = ConfigPromoter._first_mapping(
            metrics_payload.get("paper_validation"),
            metrics_payload.get("paper_trading_validation"),
            metrics_payload.get("paper_validation_report"),
            evidence.get("paper_validation"),
            evidence.get("paper_trading_validation"),
        )
        return {"passed": ConfigPromoter._truthy_status(paper), "details": paper}

    @staticmethod
    def _canary_validation_evidence(
        metrics_payload: Dict[str, Any],
        evidence: Dict[str, Any],
        *,
        production_bundle: Dict[str, Any],
    ) -> Dict[str, Any]:
        canary = ConfigPromoter._first_mapping(
            metrics_payload.get("canary_validation"),
            metrics_payload.get("canary_duration"),
            metrics_payload.get("canary_report"),
            evidence.get("canary_validation"),
            evidence.get("canary_duration"),
        )
        tiers = production_bundle.get("gate_tiers") or {}
        canary_tier = tiers.get("canary_validation") or {}
        checks = canary_tier.get("checks") if isinstance(canary_tier, dict) else {}
        required_hours = ConfigPromoter._numeric_value(
            canary.get("required_duration_hours"),
            canary.get("min_duration_hours"),
            (checks or {}).get("min_duration_hours") if isinstance(checks, dict) else None,
        )
        observed_hours = ConfigPromoter._numeric_value(
            canary.get("duration_hours"),
            canary.get("observed_duration_hours"),
            canary.get("hours"),
        )
        duration_passed = bool(
            ConfigPromoter._truthy_status(canary)
            or (
                observed_hours is not None
                and required_hours is not None
                and observed_hours >= required_hours
            )
        )
        return {
            "passed": duration_passed,
            "duration_hours": observed_hours,
            "required_duration_hours": required_hours,
            "details": canary,
        }

    @staticmethod
    def _inference_scope_evidence(
        development_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        reload_validation = development_metadata.get("inference_reload_validation") or {}
        gate_bundle = development_metadata.get("gate_bundle") or {}
        return {
            "passed": (
                reload_validation.get("passed") is True
                and gate_bundle.get("passed") is True
            ),
            "reload_validation": reload_validation,
            "gate_bundle_passed": gate_bundle.get("passed"),
        }

    @staticmethod
    def _live_risk_limits_evidence(
        metrics_payload: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        limits = ConfigPromoter._first_mapping(
            metrics_payload.get("live_risk_limits"),
            metrics_payload.get("risk_limits"),
            metrics_payload.get("production_risk_limits"),
            evidence.get("live_risk_limits"),
            evidence.get("risk_limits"),
        )
        return {"passed": ConfigPromoter._truthy_status(limits), "details": limits}

    @staticmethod
    def _monitoring_alerts_evidence(
        metrics_payload: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        alerts = ConfigPromoter._first_mapping(
            metrics_payload.get("monitoring_alerts"),
            metrics_payload.get("alerts"),
            metrics_payload.get("production_monitoring"),
            evidence.get("monitoring_alerts"),
            evidence.get("alerts"),
        )
        blocking = bool(
            alerts.get("alerts_block_promotion")
            or alerts.get("blocking_alerts_present")
        )
        return {
            "passed": ConfigPromoter._truthy_status(alerts) and not blocking,
            "blocking_alerts_present": blocking,
            "details": alerts,
        }

    @staticmethod
    def _rl_oos_scope_evidence(
        metrics_payload: Dict[str, Any],
        development_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        rl_oos = metrics_payload.get("rl_oos") if isinstance(metrics_payload.get("rl_oos"), dict) else {}
        blockers = set((development_metadata.get("gate_bundle") or {}).get("blockers") or [])
        rl_blockers = {
            "missing_oof_provenance",
            "missing_volatility_oof_provenance",
            "missing_direction_feature_provenance",
            "missing_volatility_feature_provenance",
            "incomplete_direction_feature_provenance",
            "incomplete_volatility_feature_provenance",
            "missing_rl_feature_bundle_hash",
            "proxy_or_neutral_direction_proba_fallback",
            "proxy_or_neutral_volatility_feature_fallback",
            "stale_or_leaked_feature_provenance",
            "missing_nested_validation",
            "missing_multi_seed_rl_validation",
            "missing_rl_oos_metrics",
        }
        return {
            "passed": bool(rl_oos) and not bool(blockers & rl_blockers),
            "details": rl_oos,
            "development_blockers": sorted(blockers & rl_blockers),
        }

    @staticmethod
    def _rl_economic_replay_scope_evidence(
        metrics_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        replay = ConfigPromoter._first_mapping(
            metrics_payload.get("rl_economic_replay"),
            metrics_payload.get("economic_replay"),
        )
        gates = replay.get("gates") if isinstance(replay.get("gates"), dict) else {}
        passed = bool(
            replay
            and gates.get("all_gates_passed") is True
            and (
                replay.get("rl_profit_score") is not None
                or metrics_payload.get("rl_profit_score") is not None
            )
            and (
                first_valid_artifact_ref(
                    replay.get("artifact_hash"),
                    metrics_payload.get("rl_economic_replay_artifact_hash"),
                )
            )
        )
        return {"passed": passed, "details": replay}

    @staticmethod
    def _numeric_value(*values: Any) -> Optional[float]:
        for value in values:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _best_iteration_payload(best_iteration: Dict[str, Any]) -> Dict[str, Any]:
        raw = best_iteration.get("metrics_json")
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                normalize_artifact_references_in_mapping(parsed)
                return parsed
            return {}
        if isinstance(raw, dict):
            payload = dict(raw)
            normalize_artifact_references_in_mapping(payload)
            return payload
        return {}

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
                normalize_artifact_references_in_mapping(parsed)
                return parsed
        if isinstance(raw, dict):
            payload = dict(raw)
            normalize_artifact_references_in_mapping(payload)
            return payload
        embedded = metrics_payload.get("attempt_snapshot")
        if isinstance(embedded, dict):
            payload = dict(embedded)
            normalize_artifact_references_in_mapping(payload)
            return payload
        return {}

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
        serving_registry, serving_version = ConfigPromoter._model_version_components(
            metrics_payload
        )
        return {
            "mlflow_run_id": first_valid_artifact_ref(
                best_iteration.get("mlflow_run_id"),
                metrics_payload.get("mlflow_run_id"),
            ),
            "model_registry_name": metrics_payload.get("model_registry_name"),
            "model_version": metrics_payload.get("model_version"),
            "ensemble_model_registry_name": metrics_payload.get(
                "ensemble_model_registry_name"
            ),
            "ensemble_model_version": metrics_payload.get("ensemble_model_version"),
            "serving_model_registry_name": serving_registry,
            "serving_model_version": serving_version,
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
    def _metadata_sidecar_path(
        target_path: str,
        iteration: int,
        *,
        scope: str = DEVELOPMENT_PROMOTION_SCOPE,
    ) -> str:
        path = Path(target_path)
        return str(
            path.with_name(
                f"{path.name}.{scope}-promotion.iter-{iteration}.json"
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
        """Atomic write: tmp file → fsync → os.replace.

        Phase 3.1: durability hardening. A crash mid-write previously could
        leave a half-written config or metadata sidecar at the target path;
        the tmp+rename pattern guarantees readers either see the old
        complete content or the new complete content. The directory is also
        fsync'd so the rename itself survives a power loss.
        """
        await asyncio.to_thread(_atomic_write_text, path, content)

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
        training_gates_passed = training_gates_passed_from_iteration(best_iteration)
        payload["training_gates_passed"] = training_gates_passed
        payload["all_gates_passed"] = training_gates_passed
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
        structured = metrics_payload.get("tsfm_fallback_validation")
        if not isinstance(structured, dict):
            structured = {}
        is_tsfm = any(
            value is True
            for value in (
                metrics_payload.get("is_tsfm_candidate"),
                metrics_payload.get("tsfm_candidate"),
                inference.get("is_tsfm_candidate"),
                inference.get("tsfm_candidate"),
                structured.get("is_tsfm_candidate"),
            )
        )
        if not is_tsfm:
            for value in (
                metrics_payload.get("model_family"),
                metrics_payload.get("candidate_family"),
                inference.get("model_family"),
                inference.get("candidate_family"),
                structured.get("model_family"),
                structured.get("candidate_family"),
            ):
                if isinstance(value, str) and value.lower() in {
                    "tsfm",
                    "ts-fm",
                    "timesfm",
                }:
                    is_tsfm = True
                    break
        fallback_passed = structured.get("passed") is True or any(
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
            "passed": fallback_passed if is_tsfm else structured.get("passed"),
            "details": {
                "inference": inference,
                "adapter": adapter,
                "structured": structured,
            },
        }

    async def _build_quality_baseline_evaluation(
        self,
        *,
        research_id: str,
        best_iteration: Dict[str, Any],
        model_type: str,
        instrument: str,
        timeframe: str,
    ) -> Dict[str, Any]:
        current_metric = self._number(best_iteration.get("primary_metric"))
        current_metric_name = self._clean_metric_name(
            best_iteration.get("metric_name")
        )
        current_formula_version = self._formula_version(
            self._best_iteration_payload(best_iteration)
        )
        epsilon = float(settings.global_stagnation_epsilon)
        comparison: Dict[str, Any] = {
            "current_research_id": research_id,
            "current_iteration": best_iteration.get("iteration"),
            "current_metric": current_metric,
            "current_metric_name": current_metric_name,
            "baseline_promotion_id": None,
            "baseline_research_id": None,
            "baseline_iteration": None,
            "baseline_metric": None,
            "baseline_metric_name": None,
            "epsilon": epsilon,
            "delta": None,
        }
        checks: list[Dict[str, Any]] = []

        def add_check(
            name: str,
            status: str,
            *,
            reason: str | None = None,
            details: Dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                {
                    "name": name,
                    "status": status,
                    "reason": reason,
                    "details": details or {},
                }
            )

        if current_metric is None:
            add_check(
                "current_best_metric_recorded",
                "warning",
                details={"current_metric": best_iteration.get("primary_metric")},
            )
            return {
                "passed": True,
                "status": "not_comparable_missing_current_metric",
                "mode": QUALITY_BASELINE_MODE,
                "blockers": [],
                "checks": checks,
                "comparison": comparison,
            }

        add_check(
            "current_best_metric_recorded",
            "passed",
            details={
                "current_metric": current_metric,
                "current_metric_name": current_metric_name,
            },
        )
        baseline = await self._latest_eligible_development_baseline(
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
        )
        if baseline is None:
            add_check(
                "eligible_development_baseline_present",
                "warning",
                details={
                    "model_type": model_type,
                    "instrument": instrument,
                    "timeframe": timeframe,
                },
            )
            return {
                "passed": True,
                "status": "no_eligible_development_baseline",
                "mode": QUALITY_BASELINE_MODE,
                "blockers": [],
                "checks": checks,
                "comparison": comparison,
            }

        baseline_metric = self._promotion_best_metric(baseline)
        baseline_metric_name = self._promotion_metric_name(baseline)
        if baseline_metric is None:
            add_check(
                "eligible_development_baseline_present",
                "warning",
                details={"baseline_promotion_id": baseline.get("id")},
            )
            return {
                "passed": True,
                "status": "no_eligible_development_baseline",
                "mode": QUALITY_BASELINE_MODE,
                "blockers": [],
                "checks": checks,
                "comparison": comparison,
            }
        comparison.update(
            {
                "baseline_promotion_id": baseline.get("id"),
                "baseline_research_id": baseline.get("research_id"),
                "baseline_iteration": baseline.get("iteration"),
                "baseline_metric": baseline_metric,
                "baseline_metric_name": baseline_metric_name,
            }
        )
        add_check(
            "eligible_development_baseline_present",
            "passed",
            details={
                "baseline_promotion_id": baseline.get("id"),
                "baseline_research_id": baseline.get("research_id"),
                "baseline_iteration": baseline.get("iteration"),
            },
        )

        if (
            current_metric_name
            and baseline_metric_name
            and current_metric_name != baseline_metric_name
        ):
            add_check(
                "quality_metric_comparable",
                "warning",
                details={
                    "current_metric_name": current_metric_name,
                    "baseline_metric_name": baseline_metric_name,
                },
            )
            return {
                "passed": True,
                "status": "not_comparable_metric_name_mismatch",
                "mode": QUALITY_BASELINE_MODE,
                "blockers": [],
                "checks": checks,
                "comparison": comparison,
            }

        # R3: scores are NOT comparable across composite formula versions, even
        # when the metric NAME matches (composite_direction_score spans
        # v5_calibration / v6_sized_econ with different term semantics). A
        # raw numeric compare here wrongly blocks a newer-formula champion
        # behind an older-formula baseline (observed: v6 0.6969 blocked by v5
        # 0.7133, so every session re-derived from the stale promoted config).
        # The newer formula is the current scoring truth → pass through and
        # let the gates (floors / all_gates_passed) protect quality.
        baseline_formula_version = self._promotion_formula_version(baseline)
        comparison["current_formula_version"] = current_formula_version
        comparison["baseline_formula_version"] = baseline_formula_version
        # A numeric metric comparison is valid ONLY when both sides are the
        # SAME, explicitly-stamped formula version. Different versions — or a
        # baseline that predates version stamping (legacy promotions have no
        # composite_formula_version) — are not comparable (R3): pass through so
        # the current-formula champion isn't blocked by an incomparable number.
        # The gates (floors / all_gates_passed) still protect quality, and
        # going forward every promotion persists its version so same-version
        # comparisons resume strict.
        _formula_comparable = bool(
            current_formula_version
            and baseline_formula_version
            and current_formula_version == baseline_formula_version
        )
        if not _formula_comparable and (
            current_formula_version or baseline_formula_version
        ):
            add_check(
                "quality_formula_version_comparable",
                "warning",
                details={
                    "current_formula_version": current_formula_version,
                    "baseline_formula_version": baseline_formula_version,
                },
            )
            return {
                "passed": True,
                "status": "not_comparable_formula_version_mismatch",
                "mode": QUALITY_BASELINE_MODE,
                "blockers": [],
                "checks": checks,
                "comparison": comparison,
            }

        add_check(
            "quality_metric_comparable",
            "passed",
            details={
                "current_metric_name": current_metric_name,
                "baseline_metric_name": baseline_metric_name,
            },
        )
        delta = current_metric - baseline_metric
        threshold = baseline_metric - epsilon
        comparison["delta"] = delta
        passed = current_metric >= threshold
        blockers = [] if passed else [QUALITY_BASELINE_BLOCKER]
        add_check(
            "best_metric_not_below_development_baseline",
            "passed" if passed else "failed",
            reason=None if passed else QUALITY_BASELINE_BLOCKER,
            details={
                "current_metric": current_metric,
                "baseline_metric": baseline_metric,
                "delta": delta,
                "epsilon": epsilon,
                "minimum_allowed_metric": threshold,
            },
        )
        return {
            "passed": passed,
            "status": "passed" if passed else "blocked",
            "mode": QUALITY_BASELINE_MODE,
            "blockers": blockers,
            "checks": checks,
            "comparison": comparison,
        }

    async def _latest_eligible_development_baseline(
        self,
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
    ) -> Optional[Dict[str, Any]]:
        list_promotions = getattr(self._store, "list_promotions", None)
        if callable(list_promotions):
            rows = await list_promotions()
            ordered = sorted(
                [row for row in rows if isinstance(row, dict)],
                key=lambda row: (
                    str(row.get("promoted_at") or ""),
                    int(row.get("id") or 0),
                ),
                reverse=True,
            )
            for row in ordered:
                if self._development_baseline_matches(
                    row,
                    model_type=model_type,
                    instrument=instrument,
                    timeframe=timeframe,
                ) and self._development_baseline_eligible(row):
                    return row
            return None

        get_latest = getattr(
            self._store, "get_latest_development_promotion", None
        )
        if not callable(get_latest):
            return None
        row = await get_latest(
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
        )
        if not isinstance(row, dict):
            return None
        if not self._development_baseline_matches(
            row,
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
        ):
            return None
        if not self._development_baseline_eligible(row):
            return None
        return row

    @classmethod
    def _development_baseline_matches(
        cls,
        promotion: Dict[str, Any],
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
    ) -> bool:
        metadata = cls._promotion_metadata(promotion)
        scope = (
            promotion.get("scope")
            or metadata.get("scope")
            or DEVELOPMENT_PROMOTION_SCOPE
        )
        return bool(
            scope == DEVELOPMENT_PROMOTION_SCOPE
            and promotion.get("model_type") == model_type
            and promotion.get("instrument") == instrument
            and promotion.get("timeframe") == timeframe
        )

    @classmethod
    def _development_baseline_eligible(
        cls,
        promotion: Dict[str, Any],
    ) -> bool:
        metadata = cls._promotion_metadata(promotion)
        if promotion.get("rolled_back_at") or metadata.get("rolled_back_at"):
            return False
        if metadata.get("promotion_allowed") is not True:
            return False
        if cls._baseline_explicitly_unusable(metadata):
            return False
        return cls._promotion_best_metric(promotion) is not None

    @staticmethod
    def _promotion_metadata(promotion: Dict[str, Any]) -> Dict[str, Any]:
        metadata = promotion.get("promotion_metadata")
        return metadata if isinstance(metadata, dict) else {}

    @classmethod
    def _promotion_best_metric(cls, promotion: Dict[str, Any]) -> Optional[float]:
        metadata = cls._promotion_metadata(promotion)
        return cls._number(
            metadata.get("best_metric"),
            promotion.get("best_metric"),
            promotion.get("metric_value"),
            promotion.get("primary_metric"),
        )

    @classmethod
    def _promotion_metric_name(cls, promotion: Dict[str, Any]) -> Optional[str]:
        metadata = cls._promotion_metadata(promotion)
        return cls._clean_metric_name(
            metadata.get("metric_name") or promotion.get("metric_name")
        )

    @staticmethod
    def _baseline_explicitly_unusable(metadata: Dict[str, Any]) -> bool:
        return (
            metadata.get("quality_baseline_usable") is False
            or metadata.get("quality_baseline_unusable") is True
        )

    @staticmethod
    def _number(*values: Any) -> Optional[float]:
        for value in values:
            if value is None or isinstance(value, bool):
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                return number
        return None

    @staticmethod
    def _clean_metric_name(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _formula_version(cls, payload: Dict[str, Any]) -> Optional[str]:
        """composite_formula_version from a metrics payload (top-level mirror
        or the composite_components blob). None when absent."""
        if not isinstance(payload, dict):
            return None
        version = payload.get("composite_formula_version")
        if not version:
            components = payload.get("composite_components")
            if isinstance(components, dict):
                version = components.get("composite_formula_version")
        return cls._clean_metric_name(version)

    @classmethod
    def _promotion_formula_version(cls, promotion: Dict[str, Any]) -> Optional[str]:
        metadata = cls._promotion_metadata(promotion)
        return cls._clean_metric_name(
            metadata.get("composite_formula_version")
        )

    async def _promotion_iterations(
        self,
        research_id: str,
        best_iteration: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        getter = getattr(self._store, "get_iterations", None)
        if getter is None:
            return [best_iteration]
        try:
            rows = await getter(research_id)
        except TypeError:
            return [best_iteration]
        if not rows:
            return [best_iteration]
        return list(rows)

    @staticmethod
    def _with_blocker_details(
        evaluation: Dict[str, Any],
        *,
        metrics_payload: Dict[str, Any],
        phase_state: Dict[str, Any],
        source: str,
    ) -> Dict[str, Any]:
        annotated = dict(evaluation)
        annotated["blocker_details"] = classify_blockers(
            annotated.get("blockers", []),
            checks=annotated.get("checks", []),
            metrics_payload=metrics_payload,
            phase_state=phase_state,
            source=source,
        )
        return annotated

    @staticmethod
    def _merge_blocker_details(*detail_groups: Any) -> list[Dict[str, Any]]:
        merged: list[Dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for group in detail_groups:
            if not isinstance(group, list):
                continue
            for detail in group:
                if not isinstance(detail, dict):
                    continue
                key = (str(detail.get("source", "")), str(detail.get("code", "")))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(dict(detail))
        return merged

    @staticmethod
    def _merge_blockers(*blocker_groups: Any) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for group in blocker_groups:
            if isinstance(group, str):
                group = [group]
            if not isinstance(group, list):
                continue
            for blocker in group:
                text = str(blocker).strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                merged.append(text)
        return merged

    def _evaluate_gate_bundle(
        self,
        model_type: str,
        best_iteration: Dict[str, Any],
        *,
        instrument: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate the best iteration against the development gate bundle.

        MQ-C1: when the instrument identity is provided, per-instrument gate
        thresholds (``gates_overrides`` in the promoted instrument config) are
        overlaid onto the bundle before evaluation, with provenance recorded
        in the result.
        """
        try:
            bundle = load_gate_bundle(settings.workspace_root)
            bundle = apply_instrument_gate_overrides(
                bundle,
                instrument=instrument,
                timeframe=timeframe,
                workspace_root=settings.workspace_root,
            )
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

    @staticmethod
    def _apply_pipeline_feature_replay_policy(
        *,
        session: Dict[str, Any],
        model_type: str,
        gate_bundle_evaluation: Dict[str, Any],
        consistency_report: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Do not require standalone economic replay for pipeline feature phases.

        Direction and volatility phases in the pipeline produce supervised
        features for the RL policy. Their own promotion path may still demand
        calibration, feature parity, rollback, smoke, and reload evidence, but
        a missing standalone economic replay is not enough by itself to block
        the phase handoff.
        """
        if not session.get("pipeline_id"):
            return gate_bundle_evaluation, consistency_report
        if model_type not in {"direction", "volatility"}:
            return gate_bundle_evaluation, consistency_report

        allowed = {"missing_economic_replay"}
        gate_blockers = set(gate_bundle_evaluation.get("blockers") or [])
        consistency_blockers = set(consistency_report.get("blockers") or [])
        all_blockers = gate_blockers | consistency_blockers
        if not all_blockers or not all_blockers.issubset(allowed):
            return gate_bundle_evaluation, consistency_report

        gate_eval = dict(gate_bundle_evaluation)
        gate_eval["blockers"] = [
            blocker
            for blocker in gate_bundle_evaluation.get("blockers", [])
            if blocker not in allowed
        ]
        gate_eval["checks"] = [
            ConfigPromoter._waive_missing_replay_check(check)
            for check in gate_bundle_evaluation.get("checks", [])
        ]
        gate_eval["passed"] = not gate_eval["blockers"]
        notes = list(gate_eval.get("notes") or [])
        notes.append(
            "pipeline_feature_phase_missing_economic_replay_allowed"
        )
        gate_eval["notes"] = notes
        gate_eval["waivers"] = sorted(
            set(gate_eval.get("waivers") or [])
            | {"pipeline_feature_phase_missing_economic_replay"}
        )

        consistency = dict(consistency_report)
        consistency["blockers"] = [
            blocker
            for blocker in consistency_report.get("blockers", [])
            if blocker not in allowed
        ]
        consistency["checks"] = [
            ConfigPromoter._warn_missing_replay_check(check)
            for check in consistency_report.get("checks", [])
        ]
        consistency["passed"] = not consistency["blockers"]
        notes = list(consistency.get("notes") or [])
        notes.append(
            "pipeline_feature_phase_missing_economic_replay_allowed"
        )
        consistency["notes"] = notes
        return gate_eval, consistency

    @staticmethod
    def _waive_missing_replay_check(check: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(check)
        if (
            updated.get("status") == "failed"
            and updated.get("reason") == "missing_economic_replay"
        ):
            updated["status"] = "waived"
            updated["waiver"] = "pipeline_feature_phase_missing_economic_replay"
        return updated

    @staticmethod
    def _warn_missing_replay_check(check: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(check)
        if (
            updated.get("status") == "failed"
            and updated.get("name") == "economic_replay_present"
        ):
            updated["status"] = "warning"
            updated["detail"] = "pipeline feature phase; RL owns economic replay"
        return updated

    def _resolve_artifacts_dir(
        self,
        workspace_path: str,
        model_type: str,
        instrument: str,
        timeframe: str,
        *,
        metrics_payload: Optional[Dict[str, Any]] = None,
        attempt_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Find the directory containing trained model .pkl files."""
        inst_under = instrument.replace("-", "_")

        for container in (metrics_payload or {}, attempt_snapshot or {}):
            resolved = self._artifacts_dir_from_payload(container)
            if resolved:
                return resolved

        # Check immutable result artifact for explicit model_path.
        for container in (metrics_payload or {}, attempt_snapshot or {}):
            artifact_path = container.get("result_artifact_path")
            if not artifact_path:
                continue
            try:
                with open(artifact_path, encoding="utf-8") as f:
                    data = json.load(f)
                resolved = self._artifacts_dir_from_payload(data)
                if resolved:
                    return resolved
            except Exception:
                pass

        # Backward-compatible fallback: check live results.json for model_path.
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

    @staticmethod
    def _artifacts_dir_from_payload(payload: Dict[str, Any]) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        model_rel = payload.get("model_path")
        if not model_rel:
            model_info = payload.get("model")
            if isinstance(model_info, dict):
                model_rel = model_info.get("path")
        model_rel = normalize_optional_artifact_ref(model_rel)
        if not model_rel:
            return None
        model_abs = (
            model_rel
            if os.path.isabs(model_rel)
            else os.path.join(settings.workspace_root, model_rel)
        )
        if os.path.isfile(model_abs):
            return os.path.dirname(model_abs)
        if os.path.isdir(model_abs):
            return model_abs
        return None

    async def _update_composite_versions(
        self,
        instrument: str,
        model_type: str,
        version_tag: str,
    ) -> None:
        """PATCH the composite in mlflow-service with the new model version.

        Uses the service-token protected PATCH /by-instrument/{instrument}/versions
        endpoint. If no composite exists (404), logs a warning and moves on.
        """
        version_key = self._composite_version_key(model_type)
        if not version_key:
            logger.warning(
                "Unknown model_type %r — skipping composite update", model_type,
            )
            return
        headers = self._mlflow_service_auth_headers(require_token=False)
        if not headers:
            logger.warning(
                "Skipping composite update for %s: no mlflow-service auth token configured",
                instrument,
            )
            return

        url = (
            f"{settings.mlflow_service_url.rstrip('/')}{MLFLOW_COMPOSITES_API_PREFIX}"
            f"/by-instrument/{instrument}/versions"
        )
        body = {version_key: version_tag}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.patch(url, headers=headers, json=body)
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
