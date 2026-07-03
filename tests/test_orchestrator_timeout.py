"""Tests for ARC-011 P0-006 / P0-007 — hard wall-clock bound.

Verifies that a governed command which would overrun the session timeout is
reaped at the session boundary, and that an operator-stop cancel reaps the
in-flight subprocess tree through the ``CommandProcessRegistry`` even though
cancelling ``asyncio.to_thread`` cannot interrupt the worker thread that owns
the ``Popen`` handle.

  1. Orchestrator-level: a hung command is capped at the session's remaining
     soft budget, the command_runner's own psutil kill fires, and the session
     ends ``timed_out`` within ``timeout_s`` + slack (AC#1, AC#3).
  2. Registry-level: ``kill_all`` (invoked from the orchestrator's cancel
     handler) reaps an in-flight subprocess that a ``to_thread`` cancel could
     not (AC#2).
  3. Unit: the cap math (floor respected when budget ample; cap wins when
     budget < floor) and registry membership mechanics.
"""

from __future__ import annotations

import asyncio
import sys
import time
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub the Anthropic SDK so the orchestrator imports without a real SDK/key.
try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    sys.modules["anthropic"] = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )

from src.core.command_runner import CommandProcessRegistry, CommandRunResult, GovernedCommandRunner
from src.core.orchestrator import AgentOrchestrator, ResearchConfig, _tool_bash
from src.core.results_store import ResultsStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _process_exists(pid: int) -> bool:
    try:
        import psutil

        return psutil.pid_exists(pid)
    except ImportError:  # pragma: no cover
        import os

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


def _make_config(research_id: str, workspace: str, *, timeout_s: int = 2) -> ResearchConfig:
    return ResearchConfig(
        id=research_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="p0-006",
        max_iterations=3,
        max_budget_usd=100.0,
        workspace_path=workspace,
        timeout_s=timeout_s,
    )


async def _seed_session(store: ResultsStore, config: ResearchConfig) -> None:
    await store.create_session(
        session_id=config.id,
        instrument=config.instrument,
        timeframe=config.timeframe,
        model_type=config.model_type,
        tag=config.tag,
        quick_mode=config.quick_mode,
        max_iterations=config.max_iterations,
        max_budget_usd=config.max_budget_usd,
        focus_hint=config.focus_hint,
        workspace_path=config.workspace_path,
    )


def _fake_bash_tool_use(command: str, tool_id: str = "toolu_p006"):
    """A minimal Anthropic-shaped response containing one bash tool_use block."""
    return types.SimpleNamespace(
        content=[
            types.SimpleNamespace(
                type="tool_use",
                name="bash",
                input={"command": command, "timeout_s": 7200},
                id=tool_id,
            )
        ],
        usage=types.SimpleNamespace(input_tokens=1, output_tokens=1),
        stop_reason="tool_use",
    )


def _make_hanging_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """A workspace with ``.venv/bin/python`` symlink + a hanging autotuner script.

    Mirrors ``tests/test_command_policy.py:207`` so the command is policy-
    allowed. The script writes a grandchild pid then sleeps 60s.
    """
    workspace = tmp_path / "ws"
    python_path = workspace / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    child_pid_path = workspace / "child.pid"
    script = workspace / "scripts" / "autotuner" / "enrich_rl_dataset.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "\n".join(
            [
                "import pathlib, subprocess, sys, time",
                (
                    "child = subprocess.Popen([sys.executable, '-c', "
                    "'import time; time.sleep(60)'], start_new_session=True)"
                ),
                f"pathlib.Path({str(child_pid_path)!r}).write_text(str(child.pid))",
                "time.sleep(60)",
            ]
        ),
        encoding="utf-8",
    )
    return workspace, child_pid_path


_HANGING_COMMAND = (
    ".venv/bin/python scripts/autotuner/enrich_rl_dataset.py "
    "--instrument DOGE_USDT --timeframe 15m"
)


# ---------------------------------------------------------------------------
# 1. Orchestrator-level: capped command is reaped, session ends timed_out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capped_command_is_reaped_and_session_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, child_pid_path = _make_hanging_workspace(tmp_path)
    monkeypatch.setattr("src.config.settings.workspace_root", str(workspace))

    store = ResultsStore(str(tmp_path / "p0006.sqlite"))
    await store.initialize()
    config = _make_config("res_p0006_timeout", str(workspace), timeout_s=2)
    await _seed_session(store, config)

    orchestrator = AgentOrchestrator(store)

    with (
        patch.object(orchestrator, "_load_skill_async", new=AsyncMock(return_value="# stub")),
        patch.object(orchestrator, "_load_claude_md_async", new=AsyncMock(return_value="")),
        patch.object(orchestrator, "_refresh_phase_state", new=AsyncMock(return_value=None)),
        patch.object(orchestrator, "_extract_session_insights", new=AsyncMock(return_value=None)),
        patch.object(orchestrator, "_update_research_resume", new=AsyncMock(return_value=None)),
        patch.object(
            orchestrator,
            "_call_claude_with_retry",
            new=AsyncMock(side_effect=lambda *a, **kw: _fake_bash_tool_use(_HANGING_COMMAND)),
        ),
    ):
        start = time.monotonic()
        await orchestrator.run(config)  # type: ignore[arg-type]
        elapsed = time.monotonic() - start

    session = await store.get_session(config.id)
    assert session is not None
    # AC#1 / AC#3: the cap made the hung command self-kill at ~2s, the soft
    # check tripped, and the session ended timed_out well under the 60s sleep.
    assert session["status"] == "timed_out", elapsed
    assert elapsed < 15.0, f"session did not end within budget: {elapsed:.1f}s"

    # AC#2: the grandchild (sleep 60) was reaped by the command's own psutil
    # kill path firing at the capped boundary.
    if child_pid_path.exists():
        child_pid = int(child_pid_path.read_text(encoding="utf-8"))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _process_exists(child_pid):
            time.sleep(0.05)
        assert not _process_exists(child_pid), "grandchild was not reaped"


