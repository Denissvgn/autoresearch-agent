from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import types
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from src.core.command_policy import evaluate_command_policy
from src.core.command_runner import (
    _CHILD_ENV_ALLOWLIST,
    GovernedCommandRunner,
    redact_sensitive_text,
)

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

from src.core.orchestrator import _execute_tool
from src.core.tool_access import build_tool_access_context


def _workspace(tmp_path: Path) -> tuple[str, str]:
    workspace = tmp_path / "workspace"
    session = workspace / "runs" / "autotuner" / "DOGE_USDT_15m" / "direction"
    session.mkdir(parents=True)
    return str(workspace), str(session)


def _pin_script(tmp_path: Path, script_name: str, content: str) -> dict:
    """Create a digest-pinned packaged script outside the workspace.

    ``tmp_path/pkg`` stands in for the installed ``skills/<id>/`` tree: the
    policy resolves declared entrypoints here (digest-verified before launch)
    and never at a same-named agent-writable workspace copy.
    """
    pkg = tmp_path / "pkg"
    script_path = pkg / script_name
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {
        "allowed_scripts": {script_name},
        "script_paths": {script_name: str(script_path)},
        "script_digests": {script_name: digest},
    }


def test_base_policy_is_default_deny_for_scripts(tmp_path: Path):
    workspace, session = _workspace(tmp_path)

    decision = evaluate_command_policy(
        ".venv/bin/python scripts/autotuner/setup.py --instrument X",
        workspace_root=workspace,
        session_workspace=session,
    )
    assert not decision.allowed


