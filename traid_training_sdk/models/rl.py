from __future__ import annotations

import shutil
from pathlib import Path


class RLModelArtifact:
    """Wrapper to register RL artifacts with FilesystemRegistry."""

    def __init__(self, artifact_path: str | Path) -> None:
        self.artifact_path = Path(artifact_path)
        if not self.artifact_path.exists():
            raise FileNotFoundError(f"RL artifact not found: {self.artifact_path}")

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.artifact_path, target)

