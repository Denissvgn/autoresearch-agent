from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..io.serialization import load_json, save_json


@dataclass(frozen=True)
class RunMeta:
    run_id: str
    experiment: str
    started_at: str  # ISO8601 timestamp

    @staticmethod
    def new(run_id: str, experiment: str) -> "RunMeta":
        return RunMeta(
            run_id=run_id,
            experiment=experiment,
            started_at=datetime.now(tz=timezone.utc).isoformat(),
        )


def write_run_meta(path: str | Path, meta: RunMeta) -> None:
    save_json(path, asdict(meta))


def read_run_meta(path: str | Path) -> RunMeta:
    raw: dict[str, Any] = load_json(path)
    return RunMeta(**raw)


@dataclass
class RunStore:
    runs_root: Path
    run_id: str
    experiment: str
    seed: int
    tags: dict[str, str]
    started_at: str
    ended_at: Optional[str] = None
    metrics: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, str]] = field(default_factory=list)

    @property
    def run_dir(self) -> Path:
        return self.runs_root / self.run_id

    @property
    def run_json(self) -> Path:
        return self.run_dir / "run.json"

    @property
    def artifacts_dir(self) -> Path:
        return self.run_dir / "artifacts"

    def init(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._flush()

    def _flush(self) -> None:
        payload = {
            "run_id": self.run_id,
            "experiment": self.experiment,
            "seed": self.seed,
            "tags": self.tags,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
        }
        save_json(self.run_json, payload)

    def append_metrics(self, metrics: dict[str, Any], *, step: Optional[int] = None) -> None:
        entry = {"metrics": metrics}
        if step is not None:
            entry["step"] = step
        entry["ts"] = datetime.now(tz=timezone.utc).isoformat()
        self.metrics.append(entry)
        self._flush()

    def add_artifact(self, name: str, rel_path: str) -> None:
        self.artifacts.append({"name": name, "path": rel_path})
        self._flush()

    def finalize(self) -> None:
        self.ended_at = datetime.now(tz=timezone.utc).isoformat()
        self._flush()