def test_command_policy_allows_skill_declared_operations(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    python_path = Path(workspace) / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    pin = _pin_script(
        tmp_path, "scripts/autotuner/setup.py", "print('setup')\n"
    )

    extension = {
        **pin,
        "copyable_files": {"train.yaml", "best_train.yaml"},
        "readable_files": {"results.json"},
    }
    allowed = [
        (
            ".venv/bin/python scripts/autotuner/setup.py "
            "--instrument DOGE_USDT --timeframe 15m --models direction"
        ),
        "cat runs/autotuner/DOGE_USDT_15m/direction/results.json",
    ]

    for command in allowed:
        decision = evaluate_command_policy(
            command,
            workspace_root=workspace,
            session_workspace=session,
            policy_extension=extension,
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
    access = build_tool_access_context(workspace, workspace_root=workspace)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = Path(workspace) / "linked.txt"
    link.symlink_to(outside)

    read_result = _execute_tool("read_file", {"path": "linked.txt"}, access)
    write_result = _execute_tool(
        "write_file",
        {"path": "linked.txt", "content": "replacement"},
        access,
    )
    glob_result = _execute_tool("glob", {"pattern": "*.txt"}, access)

    assert "resolves outside" in read_result.content
    assert "symlink" in write_result.content
    assert "linked.txt" not in glob_result.content


def test_governed_runner_executes_without_shell_and_redacts_output(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    python_path = Path(workspace) / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    extension = _pin_script(
        tmp_path,
        "scripts/autotuner/enrich_rl_dataset.py",
        "print('API_KEY=super-secret')\nprint('ready')\n",
    )

    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
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


def test_governed_runner_streams_redacted_output_chunks(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    python_path = Path(workspace) / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    streamed: list[tuple[str, str]] = []
    extension = _pin_script(
        tmp_path,
        "scripts/autotuner/enrich_rl_dataset.py",
        "import sys\n"
        "print('TOKEN=top-secret', flush=True)\n"
        "print('progress 1', flush=True)\n"
        "print('warn password=bad', file=sys.stderr, flush=True)\n",
    )
    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )
    result = runner.run(
        ".venv/bin/python scripts/autotuner/enrich_rl_dataset.py "
        "--instrument DOGE_USDT --timeframe 15m",
        timeout_s=900,
        output_callback=lambda stream, chunk: streamed.append((stream, chunk)),
    )

    assert result.returncode == 0
    assert "top-secret" not in result.output
    assert "top-secret" not in "".join(chunk for _, chunk in streamed)
    assert any(stream == "stdout" and "TOKEN=<redacted>" in chunk for stream, chunk in streamed)
    assert any(stream == "stderr" and "password=<redacted>" in chunk for stream, chunk in streamed)


def test_governed_runner_timeout_cleans_process_group(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    python_path = Path(workspace) / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    child_pid_path = Path(workspace) / "child.pid"
    extension = _pin_script(
        tmp_path,
        "scripts/autotuner/enrich_rl_dataset.py",
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
    )

    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
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
    access = build_tool_access_context(session, workspace_root=workspace)

    result = _execute_tool(
        "bash",
        {"command": "wget https://example.com/model.sh"},
        access,
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


def test_governed_runner_strips_control_plane_secrets_from_child_env(
    tmp_path: Path, monkeypatch
):
    """ARC-011 P0-023 DoD: server control-plane secrets must not reach the child."""
    # Plant server-only canaries in the parent env the child would otherwise inherit.
    canaries = {
        "ANTHROPIC_AUTH_TOKEN": "leak-anthropic",
        "AUTORESEARCH_API_TOKEN": "leak-api",
        "AUTORESEARCH_MLFLOW_SERVICE_AUTH_TOKEN": "leak-promo",
        "AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER": "leak-hmac",
    }
    for name, value in canaries.items():
        monkeypatch.setenv(name, value)
    # A legacy platform admin token — must now be stripped like the others.
    monkeypatch.setenv("ML_ADMIN_TOKEN", "legacy-admin")
    # A core runtime var that must also be kept.
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    workspace, session = _workspace(tmp_path)
    python_path = Path(workspace) / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    env_dump_path = Path(workspace) / "child_env.json"
    extension = _pin_script(
        tmp_path,
        "scripts/autotuner/enrich_rl_dataset.py",
        "import json, os, pathlib\n"
        f"pathlib.Path({str(env_dump_path)!r}).write_text("
        "json.dumps(dict(os.environ)))\n",
    )

    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )
    result = runner.run(
        ".venv/bin/python scripts/autotuner/enrich_rl_dataset.py "
        "--instrument DOGE_USDT --timeframe 15m",
        timeout_s=60,
    )

    assert result.returncode == 0, result.output
    child_env = json.loads(env_dump_path.read_text(encoding="utf-8"))

    # Stripped: every planted server control-plane canary is absent from the child.
    for name, value in canaries.items():
        assert name not in child_env, f"{name} leaked into governed child env"
        assert value not in child_env.values(), (
            f"{name}'s value leaked via another env var"
        )
    # Stripped: legacy platform admin tokens do not propagate either.
    assert "ML_ADMIN_TOKEN" not in child_env
    # Kept: core runtime vars propagate.
    assert child_env.get("PATH") == "/usr/bin:/bin"


def test_build_child_env_allowlist_covers_approved_script_inventory():
    """Static contract: the allow-list ⊇ every var the six _ALLOWED_SCRIPTS read.

    X-002 parity is pure-function and does not exercise live env, so this guard
    catches the realistic regression vector: a future edit dropping an
    experiment-legitimate var. Consumers (file:line) per ARC-011 P0-023 inventory.
    """
    required = {
        # Skill bootstrap/setup scripts read the workspace roots.
        "HOST_CONFIGS_PATH",
        # Artifact-store clients (boto3-based skill scripts).
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
        "S3_ENDPOINT_URL", "MLFLOW_S3_ENDPOINT_URL",
        # MLflow tracking (generic, no service tokens).
        "MLFLOW_TRACKING_URI",
    }
    missing = required - _CHILD_ENV_ALLOWLIST
    assert not missing, (
        f"_CHILD_ENV_ALLOWLIST dropped a var an approved script reads: {sorted(missing)}"
    )


# ── ARC-011 P4-002: nonce delivery via extra_env (W11 anti-forgery) ─────────


def _nonce_dump_script(tmp_path: Path, workspace: Path) -> tuple[dict, Path]:
    """Create a digest-pinned packaged script that dumps
    AUTORESEARCH_SESSION_NONCE to a file, plus the .venv/bin/python symlink
    the policy expects.

    The script lives in the pinned package tree, never in the
    agent-writable workspace. Mirrors the env-dump pattern in
    ``test_governed_runner_strips_*`` but asserts the nonce reaches the child
    via the ``extra_env`` channel.
    """
    python_path = workspace / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    dump_path = workspace / "nonce_seen.txt"
    extension = _pin_script(
        tmp_path,
        "scripts/autotuner/enrich_rl_dataset.py",
        "import os, pathlib\n"
        f"pathlib.Path({str(dump_path)!r}).write_text("
        "os.environ.get('AUTORESEARCH_SESSION_NONCE', ''))\n",
    )
    return extension, dump_path


def test_governed_runner_extra_env_delivers_nonce(tmp_path: Path):
    """P4-002: ``GovernedCommandRunner.run(extra_env=...)`` injects the nonce
    into the child subprocess env (merged AFTER the forbidden-secret
    subtraction so it can't be stripped). This is the W11 anti-forgery delivery
    channel — without it the eval script always echoes an empty nonce.
    """
    workspace, session = _workspace(tmp_path)
    extension, dump_path = _nonce_dump_script(tmp_path, Path(workspace))

    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )
    nonce = "deadbeef" * 8
    result = runner.run(
        ".venv/bin/python scripts/autotuner/enrich_rl_dataset.py "
        "--instrument DOGE_USDT --timeframe 15m",
        timeout_s=60,
        extra_env={"AUTORESEARCH_SESSION_NONCE": nonce},
    )

    assert result.returncode == 0, result.output
    assert dump_path.read_text(encoding="utf-8") == nonce, (
        "AUTORESEARCH_SESSION_NONCE did not reach the subprocess via extra_env"
    )


def test_governed_runner_without_extra_env_has_no_nonce(tmp_path: Path, monkeypatch):
    """Companion: without ``extra_env`` the nonce is absent — confirming the
    channel is opt-in (the runner never injects the nonce on its own)."""
    # Ensure the var is not inherited from the parent env accidentally.
    monkeypatch.delenv("AUTORESEARCH_SESSION_NONCE", raising=False)
    workspace, session = _workspace(tmp_path)
    extension, dump_path = _nonce_dump_script(tmp_path, Path(workspace))

    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )
    result = runner.run(
        ".venv/bin/python scripts/autotuner/enrich_rl_dataset.py "
        "--instrument DOGE_USDT --timeframe 15m",
        timeout_s=60,
    )
    assert result.returncode == 0, result.output
    assert dump_path.read_text(encoding="utf-8") == "", (
        "nonce leaked into the child without extra_env being passed"
    )


def test_execute_tool_threads_extra_env_to_bash(tmp_path: Path):
    """P4-002 wiring: ``_execute_tool("bash", ..., extra_env=...)`` forwards the
    nonce through ``_tool_bash`` to ``GovernedCommandRunner.run``. This is the
    full delivery chain the orchestrator relies on (the call site at
    orchestrator.py passes ``extra_env=nonce_extra_env``)."""
    workspace, session = _workspace(tmp_path)
    extension, dump_path = _nonce_dump_script(tmp_path, Path(workspace))
    access = build_tool_access_context(session, workspace_root=workspace)

    nonce = "cafebabe" * 8
    result = _execute_tool(
        "bash",
        {"command": ".venv/bin/python scripts/autotuner/enrich_rl_dataset.py "
                    "--instrument DOGE_USDT --timeframe 15m"},
        access,
        extra_env={"AUTORESEARCH_SESSION_NONCE": nonce},
        policy_extension=extension,
    )
    assert result.meta["returncode"] == 0, result.content
    assert dump_path.read_text(encoding="utf-8") == nonce, (
        "_execute_tool did not forward extra_env to the subprocess"
    )
