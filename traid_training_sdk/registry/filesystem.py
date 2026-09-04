from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Sequence

from .base import ModelRegistry, RegistryEntry


def _atomic_replace(src: Path, dst: Path) -> None:
    os.replace(src, dst)


def _next_version(model_dir: Path) -> int:
    if not model_dir.exists():
        return 1
    versions = [int(p.name) for p in model_dir.iterdir() if p.is_dir() and p.name.isdigit()]
    return (max(versions) + 1) if versions else 1


class FilesystemRegistry(ModelRegistry):
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _model_dir(self, name: str) -> Path:
        return self.root / name

    def register(self, *, model, name: str, metadata: dict | None = None) -> int:
        model_dir = self._model_dir(name)
        version = _next_version(model_dir)
        tmp_dir = model_dir / f".{version}.tmp"
        final_dir = model_dir / str(version)

        # Prepare
        tmp_dir.mkdir(parents=True, exist_ok=True)
        # Delegate model persistence
        model_path = tmp_dir / "model.bin"
        if hasattr(model, "save"):
            model.save(str(model_path))
        else:  # pragma: no cover - safety path
            from ..models.base import joblib_save

            joblib_save(model, model_path)
        meta = metadata or {}
        (tmp_dir / "meta.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")

        # Atomic move into place
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        if final_dir.exists():  # pragma: no cover - unlikely race
            shutil.rmtree(final_dir)
        _atomic_replace(tmp_dir, final_dir)
        return version

    def list(self, name: str) -> Sequence[int]:
        model_dir = self._model_dir(name)
        if not model_dir.exists():
            return []
        return sorted(int(p.name) for p in model_dir.iterdir() if p.is_dir() and p.name.isdigit())

    def get(self, name: str, version: int) -> RegistryEntry:
        p = self._model_dir(name) / str(version)
        return RegistryEntry(name=name, version=version, path=p / "model.bin", meta_path=p / "meta.json")

    def promote(self, name: str, version: int, stage: str) -> None:
        stage_dir = self._model_dir(name) / "stages"
        stage_dir.mkdir(parents=True, exist_ok=True)
        (stage_dir / f"{stage}.json").write_text(json.dumps({"version": version}), encoding="utf-8")

