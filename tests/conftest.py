from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.results_store import ResultsStore


@pytest.fixture(autouse=True)
async def close_initialized_results_stores(monkeypatch: pytest.MonkeyPatch):
    """Close long-lived SQLite connections created by tests."""

    stores: list[ResultsStore] = []
    original_initialize = ResultsStore.initialize

    async def tracked_initialize(self: ResultsStore) -> None:
        await original_initialize(self)
        stores.append(self)

    monkeypatch.setattr(ResultsStore, "initialize", tracked_initialize)
    yield
    for store in reversed(stores):
        await store.close()
