"""Shared pytest configuration for the training SDK tests.

The training SDK is not always installed as a package when contributors run the
suite locally (they often rely on "pip install -r requirements-test.txt").
To keep the tests runnable without an editable install we explicitly add the
repo root (and the SDK directory itself) to ``sys.path`` before test collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

def _ensure_on_path(path: Path) -> None:
    """Append *path* to ``sys.path`` if it is not already present."""
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SDK_ROOT = PROJECT_ROOT / "traid_training_sdk"

_ensure_on_path(PROJECT_ROOT)
_ensure_on_path(SDK_ROOT)
