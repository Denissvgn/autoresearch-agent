from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from .logging import get_contextual_logger
from ..io import artifacts as artifacts_io
from ..io.artifacts import write_bytes, write_json, write_text, copy_file
from ..tracking.experiments import RunStore


@dataclass
class RunContext:
    """Run context carrying metadata and lightweight logging helpers."""

    run_id: str
    seed: int
    experiment: str
    tags: dict[str, str] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    ended_at: Optional[str] = None
    _logger_level: str = "INFO"
    _logger_json: bool = False
    runs_root: Optional[str] = None
    _store: Optional[RunStore] = None

    @property
    def logger(self):
        return get_contextual_logger(
            "traid_training_sdk.run",
            level=self._logger_level,
            json_mode=self._logger_json,
            run_id=self.run_id,
            experiment=self.experiment,
            component="run",
        )

    def log_metrics(self, metrics: Mapping[str, Any], *, step: Optional[int] = None) -> None:
        msg = {"event": "metrics", "metrics": dict(metrics)}
        if step is not None:
            self.logger.info(msg, extra={"step": step})
        else:
            self.logger.info(msg)
        if self._store is not None:
            self._store.append_metrics(dict(metrics), step=step)

    def log_artifact(self, artifact: Any, *, name: Optional[str] = None) -> None:
        target_dir = None
        if self.runs_root:
            target_dir = artifacts_io.artifacts_dir(self.runs_root, self.run_id)
        self.logger.debug({"event": "artifact", "name": name or "unnamed"})
        if target_dir is None:
            return
        if isinstance(artifact, (bytes, bytearray)):
            if not name:
                name = "artifact.bin"
            p = write_bytes(target_dir / name, bytes(artifact))
        elif isinstance(artifact, str):
            # Interpret as path or text content
            src = Path(artifact)
            if src.exists():
                p = copy_file(src, target_dir / (name or src.name))
            else:
                p = write_text(target_dir / (name or "artifact.txt"), artifact)
        elif isinstance(artifact, dict):
            p = write_json(target_dir / (name or "artifact.json"), artifact)
        else:
            # Fallback to string repr
            p = write_text(target_dir / (name or "artifact.txt"), str(artifact))
        if self._store is not None:
            rel = str(p.relative_to(Path(self.runs_root) / self.run_id)) if self.runs_root else p.name
            self._store.add_artifact(name or p.name, rel)


def new_run_context(
    *,
    seed: Optional[int] = None,
    experiment: str = "default",
    tags: Optional[Mapping[str, str]] = None,
    logger_level: str = "INFO",
    logger_json: bool = False,
    ) -> RunContext:
    """Create a new RunContext with deterministic seed policy and metadata."""
    actual_seed = seed if seed is not None else secrets.randbits(32)
    if env_seed := os.getenv("TRAID_SDK_SEED"):
        try:
            actual_seed = int(env_seed)
        except ValueError:
            pass
    run_id = secrets.token_hex(8)
    return RunContext(
        run_id=run_id,
        seed=actual_seed,
        experiment=experiment,
        tags=dict(tags or {}),
        _logger_level=logger_level,
        _logger_json=logger_json,
        runs_root=None,
        _store=None,
    )
