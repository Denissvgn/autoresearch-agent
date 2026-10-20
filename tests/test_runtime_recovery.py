from __future__ import annotations

import asyncio
import json
import os
import sys
import types
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    class _FakeAsyncAnthropic:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class _FakeAPIStatusError(Exception):
        status_code = 500

    sys.modules["anthropic"] = cast(ModuleType, types.SimpleNamespace(
        AsyncAnthropic=_FakeAsyncAnthropic,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=_FakeAPIStatusError,
    ))

from src.core.orchestrator import AgentOrchestrator
from src.core.results_store import ResultsStore
from src.core.session_manager import SessionManager


async def _create_session(
    store: ResultsStore,
    *,
    session_id: str,
    workspace: Path,
) -> None:
    await store.create_session(
        session_id=session_id,
        instrument="default",
        timeframe="production",
        # ARC-012 P7-010: a resumable/continuable row must name an installed
        # skill — the legacy model_type-only shape is refused at continue.
        model_type="",
        skill_id="prompt-engineering",
        subject_id="default",
        variant="production",
        tag=session_id,
        quick_mode=True,
        max_iterations=3,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path=str(workspace),
        manifest_path=str(workspace / "research_manifest.json"),
        manifest_json=json.dumps({"research_id": session_id}),
        manifest_hash="manifest-sha",
    )


@pytest.mark.asyncio
async def test_orphaned_running_session_becomes_resumable(tmp_path: Path):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "direction"
    workspace.mkdir(parents=True)
    (workspace / "research_manifest.json").write_text("{}", encoding="utf-8")
    await _create_session(store, session_id="res_orphan", workspace=workspace)
    command = await store.record_runtime_command(
        research_id="res_orphan",
        turn=2,
        tool_name="bash",
        command=".venv/bin/python scripts/autotuner/direction/prepare.py --quick",
        timeout_s=900,
    )

    manager = SessionManager(store)
    summary = await manager.recover_orphaned_sessions()

    session = await store.get_session("res_orphan")
    commands = await store.list_runtime_commands(command_id=command["id"])
    assert summary["resumable"] == 1
    assert session["status"] == "resumable"
    assert "operator action" in session["error_message"].lower()
    assert commands[0]["status"] == "interrupted"
    assert "service restart" in commands[0]["error_message"].lower()


@pytest.mark.asyncio
async def test_runtime_resume_requires_operator_and_creates_chained_session(
    tmp_path: Path,
):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "direction"
    workspace.mkdir(parents=True)
    await _create_session(store, session_id="res_parent", workspace=workspace)
    await store.update_session("res_parent", status="resumable")

    class FakeOrchestrator:
        async def run(self, config) -> None:
            await store.update_session(config.id, status="completed")

        def request_stop(self, research_id: str) -> None:
            pass

        def request_pause(self, research_id: str) -> None:
            pass

        def request_resume(self, research_id: str) -> None:
            pass

    manager = SessionManager(store)
    manager._orchestrator = FakeOrchestrator()

    async def healthy_preflight(model_type: str):
        return {"schema_version": "autoresearch_service_preflight.v1", "status": "ready"}

    manager._run_preflight = healthy_preflight

    resumed = await manager.resume_interrupted_session(
        "res_parent",
        reason="operator reviewed restart recovery state",
        max_iterations=1,
    )
    await asyncio.sleep(0)

    assert resumed["resumed_from"] == "res_parent"
    parent = await store.get_session("res_parent")
    assert "Runtime resume requested" in parent["error_message"]


@pytest.mark.asyncio
async def test_timeout_attempt_snapshot_remains_inspectable(tmp_path: Path):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "direction"
    workspace.mkdir(parents=True)
    await _create_session(store, session_id="res_timeout", workspace=workspace)

    marker = {
        "status": "timeout",
        "primary_metric": None,
        "metric_name": None,
        "all_gates_passed": False,
        "decision": "discard",
        "description": "server-detected training command timeout",
        "config_snapshot": "agent_strategy: BALA\n",
        "runtime_command": {
            "id": 42,
            "status": "timed_out",
            "timed_out": True,
            "returncode": -15,
        },
    }
    await AgentOrchestrator(store)._record_iteration(
        "res_timeout",
        1,
        marker,
        0.0,
        workspace=str(workspace),
        turn=3,
        command=(
            ".venv/bin/python scripts/autotuner/direction/prepare.py "
            "--config runs/autotuner/DOGE_USDT_15m/direction/train.yaml --quick"
        ),
    )

    row = await store.get_iteration("res_timeout", 1)
    metrics = json.loads(row["metrics_json"])
    snapshot = json.loads(row["attempt_snapshot_json"])
    assert metrics["status"] == "timeout"
    assert snapshot["status"] == "timeout"
    assert snapshot["runtime_command"]["status"] == "timed_out"
    assert Path(row["attempt_snapshot_path"]).exists()
