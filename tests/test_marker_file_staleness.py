from __future__ import annotations

import os
import sys
import time
import types
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    _stub = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = _stub

from src.core import orchestrator as orchestrator_module
from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.results_store import ResultsStore


_FRESH_MARKER = "\n".join(
    [
        "---",
        "status:             completed",
        "primary_metric:     0.643492",
        "metric_name:        composite_direction_score",
        "direction:          higher_is_better",
        "training_gates_passed: true",
        "all_gates_passed:   true",
        "---",
    ]
)


@pytest.mark.asyncio
async def test_stale_marker_is_ignored_when_min_mtime_in_future(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "workspace-root"
    workspace = root / "runs" / "autotuner" / "DOGE_USDT_15m" / "direction"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(orchestrator_module.settings, "workspace_root", str(root))

    marker_path = workspace / "last_metrics.txt"
    marker_path.write_text(_FRESH_MARKER, encoding="utf-8")

    stale_mtime = time.time() - 600.0
    os.utime(marker_path, (stale_mtime, stale_mtime))

    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    orchestrator = AgentOrchestrator(store)

    text = orchestrator._read_marker_file(
        ResearchConfig(
            id="res_test",
            instrument="DOGE_USDT",
            timeframe="15m",
            model_type="direction",
        ),
        min_mtime=time.time(),
    )

    assert text is None, "stale marker should be ignored when min_mtime is fresh"
    assert marker_path.exists(), "stale marker must not be consumed"


@pytest.mark.asyncio
async def test_fresh_marker_is_consumed_when_min_mtime_in_past(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "workspace-root"
    workspace = root / "runs" / "autotuner" / "DOGE_USDT_15m" / "direction"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(orchestrator_module.settings, "workspace_root", str(root))

    marker_path = workspace / "last_metrics.txt"
    marker_path.write_text(_FRESH_MARKER, encoding="utf-8")

    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    orchestrator = AgentOrchestrator(store)

    text = orchestrator._read_marker_file(
        ResearchConfig(
            id="res_test",
            instrument="DOGE_USDT",
            timeframe="15m",
            model_type="direction",
        ),
        min_mtime=time.time() - 3600.0,
    )

    assert text is not None
    assert "primary_metric:     0.643492" in text
    assert not marker_path.exists(), "consumed marker should be removed"


@pytest.mark.asyncio
async def test_marker_read_without_min_mtime_preserves_legacy_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "workspace-root"
    workspace = root / "runs" / "autotuner" / "DOGE_USDT_15m" / "direction"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(orchestrator_module.settings, "workspace_root", str(root))

    marker_path = workspace / "last_metrics.txt"
    marker_path.write_text(_FRESH_MARKER, encoding="utf-8")

    stale_mtime = time.time() - 86400.0
    os.utime(marker_path, (stale_mtime, stale_mtime))

    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    orchestrator = AgentOrchestrator(store)

    text = orchestrator._read_marker_file(
        ResearchConfig(
            id="res_test",
            instrument="DOGE_USDT",
            timeframe="15m",
            model_type="direction",
        ),
    )

    assert text is not None, "no min_mtime → no staleness check → marker is read"
