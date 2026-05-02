from __future__ import annotations

import os
import sys
import time
import types
from pathlib import Path

import pytest

from src.core.command_policy import evaluate_command_policy
from src.core.command_runner import GovernedCommandRunner, redact_sensitive_text

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    class _FakeAsyncAnthropic:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class _FakeAPIStatusError(Exception):
        status_code = 500

    sys.modules["anthropic"] = types.SimpleNamespace(
        AsyncAnthropic=_FakeAsyncAnthropic,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=_FakeAPIStatusError,
    )

from src.core.orchestrator import _execute_tool


def _workspace(tmp_path: Path) -> tuple[str, str]:
    workspace = tmp_path / "workspace"
    session = workspace / "runs" / "autotuner" / "DOGE_USDT_15m" / "direction"
    session.mkdir(parents=True)
    return str(workspace), str(session)


def test_command_policy_allows_known_training_operations(tmp_path: Path):
    workspace, session = _workspace(tmp_path)

    allowed = [
        (
            ".venv/bin/python scripts/autotuner/setup.py "
            "--instrument DOGE_USDT --timeframe 15m --models direction"
        ),
        (
            f"cd {workspace} && .venv/bin/python "
            "scripts/autotuner/direction/prepare.py "
            " --config runs/autotuner/DOGE_USDT_15m/direction/train.yaml --quick"
        ),
        (
            "cp runs/autotuner/DOGE_USDT_15m/direction/train.yaml "
            "runs/autotuner/DOGE_USDT_15m/direction/best_train.yaml"
        ),
        "cat runs/autotuner/DOGE_USDT_15m/direction/results.json",
    ]

    for command in allowed:
        decision = evaluate_command_policy(
            command,
            workspace_root=workspace,
            session_workspace=session,
        )
        assert decision.allowed, command
        assert decision.argv[0] != "bash"


@pytest.mark.parametrize(
    "command",
    [
        "curl https://example.com",
        ".venv/bin/python -m pip install pandas",
        "git status",
        "docker ps",
        (
            ".venv/bin/python scripts/autotuner/promote.py "
            "--config runs/autotuner/DOGE_USDT_15m/direction/best_train.yaml"
        ),
        ".venv/bin/python scripts/autotuner/direction/prepare.py --config /etc/passwd",
        ".venv/bin/python scripts/autotuner/direction/prepare.py --config train.yaml 2>&1",
        ".venv/bin/python scripts/autotuner/setup.py --instrument $(cat /run/secrets/token)",
        "cat /etc/passwd",
        "cp train.yaml /tmp/best_train.yaml",
        ".venv/bin/python -c 'print(123)'",
        "cat results.json | head",
        "ln -s train.yaml linked.yaml",
    ],
)
def test_command_policy_blocks_unsafe_commands(tmp_path: Path, command: str):
    workspace, session = _workspace(tmp_path)

    decision = evaluate_command_policy(
        command,
        workspace_root=workspace,
        session_workspace=session,
    )

    assert not decision.allowed
    assert decision.reason


def test_command_policy_rejects_symlink_escape_for_cat(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    outside = tmp_path / "outside" / "results.json"
    outside.parent.mkdir()
    outside.write_text("secret", encoding="utf-8")
    link = Path(session) / "results.json"
    link.symlink_to(outside)

    decision = evaluate_command_policy(
        "cat results.json",
        workspace_root=workspace,
        session_workspace=session,
    )

    assert not decision.allowed
    assert "session workspace" in decision.reason


def test_file_tools_reject_and_filter_symlink_escapes(tmp_path: Path):
    workspace, _ = _workspace(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = Path(workspace) / "linked.txt"
    link.symlink_to(outside)

    read_result = _execute_tool("read_file", {"path": "linked.txt"}, workspace)
    write_result = _execute_tool(
        "write_file",
        {"path": "linked.txt", "content": "replacement"},
        workspace,
    )
    glob_result = _execute_tool("glob", {"pattern": "*.txt"}, workspace)

    assert "resolves outside workspace" in read_result.content
    assert "symlink" in write_result.content
    assert "linked.txt" not in glob_result.content


def test_governed_runner_executes_without_shell_and_redacts_output(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    python_path = Path(workspace) / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    script = Path(workspace) / "scripts" / "autotuner" / "enrich_rl_dataset.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "print('API_KEY=super-secret')\nprint('ready')\n",
        encoding="utf-8",
    )

    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session,
    )
    result = runner.run(
        ".venv/bin/python scripts/autotuner/enrich_rl_dataset.py "
        "--instrument DOGE_USDT --timeframe 15m",
        timeout_s=900,
    )

    assert not result.rejected
    assert result.returncode == 0
    assert "API_KEY=<redacted>" in result.output
    assert "super-secret" not in result.output
    assert "ready" in result.output


def test_governed_runner_timeout_cleans_process_group(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    python_path = Path(workspace) / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    child_pid_path = Path(workspace) / "child.pid"
    script = Path(workspace) / "scripts" / "autotuner" / "enrich_rl_dataset.py"
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

    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session,
    )
    result = runner.run(
        ".venv/bin/python scripts/autotuner/enrich_rl_dataset.py "
        "--instrument DOGE_USDT --timeframe 15m",
        timeout_s=1,
    )

    assert result.timed_out is True
    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _process_exists(child_pid):
        time.sleep(0.05)
    assert not _process_exists(child_pid)


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.exists():
        try:
            return proc_stat.read_text(encoding="utf-8").split()[2] != "Z"
        except OSError:
            return True
    return True


def test_execute_tool_returns_policy_rejection_metadata(tmp_path: Path):
    workspace, session = _workspace(tmp_path)

    result = _execute_tool(
        "bash",
        {"command": "wget https://example.com/model.sh"},
        workspace,
        session,
    )

    assert "Command rejected by policy" in result.content
    assert result.meta["policy_allowed"] is False
    assert "wget" in result.meta["policy_reason"]


def test_redaction_handles_bearer_and_env_like_values():
    text = "Authorization: Bearer abc.def TOKEN=my-token password = p4ss"

    redacted = redact_sensitive_text(text)

    assert "abc.def" not in redacted
    assert "my-token" not in redacted
    assert "p4ss" not in redacted
