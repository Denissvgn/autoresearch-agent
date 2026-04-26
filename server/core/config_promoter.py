"""Config promoter — previews and writes winning configs to the host bind mount."""

from __future__ import annotations

import asyncio
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

        gate_bundle_evaluation = self._evaluate_gate_bundle(model_type, best)
        promotion_allowed = bool(best["all_gates_passed"]) and gate_bundle_evaluation.get(
            "passed",
            False,
        )
        candidate_pool_record = {
            "source": "autoresearch.iterations",
            "research_id": research_id,
            "iteration": best["iteration"],
            "status": "eligible" if promotion_allowed else "blocked",
            "blockers": gate_bundle_evaluation.get("blockers", []),
            "inspectable": True,
            "promotion_record_created": False,
        }
        metrics_payload = self._best_iteration_payload(best)
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
        )

        return {
            "research_id": research_id,
            "iteration": best["iteration"],
            "model_type": model_type,
            "instrument": instrument,
            "timeframe": timeframe,
            "target_path": target_path,
            "new_config": best_yaml,
            "current_config": previous_yaml,
            "best_metric": best["primary_metric"],
            "gates_passed": bool(best["all_gates_passed"]),
            "gate_bundle_evaluation": gate_bundle_evaluation,
            "candidate_pool_record": candidate_pool_record,
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
    ) -> Dict[str, Any]:
        """Create the auditable development promotion decision artifact."""
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
            },
            "registry_metadata": self._registry_metadata(
                best_iteration, metrics_payload
            ),
            "composite_metadata": self._composite_metadata(metrics_payload),
            "rollback_target": (
                metrics_payload.get("rollback_target")
                or metrics_payload.get("previous_development_version")
            ),
            "smoke_validation": (
                metrics_payload.get("smoke_validation")
                or {"passed": metrics_payload.get("smoke_validation_passed")}
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
