"""Execution isolation acceptance tests.

Real filesystem/network denial probes, child-process containment, capability
refusal, host-prerequisite failure behavior, and trusted/untrusted mode
contract tests. The probes are gated on the host actually providing the
isolation prerequisites (bubblewrap + user namespaces); the contract tests
are host-independent.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.core.isolation import (
    SANDBOXED_PREFIX,
    TRUSTED_LOCAL_CODE,
    BwrapBackend,
    IsolationPolicy,
    IsolationUnavailableError,
    UnsupportedCapabilityError,
    probe_host,
    wrap_command,
)
from src.core.plugin_runner import PluginCaps, PluginRunner

_HOST_READY = bool(probe_host().get("ready"))
requires_backend = pytest.mark.skipif(
    not _HOST_READY, reason="isolation backend prerequisites unavailable on host"
)


def _run_sandboxed(policy: IsolationPolicy, script: str) -> str:
    from dataclasses import replace as _dc_replace

    policy = _dc_replace(
        policy,
        read_roots=tuple(dict.fromkeys(policy.read_roots + (sys.prefix, sys.base_prefix))),
    )
    cmd = wrap_command([sys.executable, "-c", script], policy=policy)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return proc.stdout.strip()


def _probe_script(*attempts: str) -> str:
    """A python probe that runs each attempt and reports success/failure."""
    body = "\n".join(
        f"try:\n    {a}\n    print('OK')\nexcept Exception:\n    print('DENIED')"
        for a in attempts
    )
    return body


@requires_backend
def test_fs_write_none_denied_at_os_boundary(tmp_path: Path) -> None:
    """``fs_write: none`` prevents writes at the OS boundary."""
    ws = tmp_path / "ws"
    ws.mkdir()
    policy = IsolationPolicy(
        fs_write="none", read_roots=(str(ws),), write_roots=(str(ws),), cwd=str(ws)
    )
    out = _run_sandboxed(policy, _probe_script("open('escape.txt', 'w').write('x')"))
    assert out == "DENIED"
    assert not (ws / "escape.txt").exists()
    assert not (tmp_path / "escape.txt").exists()


@requires_backend
def test_fs_write_workspace_confined(tmp_path: Path) -> None:
    """``fs_write: workspace`` permits workspace writes and nothing else."""
    ws = tmp_path / "ws"
    ws.mkdir()
    policy = IsolationPolicy(
        fs_write="workspace", read_roots=(str(tmp_path),), write_roots=(str(ws),), cwd=str(ws)
    )
    out = _run_sandboxed(
        policy,
        _probe_script(
            "open('inside.txt', 'w').write('x')",
            "open('../outside.txt', 'w').write('x')",
        ),
    )
    assert out.splitlines() == ["OK", "DENIED"]
    assert (ws / "inside.txt").exists()
    assert not (tmp_path / "outside.txt").exists()


@requires_backend
def test_network_default_deny() -> None:
    """Disallowed network destinations are unreachable (default-deny)."""
    policy = IsolationPolicy(fs_write="none")
    out = _run_sandboxed(
        policy,
        _probe_script(
            "import socket; socket.create_connection(('1.1.1.1', 80), timeout=2)"
        ),
    )
    assert out == "DENIED"


@requires_backend
def test_child_process_attempts_cannot_escape(tmp_path: Path) -> None:
    """Candidate-controlled subprocesses cannot escape the same policy."""
    ws = tmp_path / "ws"
    ws.mkdir()
    policy = IsolationPolicy(
        fs_write="none", read_roots=(str(ws),), write_roots=(str(ws),), cwd=str(ws)
    )
    script = (
        "import subprocess, sys; "
        "r = subprocess.run([sys.executable, '-c', \"import socket; "
        "socket.create_connection(('1.1.1.1', 80), timeout=2)\"], "
        "capture_output=True); "
        "print('CHILD_NET_DENIED' if r.returncode != 0 else 'CHILD_NET_OK'); "
        "r2 = subprocess.run([sys.executable, '-c', \"open('child_escape.txt', 'w').write('x')\"], "
        "capture_output=True); "
        "print('CHILD_FS_DENIED' if r2.returncode != 0 else 'CHILD_FS_OK')"
    )
    out = _run_sandboxed(policy, script)
    assert out.splitlines() == ["CHILD_NET_DENIED", "CHILD_FS_DENIED"]
    assert not (ws / "child_escape.txt").exists()


def test_network_allowlist_capability_refused() -> None:
    """Unsupported capability requests are refused, never silently widened."""
    policy = IsolationPolicy(fs_write="none", network_egress=("example.com:443",))
    with pytest.raises(UnsupportedCapabilityError):
        wrap_command([sys.executable, "-c", "pass"], policy=policy)


@requires_backend
def test_masked_evaluator_code_unreadable(tmp_path: Path) -> None:
    """Plugins are isolated from evaluator code via masked mounts."""
    ws = tmp_path / "ws"
    eval_root = tmp_path / "skill" / "eval"
    eval_root.mkdir(parents=True)
    (eval_root / "run.py").write_text("SECRET_EVALUATOR = 1\n")
    ws.mkdir()
    policy = IsolationPolicy(
        fs_write="none",
        read_roots=(str(tmp_path / "skill"), str(ws)),
        masked_roots=(str(eval_root),),
        cwd=str(ws),
    )
    out = _run_sandboxed(
        policy,
        _probe_script("open('" + str(eval_root / "run.py") + "').read()"),
    )
    assert out == "DENIED"


def _write_probe_plugin(skill_dir: Path, *, attempt: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "probe.py").write_text(
        "import json\n"
        "try:\n"
        f"    {attempt}\n"
        "    print(json.dumps({'escape': 'ok'}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'escape': 'denied', 'err': str(exc)}))\n"
    )


@requires_backend
def test_plugin_runner_enforced_mode_sandboxed(tmp_path: Path) -> None:
    """Untrusted plugin runs are sandboxed: caps enforced at the OS boundary."""
    import asyncio

    skill_dir = tmp_path / "skill"
    ws = tmp_path / "ws"
    ws.mkdir()
    # Escape target inside the skill dir: read-only at the OS boundary.
    _write_probe_plugin(
        skill_dir, attempt="open('" + str(skill_dir / "plugin_escape.txt") + "', 'w').write('x')"
    )
    result = asyncio.run(PluginRunner().run(
        skill_dir=skill_dir, plugin="probe.py", kind="parser",
        input_json={}, caps=PluginCaps(fs_write="none"), workspace=ws,
    ))
    assert result.ok, result.error
    assert result.isolation == SANDBOXED_PREFIX + "bwrap"
    assert result.output is not None
    assert result.output["escape"] == "denied"
    assert not (skill_dir / "plugin_escape.txt").exists()


@requires_backend
def test_plugin_runner_refuses_allowlist_request(tmp_path: Path) -> None:
    """A plugin requesting network egress is refused and never executes."""
    import asyncio

    skill_dir = tmp_path / "skill"
    ws = tmp_path / "ws"
    ws.mkdir()
    _write_probe_plugin(
        skill_dir, attempt="open('" + str(skill_dir / "refusal_marker.txt") + "', 'w').write('x')"
    )
    result = asyncio.run(PluginRunner().run(
        skill_dir=skill_dir, plugin="probe.py", kind="parser",
        input_json={}, caps=PluginCaps(fs_write="none", network_egress=["example.com:443"]),
        workspace=ws,
    ))
    assert not result.ok
    assert "unsupported capability request" in (result.error or "")
    assert not (skill_dir / "refusal_marker.txt").exists()


def test_plugin_runner_host_prereq_failure_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unavailable isolation refuses execution instead of falling back."""
    import asyncio


    skill_dir = tmp_path / "skill"
    ws = tmp_path / "ws"
    ws.mkdir()
    _write_probe_plugin(
        skill_dir, attempt="open('" + str(skill_dir / "fallback_marker.txt") + "', 'w').write('x')"
    )

    def _no_backend(*_a, **_k):
        raise IsolationUnavailableError("bwrap binary not found")

    monkeypatch.setattr("src.core.plugin_runner.wrap_command", _no_backend)
    result = asyncio.run(PluginRunner().run(
        skill_dir=skill_dir, plugin="probe.py", kind="parser",
        input_json={}, caps=PluginCaps(fs_write="none"), workspace=ws,
    ))
    assert not result.ok
    assert "isolation unavailable" in (result.error or "")
    assert not (skill_dir / "fallback_marker.txt").exists()