# ---------------------------------------------------------------------------
# 2. Registry-level: kill_all reaps an in-flight subprocess a cancel can't
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registry_kill_all_reaps_in_flight_subprocess(tmp_path: Path) -> None:
    workspace, child_pid_path = _make_hanging_workspace(tmp_path)
    runner = GovernedCommandRunner(workspace_root=str(workspace))
    registry = CommandProcessRegistry()
    research_id = "res_p0006_killall"

    # Run the hanging command in a worker thread, exactly as the orchestrator
    # does via asyncio.to_thread(_execute_tool, ...).
    loop = asyncio.get_running_loop()
    worker = loop.run_in_executor(
        None,
        lambda: runner.run(
            _HANGING_COMMAND,
            timeout_s=60,
            proc_registry=registry,
            research_id=research_id,
        ),
    )

    # Wait until the command is in-flight: the grandchild pid file exists and
    # the proc is registered.
    spawn_deadline = time.monotonic() + 10
    while time.monotonic() < spawn_deadline and not child_pid_path.exists():
        await asyncio.sleep(0.05)
    assert child_pid_path.exists(), "hanging script never started"
    assert research_id in registry._procs, "proc was not registered"

    # AC#2: kill_all from the event-loop thread reaps the tree (this is what
    # the orchestrator's except-CancelledError handler calls). A bare
    # task.cancel() could not interrupt the worker thread holding the Popen.
    await asyncio.to_thread(registry.kill_all, research_id)

    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
    reap_deadline = time.monotonic() + 8
    while time.monotonic() < reap_deadline and _process_exists(child_pid):
        await asyncio.sleep(0.05)
    assert not _process_exists(child_pid), "grandchild was not reaped by kill_all"

    # The worker thread unblocks (proc killed externally → poll loop exits) and
    # returns normally, i.e. the worker thread is itself reaped.
    await asyncio.wait_for(worker, timeout=10)


# ---------------------------------------------------------------------------
# 3. Unit: cap math + registry mechanics
# ---------------------------------------------------------------------------


class _CapturingRunner:
    """Stand-in for GovernedCommandRunner that records the resolved timeout_s."""

    captures: list[dict[str, object]] = []

    def __init__(self, **_: object) -> None:
        pass

    def run(
        self,
        command: str,
        *,
        timeout_s: int,
        output_callback: object = None,
        proc_registry: object = None,
        research_id: object = None,
    ) -> CommandRunResult:
        type(self).captures.append(
            {
                "timeout_s": timeout_s,
                "proc_registry": proc_registry,
                "research_id": research_id,
            }
        )
        decision = MagicMock()
        decision.allowed = True
        return CommandRunResult(output="ok", decision=decision)


def test_command_timeout_cap_respects_floor_then_budget() -> None:
    """Ample budget → the 900s floor holds; tight budget → the cap wins below it."""
    _CapturingRunner.captures = []
    with patch("src.core.orchestrator.GovernedCommandRunner", _CapturingRunner):
        # Ample remaining budget: agent asked for 30s, floored to 900, not capped.
        _tool_bash(
            {"command": "echo hi", "timeout_s": 30},
            "/ws",
            command_deadline_mono=time.monotonic() + 5000,
        )
        assert _CapturingRunner.captures[-1]["timeout_s"] == 900

        # Tight remaining budget (< floor): the cap wins even though 30 < 900.
        _tool_bash(
            {"command": "echo hi", "timeout_s": 30},
            "/ws",
            command_deadline_mono=time.monotonic() + 5,
        )
        capped = _CapturingRunner.captures[-1]["timeout_s"]
        assert isinstance(capped, int)
        assert 4 <= capped <= 6, capped  # ceil(≈5) → 5 or 6

        # No deadline → unchanged behavior (floor only).
        _tool_bash({"command": "echo hi", "timeout_s": 30}, "/ws")
        assert _CapturingRunner.captures[-1]["timeout_s"] == 900


def test_registry_register_unregister_and_membership() -> None:
    registry = CommandProcessRegistry()
    assert registry.size == 0

    proc_a = MagicMock()
    proc_a.poll.return_value = None  # still running
    proc_b = MagicMock()
    proc_b.poll.return_value = None

    registry.register("s1", proc_a)
    registry.register("s1", proc_b)
    assert registry.size == 1  # one session, two procs

    registry.unregister("s1", proc_a)
    assert registry.size == 1  # proc_b still registered for s1

    registry.unregister("s1", proc_b)
    assert registry.size == 0  # session entry evicted when empty

    # kill_all on an unknown session is a no-op.
    registry.kill_all("unknown")
