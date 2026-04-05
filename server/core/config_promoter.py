"""Config promoter — previews and writes winning configs to the host bind mount."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import yaml

from server.config import settings
from server.core.results_store import ResultsStore

logger = logging.getLogger(__name__)


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

        # Determine target path on host
        target_path = self._get_target_path(model_type, instrument, timeframe)

        # Read current config if it exists
        previous_yaml: Optional[str] = None
        if os.path.exists(target_path):
            previous_yaml = Path(target_path).read_text(encoding="utf-8")

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
        }

    async def confirm(self, research_id: str) -> Dict[str, Any]:
        """Execute the promotion: write best config to host bind mount."""
        preview = await self.preview(research_id)

        if not preview["gates_passed"]:
            raise ValueError(
                "Cannot promote: best iteration did not pass all gates"
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
    def _get_target_path(
        model_type: str, instrument: str, timeframe: str,
    ) -> str:
        """Determine the host config file path for promotion."""
        host_configs = settings.host_configs_path
        if model_type in ("direction", "volatility"):
            return os.path.join(
                host_configs,
                "instrument_configs",
                f"{instrument}_{timeframe}.yaml",
            )
        elif model_type == "rl":
            return os.path.join(
                host_configs,
                "rl",
                f"{instrument}_{timeframe}_production.yaml",
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")
