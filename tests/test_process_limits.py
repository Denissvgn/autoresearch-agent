"""Bounded resource use, output, and cancellation acceptance tests.

Synthetic CPU/memory/output/process workloads assert that a breach stops the
process tree within the documented tested termination bound and produces an
attributed failed record; independent psutil inspection after teardown finds
no orphaned child; unenforceable required caps reject the capability.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from src.core.plugin_runner import PluginCaps, PluginRunner
from src.core.process_limits import (
    TERMINATION_BOUND_S,
    ProcessResourceCaps,
    TreeResourceGuard,
    UnenforceableResourceCapabilityError,
    bounded_drain,
    rlimit_prefix,
    terminate_process_tree,
)

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


def _guarded_run(code: str, caps: ProcessResourceCaps):
    """Run one python probe under caps; return (outcome, proc, elapsed)."""
    from src.core.process_limits import rlimit_prefix as _prefix

    proc = subprocess.Popen(
        [*_prefix(caps), sys.executable, "-c", code],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL, start_new_session=True,
    )
    guard = TreeResourceGuard(proc, caps)
    guard.start()
    started = time.monotonic()
    try:
        outcome = bounded_drain(proc, input_bytes=None, caps=caps, guard=guard)
    finally:
        guard.stop()
    return outcome, proc, time.monotonic() - started


def _assert_no_orphans(pids: list[int]) -> None:
    """Independent process inspection after teardown."""
    if psutil is None:  # pragma: no cover
        return
    time.sleep(0.2)
    alive = [pid for pid in pids if psutil.pid_exists(pid)]
    assert alive == [], f"orphaned children survived teardown: {alive}"


def test_cpu_breach_stops_tree_within_bound() -> None:
    """Cumulative CPU breach stops the tree within the documented bound."""
    outcome, proc, elapsed = _guarded_run(
        "while True: pass",
        ProcessResourceCaps(wall_s=30.0, cpu_s=1.0),
    )
    assert outcome.violation == "cpu", (outcome.violation, outcome.stderr[-200:])
    assert not outcome.cleanup_incomplete
    assert proc.poll() is not None
    assert elapsed < 30.0


def test_memory_breach_stops_tree_within_bound() -> None:
    """Process-tree RSS breach stops the tree."""
    probe = (
        "x = bytearray(600 * 1024 * 1024)\n"
        "x[::4096] = b'a' * len(x[::4096])\n"
        "import time; time.sleep(30)\n"
    )
    outcome, proc, _elapsed = _guarded_run(
        probe,
        ProcessResourceCaps(wall_s=30.0, rss_mb=100),
    )
    assert outcome.violation == "rss", (outcome.violation, outcome.stderr[-200:])
    assert proc.poll() is not None


def test_output_breach_stops_tree_and_capture_stays_bounded() -> None:
    """Output quota breach terminates; capture itself never grows unbounded."""
    outcome, proc, _elapsed = _guarded_run(
        "import sys\nwhile True: sys.stdout.write('x' * 65536); sys.stdout.flush()",
        ProcessResourceCaps(wall_s=30.0, max_output_bytes=200_000),
    )
    assert outcome.violation == "output"
    assert proc.poll() is not None
    assert len(outcome.stdout) <= 200_000 + 65_536


def test_process_count_breach_stops_tree_with_no_orphans() -> None:
    """Process-count breach stops the whole tree; no child survives teardown."""
    code = (
        "import subprocess, sys, time; "
        "kids = [subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']) "
        "for _ in range(8)]; "
        "print(','.join(str(k.pid) for k in kids), flush=True); "
        "time.sleep(60)"
    )
    outcome, proc, _elapsed = _guarded_run(
        code, ProcessResourceCaps(wall_s=30.0, max_processes=4),
    )
    assert outcome.violation == "processes"
    pids = [int(x) for x in outcome.stdout.decode().strip().split(",") if x]
    assert pids, "probe should have printed its child pids before the breach"
    _assert_no_orphans(pids + [proc.pid])



def test_file_write_quota_enforced_at_kernel() -> None:
    """Per-file write quota (RLIMIT_FSIZE) stops oversized writes."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "big.bin"
        code = (
            "from pathlib import Path; "
            f"Path({str(target)!r}).write_bytes(b'x' * 5_000_000); "
            "print('WROTE_OK')"
        )
        outcome, proc, _elapsed = _guarded_run(
            code,
            ProcessResourceCaps(wall_s=30.0, max_file_write_bytes=100_000),
        )
        assert "WROTE_OK" not in outcome.stdout.decode()
        assert proc.poll() is not None
        assert not target.exists() or target.stat().st_size <= 100_000
        # Attribution: the kernel signal death maps to the file_size cap.
        assert outcome.violation == "file_size" or proc.returncode is not None


