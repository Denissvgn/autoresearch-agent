"""Config promoter — previews and writes winning configs to the host bind mount."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

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

        # Read best_train.yaml from workspace
        best_config_path = os.path.join(workspace_path, "best_train.yaml")
        if not os.path.exists(best_config_path):
            raise FileNotFoundError(
                f"best_train.yaml not found at {best_config_path}"
            )

        best_yaml = Path(best_config_path).read_text(encoding="utf-8")

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
            "best_yaml": best_yaml,
            "previous_yaml": previous_yaml,
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
        workspace_path = (await self._store.get_session(research_id))["workspace_path"]

        # Use promote.py script if available, otherwise write directly
        promote_script = os.path.join(
            settings.autotuner_scripts_dir, "promote.py",
        )
        if os.path.exists(promote_script):
            cmd = [
                settings.venv_python,
                promote_script,
                "--model", model_type,
                "--workspace", os.path.dirname(workspace_path),
                "--instrument", instrument,
                "--timeframe", timeframe,
            ]
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
                Path(target_path).write_text, preview["best_yaml"], encoding="utf-8",
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
            config_yaml=preview["best_yaml"],
            previous_yaml=preview["previous_yaml"],
        )

        return promotion

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
