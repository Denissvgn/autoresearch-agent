from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from server.core.command_policy import evaluate_command_policy
from server.core.command_runner import GovernedCommandRunner, redact_sensitive_text

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

from server.core.orchestrator import _execute_tool


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
        ".venv/bin/python scripts/autotuner/direction/prepare.py --config /etc/passwd",
        ".venv/bin/python scripts/autotuner/direction/prepare.py --config train.yaml 2>&1",
        ".venv/bin/python scripts/autotuner/setup.py --instrument $(cat /run/secrets/token)",
        "cat /etc/passwd",
        "cp train.yaml /tmp/best_train.yaml",
        ".venv/bin/python -c 'print(123)'",
        "cat results.json | head",
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