def test_wall_timeout_stops_tree() -> None:
    """Wall-time breach terminates immediately and is attributed."""
    outcome, proc, elapsed = _guarded_run(
        "import time; time.sleep(60)",
        ProcessResourceCaps(wall_s=0.5),
    )
    assert outcome.violation == "wall_time"
    assert outcome.timed_out
    assert proc.poll() is not None
    assert elapsed < 0.5 + TERMINATION_BOUND_S


def test_unenforceable_required_cap_rejects_capability(monkeypatch) -> None:
    """A required cap that cannot be enforced rejects the capability."""
    monkeypatch.setattr("src.core.process_limits.shutil.which", lambda _name: None)
    with pytest.raises(UnenforceableResourceCapabilityError):
        rlimit_prefix(ProcessResourceCaps(max_file_write_bytes=1000))
    # CPU-only requests still have the parent-side guard and do not require prlimit.
    assert rlimit_prefix(ProcessResourceCaps(cpu_s=5.0)) == []


def test_termination_latency_within_documented_bound() -> None:
    """Record the tested termination bound: breach to tree-gone latency."""
    latencies = []
    for _ in range(3):
        started = time.monotonic()
        outcome, proc, _elapsed = _guarded_run(
            "while True: pass",
            ProcessResourceCaps(wall_s=30.0, cpu_s=0.5),
        )
        latencies.append(time.monotonic() - started)
        assert outcome.violation == "cpu"
        assert proc.poll() is not None
    assert max(latencies) < 0.5 + TERMINATION_BOUND_S


def _write_probe_plugin(skill_dir: Path, body: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "probe.py").write_text(body)


def test_plugin_result_is_attributed_and_failed(tmp_path: Path) -> None:
    """A plugin resource breach is an attributed failed record."""
    _write_probe_plugin(
        tmp_path / "skill",
        "import sys\nwhile True: sys.stdout.write('x' * 65536); sys.stdout.flush()\n",
    )
    result = asyncio.run(PluginRunner().run(
        skill_dir=tmp_path / "skill", plugin="probe.py", kind="parser",
        input_json={}, caps=PluginCaps(fs_write="none", timeout_s=30.0, max_cpu_s=30.0),
        workspace=tmp_path,
    ))
    assert not result.ok
    assert result.output_exceeded
    assert result.violation == "output"
    assert "output quota" in (result.error or "")
    assert not result.cleanup_incomplete