def test_trusted_local_code_mode_labeled_not_sandboxed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The trusted local-code policy is separately labeled, never sandboxed."""
    import asyncio

    from src.config import get_settings

    monkeypatch.setenv("AUTORESEARCH_EXECUTION_ISOLATION_MODE", "trusted_local_code")
    get_settings.cache_clear()
    try:
        skill_dir = tmp_path / "skill"
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_probe_plugin(
            skill_dir,
            attempt="open('" + str(skill_dir / "trusted_write.txt") + "', 'w').write('x')",
        )
        result = asyncio.run(PluginRunner().run(
            skill_dir=skill_dir, plugin="probe.py", kind="parser",
            input_json={}, caps=PluginCaps(fs_write="none"), workspace=ws,
        ))
        assert result.ok, result.error
        assert result.isolation == TRUSTED_LOCAL_CODE
        assert "sandboxed" not in result.isolation
        # Documented, operator-chosen behavior: caps are NOT enforced here.
        assert (skill_dir / "trusted_write.txt").exists()
        assert result.output == {"escape": "ok"}
    finally:
        get_settings.cache_clear()


# --- command runner: the retained trusted path and its sandboxed variant ---

EVAL_CONTENT = (
    "import pathlib, sys\n"
    "config_path = sys.argv[sys.argv.index('--config') + 1]\n"
    "text = pathlib.Path(config_path).read_text(encoding='utf-8')\n"
    "pathlib.Path('seen.txt').write_text(text, encoding='utf-8')\n"
)


def _cmd_fixture(tmp_path: Path):
    """Workspace/session + a pinned evaluator, mirroring the resolver tests."""
    import hashlib

    workspace = tmp_path / "workspace"
    session = workspace / "runs" / "autotuner" / "DOGE_USDT_15m" / "direction"
    session.mkdir(parents=True)
    python_path = workspace / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    pkg = tmp_path / "pkg"
    script = pkg / "eval" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text(EVAL_CONTENT, encoding="utf-8")
    extension = {
        "allowed_scripts": {"eval/run.py"},
        "script_paths": {"eval/run.py": str(script)},
        "script_digests": {
            "eval/run.py": hashlib.sha256(EVAL_CONTENT.encode("utf-8")).hexdigest()
        },
        "config_flag": "--config",
        "copyable_files": ["db_config.yaml"],
    }
    (session / "db_config.yaml").write_text("max_conn: 7\n", encoding="utf-8")
    return str(workspace), str(session), extension, pkg


def test_command_runner_trusted_boundary_labeled(tmp_path: Path) -> None:
    """Without an isolation policy the command path is labeled local-code."""
    from src.core.command_runner import GovernedCommandRunner

    workspace, session, extension, _pkg = _cmd_fixture(tmp_path)
    runner = GovernedCommandRunner(
        workspace_root=workspace, session_workspace=session, policy_extension=extension
    )
    result = runner.run(".venv/bin/python eval/run.py --config db_config.yaml", timeout_s=60)
    assert result.returncode == 0, result.output
    assert result.execution_boundary == TRUSTED_LOCAL_CODE
    # Retained trusted path executes as today — but is never 'sandboxed'.
    assert "sandboxed" not in result.execution_boundary
    assert (Path(session) / "seen.txt").exists()


@requires_backend
def test_command_runner_sandboxed_enforces_policy(tmp_path: Path) -> None:
    """With an isolation policy the same boundary confines governed commands."""
    from src.core.command_runner import GovernedCommandRunner

    workspace, session, extension, pkg = _cmd_fixture(tmp_path)
    policy = IsolationPolicy(
        fs_write="none",
        read_roots=(str(tmp_path), sys.prefix, sys.base_prefix),
        write_roots=(session,),
    )
    runner = GovernedCommandRunner(
        workspace_root=workspace, session_workspace=session, policy_extension=extension
    )
    result = runner.run(
        ".venv/bin/python eval/run.py --config db_config.yaml",
        timeout_s=60, isolation_policy=policy,
    )
    assert result.returncode not in (0, None), result.output
    assert result.execution_boundary == SANDBOXED_PREFIX + "bwrap"
    assert not (Path(session) / "seen.txt").exists()


def test_command_runner_refuses_unenforceable_policy(tmp_path: Path) -> None:
    """An unenforceable capability refuses the execution (no silent fallback)."""
    from src.core.command_runner import GovernedCommandRunner

    workspace, session, extension, _pkg = _cmd_fixture(tmp_path)
    policy = IsolationPolicy(fs_write="none", network_egress=("example.com:443",))
    runner = GovernedCommandRunner(
        workspace_root=workspace, session_workspace=session, policy_extension=extension
    )
    result = runner.run(
        ".venv/bin/python eval/run.py --config db_config.yaml",
        timeout_s=60, isolation_policy=policy,
    )
    assert result.execution_boundary == "refused"
    assert "refused" in result.output.lower()
    assert not (Path(session) / "seen.txt").exists()
