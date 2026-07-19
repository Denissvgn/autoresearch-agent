"""Tests for the sync tool-dispatch path (ARC-011 P1-029 / P1-030).

History note: P1-029 originally proposed migrating ``grep`` from a synchronous
``subprocess.run`` (run inside ``asyncio.to_thread``) to
``asyncio.create_subprocess_exec``, and making ``_execute_tool`` itself
``async``. That migration was **reverted** in favor of the existing
``asyncio.to_thread`` wrapping (orchestrator.py:648) — keeping every tool call
site uniform. These tests pin the **current** sync contract:

* the dispatch shape (``_execute_tool`` / ``_tool_grep`` are sync functions;
  ``_tool_glob`` is sync pure-Python);
* the grep happy-path output + the 60k-char truncation + the no-match marker;
* the ``subprocess.run(timeout=30)`` path returns the timeout marker on
  timeout (the standard-library reaper handles child cleanup; there is no
  in-process reap to test);
* the P1-029 security delta: the grep child runs with ``_build_child_env()``,
  so server control-plane secrets are stripped (same P0-023 invariant, applied
  to the previously-ungoverned grep path).

The behavioral gate for the bash tool path stays in ``test_command_policy.py``;
this file covers the grep / glob tools specifically.
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from src.core.orchestrator import _execute_tool, _tool_glob, _tool_grep

# ── helpers ────────────────────────────────────────────────────────────────


def _workspace(tmp_path: Path) -> str:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return str(ws)


# ── dispatch shape ─────────────────────────────────────────────────────────


def test_execute_tool_is_sync_function():
    """``_execute_tool`` is a plain synchronous function. The agent loop wraps
    it in ``asyncio.to_thread`` so blocking work runs on a worker thread; the
    P1-029 proposal to make it ``async`` was reverted (see orchestrator.py:648).
    """
    assert not inspect.iscoroutinefunction(_execute_tool), (
        "_execute_tool is sync by design; P1-029's async migration was reverted"
    )


def test_tool_grep_is_sync_function():
    """``_tool_grep`` is a plain synchronous function (uses ``subprocess.run``
    with timeout=30; the asyncio.subprocess migration was reverted)."""
    assert not inspect.iscoroutinefunction(_tool_grep)


def test_tool_glob_is_sync_function():
    """``_tool_glob`` is synchronous (pure-Python, non-blocking)."""
    assert not inspect.iscoroutinefunction(_tool_glob), (
        "_tool_glob is pure-Python glob; it should NOT be async"
    )


# ── happy path ─────────────────────────────────────────────────────────────


def test_grep_returns_matches(tmp_path: Path):
    """``grep`` finds the pattern across files and returns matching lines."""
    workspace = _workspace(tmp_path)
    (Path(workspace) / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    (Path(workspace) / "b.txt").write_text("alpha\ngamma\n", encoding="utf-8")

    result = _tool_grep({"pattern": "alpha"}, workspace)

    # grep reports the search-path prefix (absolute safe_dir) + filename.
    assert "a.txt" in result and "alpha" in result
    assert "b.txt" in result
    assert "beta" not in result
    assert "gamma" not in result


def test_grep_no_matches_returns_marker(tmp_path: Path):
    """No matches → the ``"(no matches)"`` sentinel."""
    workspace = _workspace(tmp_path)
    (Path(workspace) / "a.txt").write_text("alpha\n", encoding="utf-8")

    result = _tool_grep({"pattern": "zzz_not_present"}, workspace)

    assert result == "(no matches)"


def test_grep_truncates_large_output(tmp_path: Path):
    """Output > 60k chars is truncated to the 30k-head + 30k-tail shape."""
    workspace = _workspace(tmp_path)
    # 10k lines × ~10 chars = ~100k chars of grep output (file:line prefix + match).
    big = "matchme\n" * 10_000
    (Path(workspace) / "big.txt").write_text(big, encoding="utf-8")

    result = _tool_grep({"pattern": "matchme"}, workspace)

    assert "...(truncated)..." in result
    assert len(result) <= 60_000 + len("...(truncated)...\n") + 10


def test_grep_include_filter(tmp_path: Path):
    """The ``--include`` glob narrows the search."""
    workspace = _workspace(tmp_path)
    (Path(workspace) / "keep.py").write_text("target\n", encoding="utf-8")
    (Path(workspace) / "skip.txt").write_text("target\n", encoding="utf-8")

    result = _tool_grep(
        {"pattern": "target", "include": "*.py"}, workspace,
    )

    assert "keep.py" in result
    assert "skip.txt" not in result


# ── dispatch through _execute_tool ─────────────────────────────────────────


def test_execute_tool_dispatches_grep(tmp_path: Path):
    """``_execute_tool("grep", ...)`` routes through ``_tool_grep`` and returns
    a ``ToolExecutionResult``."""
    workspace = _workspace(tmp_path)
    (Path(workspace) / "a.txt").write_text("hello\n", encoding="utf-8")

    result = _execute_tool("grep", {"pattern": "hello"}, workspace)

    assert "a.txt" in result.content
    assert "hello" in result.content


def test_execute_tool_dispatches_glob(tmp_path: Path):
    """``glob`` routes through ``_tool_glob`` via ``_execute_tool``."""
    workspace = _workspace(tmp_path)
    (Path(workspace) / "find.txt").write_text("x", encoding="utf-8")

    result = _execute_tool("glob", {"pattern": "*.txt"}, workspace)

    assert "find.txt" in result.content


# ── timeout path ───────────────────────────────────────────────────────────


def test_grep_timeout_returns_marker(tmp_path: Path, monkeypatch):
    """A grep that exceeds the 30s wall-clock timeout returns the timeout
    marker. ``subprocess.run(timeout=30)`` raises ``TimeoutExpired`` after
    killing the child (the standard-library reaper handles process-tree
    cleanup internally); ``_tool_grep`` catches the exception and returns the
    marker string.

    The production timeout is 30s; this test monkeypatches ``subprocess.run``
    so it raises ``TimeoutExpired`` immediately, so the test runs in
    milliseconds instead of 30s.
    """
    workspace = _workspace(tmp_path)

    import src.core.orchestrator as orch_mod

    def _fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=30)

    monkeypatch.setattr(orch_mod.subprocess, "run", _fake_run)

    result = _tool_grep({"pattern": "anything"}, workspace)

    assert result == "Grep timed out after 30s"


# ── security: env scrubbing (P1-029 delta, P0-023 invariant) ───────────────


def test_grep_does_not_inherit_control_plane_secrets(
    tmp_path: Path, monkeypatch,
):
    """P1-029 security delta: the grep child runs with ``_build_child_env()``
    passed as ``env=``, so server control-plane secrets (the P0-023 forbidden
    set) are stripped.

    Mirrors ``test_governed_runner_strips_control_plane_secrets_from_child_env``
    in ``test_command_policy.py`` but for the grep path, which previously
    inherited the full parent env via bare ``subprocess.run``.

    Verified two ways:
      (1) ``_build_child_env()`` — the function ``_tool_grep`` now passes as
          ``env=`` — strips every canary (pure-function check, deterministic).
      (2) ``_tool_grep`` actually invokes ``subprocess.run`` with that env= —
          captured by intercepting ``subprocess.run`` and asserting the
          forbidden canaries are absent from the env dict it received.
    """
    canaries = {
        "ANTHROPIC_AUTH_TOKEN": "leak-anthropic",
        "AUTORESEARCH_API_TOKEN": "leak-api",
        "AUTORESEARCH_PROMETHEUS_TOKEN": "leak-prometheus",
    }
    for name, value in canaries.items():
        monkeypatch.setenv(name, value)

    workspace = _workspace(tmp_path)
    (Path(workspace) / "a.txt").write_text("alpha\n", encoding="utf-8")

    # (1) Pure-function check: _build_child_env() strips every canary.
    from src.core.command_runner import _build_child_env

    child_env = _build_child_env()
    for name in canaries:
        assert name not in child_env, (
            f"{name} would leak into the grep child env (P1-029 regression)"
        )

    # (2) Behavioral check: _tool_grep actually passes the scrubbed env to
    # subprocess.run. Intercept subprocess.run, capture the env= kwarg, and
    # short-circuit the call (return an empty CompletedProcess).
    import src.core.orchestrator as orch_mod

    captured_env: dict[str, str] = {}

    def _capturing_run(cmd, **kwargs):
        captured_env.update(kwargs.get("env") or {})
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(orch_mod.subprocess, "run", _capturing_run)

    _tool_grep({"pattern": "alpha"}, workspace)

    assert captured_env, "_tool_grep did not invoke subprocess.run"
    for name in canaries:
        assert name not in captured_env, (
            f"_tool_grep passed {name} through to subprocess.run "
            f"(the env= scrubbing did not apply)"
        )


def test_grep_child_env_still_has_path(tmp_path: Path, monkeypatch):
    """Companion to the secret-leak test: the scrubbed env must still carry
    ``PATH`` so the ``grep`` binary is locatable. A regression that strips
    ``PATH`` would make every grep call fail with FileNotFoundError."""
    workspace = _workspace(tmp_path)
    (Path(workspace) / "a.txt").write_text("alpha\n", encoding="utf-8")

    import src.core.orchestrator as orch_mod

    captured_env: dict[str, str] = {}

    def _capturing_run(cmd, **kwargs):
        captured_env.update(kwargs.get("env") or {})
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(orch_mod.subprocess, "run", _capturing_run)

    _tool_grep({"pattern": "alpha"}, workspace)

    assert "PATH" in captured_env, (
        "PATH missing from grep child env — subprocess would fail to find grep"
    )