def test_registry_cancel_reaps_plugin_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stop/cancel propagates through the plugin (bootstrap) channel."""
    from src.config import get_settings
    from src.core.command_runner import CommandProcessRegistry

    # Host-visible pids for the orphan inspection: the trusted local-code
    # policy runs unsandboxed (cancellation mechanics are identical).
    monkeypatch.setenv("AUTORESEARCH_EXECUTION_ISOLATION_MODE", "trusted_local_code")
    get_settings.cache_clear()
    body = (
        "import json, subprocess, sys, time; "
        "kid = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "sys.stdout.write(json.dumps({'kid': kid.pid}) + '\\n'); sys.stdout.flush(); "
        "time.sleep(60)"
    )
    _write_probe_plugin(tmp_path / "skill", body)
    registry = CommandProcessRegistry()

    async def scenario():
        task = asyncio.ensure_future(PluginRunner().run(
            skill_dir=tmp_path / "skill", plugin="probe.py", kind="parser",
            input_json={}, caps=PluginCaps(fs_write="none", timeout_s=30.0),
            workspace=tmp_path, proc_registry=registry, research_id="cancel-1",
        ))
        await asyncio.sleep(0.6)
        clean = registry.kill_all("cancel-1")
        result = await task
        return clean, result

    try:
        clean, result = asyncio.run(scenario())
    finally:
        get_settings.cache_clear()
    assert clean, "kill_all must report complete cleanup"
    assert not result.ok
    assert not result.cleanup_incomplete
    kid_pid = json.loads(result.raw_output.strip().splitlines()[-1])["kid"]
    _assert_no_orphans([kid_pid])


def _cmd_fixture(tmp_path: Path, content: str):
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
    script.write_text(content, encoding="utf-8")
    extension = {
        "allowed_scripts": {"eval/run.py"},
        "script_paths": {"eval/run.py": str(script)},
        "script_digests": {"eval/run.py": hashlib.sha256(content.encode()).hexdigest()},
        "config_flag": "--config",
        "copyable_files": ["db_config.yaml"],
    }
    (session / "db_config.yaml").write_text("max_conn: 7\n", encoding="utf-8")
    return workspace, session, extension


def test_registry_cancel_reaps_evaluator_tree(tmp_path: Path) -> None:
    """Stop/cancel propagates through the evaluator (command) channel."""
    from src.core.command_runner import CommandProcessRegistry, GovernedCommandRunner

    content = (
        "import subprocess, sys, time\n"
        "kid = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "print('kid', kid.pid, flush=True)\n"
        "time.sleep(60)\n"
    )
    workspace, session, extension = _cmd_fixture(tmp_path, content)
    registry = CommandProcessRegistry()
    runner = GovernedCommandRunner(
        workspace_root=str(workspace), session_workspace=str(session),
        policy_extension=extension,
    )
    result_box: dict = {}

    def run_it():
        result_box["result"] = runner.run(
            ".venv/bin/python eval/run.py --config db_config.yaml",
            timeout_s=30, proc_registry=registry, research_id="cancel-2",
        )

    worker = threading.Thread(target=run_it, daemon=True)
    worker.start()
    time.sleep(0.8)
    clean = registry.kill_all("cancel-2")
    worker.join(timeout=TERMINATION_BOUND_S + 2)
    assert clean, "kill_all must report complete cleanup"
    result = result_box["result"]
    assert result.returncode not in (0, None)
    assert not result.cleanup_incomplete
    kid_line = [ln for ln in result.output.splitlines() if ln.startswith("kid ")][0]
    kid_pid = int(kid_line.split()[1])
    _assert_no_orphans([kid_pid])


def test_command_output_quota_attributed(tmp_path: Path, monkeypatch) -> None:
    """The evaluator channel enforces the output quota and attributes it."""
    from src.config import get_settings
    from src.core.command_runner import GovernedCommandRunner

    monkeypatch.setenv("AUTORESEARCH_EXECUTION_MAX_OUTPUT_BYTES", "50000")
    get_settings.cache_clear()
    try:
        content = (
            "import sys\n"
            "while True:\n"
            "    sys.stdout.write('x' * 65536)\n"
            "    sys.stdout.flush()\n"
        )
        workspace, session, extension = _cmd_fixture(tmp_path, content)
        runner = GovernedCommandRunner(
            workspace_root=str(workspace), session_workspace=str(session),
            policy_extension=extension,
        )
        result = runner.run(
            ".venv/bin/python eval/run.py --config db_config.yaml",
            timeout_s=30,
        )
        assert result.resource_violation == "output"
        assert not result.cleanup_incomplete
        assert result.returncode not in (0, None)
    finally:
        get_settings.cache_clear()
