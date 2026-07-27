"""Governed subprocess runner for skill-supplied plugins (ARC-011 X-004 / P5-005).

This module implements the **plugin execution contract** recorded in the X-004
security spike (``docs/adr/ARC-011-security-spike.md`` §6). Every skill-supplied
Python file — ``bootstrap.py``, ``parser.py``, ``preflight.py``,
``resolve_identity.py`` — runs in its own confined subprocess via this runner,
never ``import``-ed into the server process (X-004 D2).

Design contract (X-004 §6, verbatim where load-bearing):

* **Invocation:** ``PluginRunner.run(skill_dir, plugin, kind, input_json, *,
  caps, timeout_s) -> PluginResult``.
* **Subprocess:** ``sys.executable <plugin>``, no shell, ``start_new_session=True``
  (process-group for tree-kill). Mirrors ``GovernedCommandRunner``'s spawn shape.
* **ABI:** JSON on stdin, JSON on stdout, exit 0/non-zero. The plugin module
  exposes a pure function; the runner does the marshalling.
* **Capability block (default-deny):** ``caps.fs_write`` / ``network_egress`` /
  ``env`` / ``timeout_s`` / ``max_rss_mb`` / ``max_cpu_s``. Default per-kind
  caps come from ``skill_loader._DEFAULT_CAPS_BY_KIND`` (X-004 §6).
* **Env (X-004 §4.2 — strict):** ``PATH`` / ``LANG`` / ``HOME`` /
  ``PYTHONUNBUFFERED`` / venv ``PYTHONPATH`` + only manifest-declared ``env``
  keys. **No secrets, no ``AWS_*``, no service tokens.** This is strictly
  narrower than ``command_runner._CHILD_ENV_ALLOWLIST`` (the agent path), by
  design — plugins have no legitimate need for any of those.
* **Failure semantics (fail-closed):** crash / timeout / invalid-JSON /
  non-zero-exit ⇒ ``PluginResult(ok=False)`` + audit; **the exception never
  propagates to the server process** (the single-instance W14 guarantee).
* **Path confinement (D4):** the plugin's CWD is the session workspace;
  ``skills/`` is reachable read-only; writes are confined to the workspace when
  ``caps.fs_write == "workspace"``. Reuses ``command_policy._is_within``.

The ``BootstrapRunner`` (P5-005, ``bootstrap_runner.py``) is the first
consumer; ``parser`` / ``preflight`` / ``resolve_identity`` plugins follow the
same contract.

Design decisions (P1-007 house style):

* **Sync subprocess + thread offload.** Like ``GovernedCommandRunner.run``,
  the blocking ``Popen`` poll loop lives on a worker thread; the public
  ``run()`` is ``async`` and wraps the body in ``asyncio.to_thread`` so a hard
  timeout / cancel can reap the tree via ``_terminate_process_group_without_communicate``.
* **No env inheritance.** The plugin child env is built fresh from the X-004
  §4.2 strict allow-list — it does NOT call ``command_runner._build_child_env``
  (that one is the agent path and carries experiment-legitimate creds plugins
  must never see).
* **Resource monitoring.** A psutil watcher thread enforces ``max_rss_mb`` /
  ``max_cpu_s``; on breach the tree is killed and the result is fail-closed.
* **Auditing is the caller's job.** ``PluginRunner`` returns a ``PluginResult``
  with ``error``/``returncode``/``timed_out``; the caller (``BootstrapRunner``
  / orchestrator) writes the ``audit_events`` row. Keeps the runner free of the
  DB handle (X-004 D3 — plugins' execution context gets no server internals).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping, Optional

from src.core.command_policy import _is_within
from src.core.skill_manifest import PluginCaps, PluginKind

try:
    import psutil
except ImportError:  # pragma: no cover - dependency is declared for runtime.
    psutil = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Re-export the kill helper so the bootstrap runner / tests reach it through
# one module without a second import site.
from src.core.command_runner import _terminate_process_group_without_communicate  # noqa: E402

# ---------------------------------------------------------------------------
# X-004 §4.2 — strict plugin env contract
# ---------------------------------------------------------------------------

#: The base allow-list for plugin subprocesses (X-004 §4.2). Strictly narrower
#: than ``command_runner._CHILD_ENV_ALLOWLIST`` (the agent path): plugins get
#: shell/locale/runtime + venv only. No ``AWS_*``, no service tokens, no
#: ``MLFLOW_TRACKING_URI``, no ``DATA_INGEST_URL``. Manifest-declared ``env``
#: keys (``PluginCaps.env``) are merged in on top.
_PLUGIN_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Shell / locale / runtime — the minimum a Python interpreter needs.
        "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE",
        "TERM", "TMPDIR", "TMP",
        # Python / venv.
        "VIRTUAL_ENV", "PKG_CONFIG_PATH",
    }
)

#: Kept by prefix so the Python family (PYTHONUNBUFFERED, PYTHONPATH, ...) and
#: locale family propagate without enumerating every member. ``PYTHONPATH`` is
#: the venv path so the plugin can ``import`` stdlib + installed packages.
_PLUGIN_ENV_PREFIXES: tuple[str, ...] = ("PYTHON", "LC_")

#: Unambiguous server control-plane secrets never needed by a plugin. Subtracted
#: last (defense in depth — X-004 T1) so a name cannot leak even via a
#: manifest-declared ``env`` key.
_FORBIDDEN_PLUGIN_ENV: frozenset[str] = frozenset(
    {
        "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY",
        "AUTORESEARCH_API_TOKEN",
        "AUTORESEARCH_PROMETHEUS_TOKEN", "PROMETHEUS_TOKEN",
        "AUTORESEARCH_MLFLOW_SERVICE_AUTH_TOKEN", "MLFLOW_SERVICE_AUTH_TOKEN",
        "SERVICE_AUTH_TOKEN",
        "AUTORESEARCH_INFERENCE_SERVICE_AUTH_TOKEN",
        "INFERENCE_SERVICE_AUTH_TOKEN",
        "AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER",
        "PRODUCTION_APPROVAL_VERIFIER",
        "AUTORESEARCH_RL_TRAINER_SERVICE_TOKEN", "RL_TRAINER_SERVICE_TOKEN",
        "ML_ADMIN_TOKEN",
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION", "AWS_REGION",
    }
)


def _build_plugin_env(
    *,
    declared_env_keys: Mapping[str, str] | None = None,
    source_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the env dict for a plugin subprocess (X-004 §4.2, strict).

    Default-deny: only ``_PLUGIN_ENV_ALLOWLIST`` or ``_PLUGIN_ENV_PREFIXES``
    survive, then any manifest-declared ``env`` keys are merged in, then
    ``_FORBIDDEN_PLUGIN_ENV`` is subtracted so a declared key cannot smuggle a
    known secret name through.
    """
    source = source_env if source_env is not None else MappingProxyType(os.environ)
    kept = {
        name: value
        for name, value in source.items()
        if name in _PLUGIN_ENV_ALLOWLIST
        or any(name.startswith(prefix) for prefix in _PLUGIN_ENV_PREFIXES)
    }
    if declared_env_keys:
        kept.update(declared_env_keys)
    for forbidden in _FORBIDDEN_PLUGIN_ENV:
        kept.pop(forbidden, None)
    return kept


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PluginResult:
    """Outcome of one plugin invocation (X-004 §6 failure semantics).

    ``ok=True`` ⇒ the plugin exited 0 and emitted valid JSON on stdout; the
    parsed object is in ``output``. ``ok=False`` ⇒ crash / timeout / bad JSON /
    non-zero exit; ``error`` carries the human-readable cause and the caller
    writes a fail-closed ``audit_events`` row. The exception never propagates.
    """

    ok: bool
    kind: PluginKind
    plugin_path: str
    output: Optional[dict[str, Any]] = None
    #: Parsed stdout when ok; combined stdout/stderr tail when failed.
    raw_output: str = ""
    returncode: Optional[int] = None
    timed_out: bool = False
    rss_exceeded: bool = False
    cpu_exceeded: bool = False
    error: Optional[str] = None
    #: Wall-clock duration in seconds (for audit / observability).
    duration_s: float = 0.0
    #: Resolved capability grant the run used (for the bootstrap artifact).
    caps: Optional[PluginCaps] = None
    #: Extra structured fields the caller may attach to the audit row.
    extra: dict[str, Any] = field(default_factory=dict)


class PluginRunner:
    """Execute one skill plugin in a confined governed subprocess (X-004 §6).

    Parameters
    ----------
    skills_root:
        Read-only skills directory (``PluginRunner`` never writes here; D4).
    """

    def __init__(self, *, skills_root: Optional[Path] = None) -> None:
        self._skills_root = Path(skills_root) if skills_root is not None else None

    async def run(
        self,
        *,
        skill_dir: Path,
        plugin: str,
        kind: PluginKind,
        input_json: dict[str, Any],
        caps: PluginCaps,
        workspace: Optional[Path] = None,
        timeout_s: Optional[float] = None,
    ) -> PluginResult:
        """Run one plugin. See module docstring for the contract.

        ``workspace`` is the session workspace (CWD + write target when
        ``caps.fs_write == "workspace"``). ``timeout_s`` overrides
        ``caps.timeout_s`` when supplied (the caller may tighten, never loosen).
        """
        plugin_path = (Path(skill_dir) / plugin).resolve()
        # Path confinement (D4): the plugin must live under its skill dir, and
        # the skill dir must be under the known skills root when one is set.
        if not plugin_path.is_file():
            return PluginResult(
                ok=False, kind=kind, plugin_path=plugin,
                error=f"plugin file not found: {plugin_path}",
            )
        try:
            plugin_path.relative_to(Path(skill_dir).resolve())
        except ValueError:
            return PluginResult(
                ok=False, kind=kind, plugin_path=plugin,
                error=f"plugin path escapes skill dir: {plugin_path}",
            )
        if self._skills_root is not None:
            try:
                Path(skill_dir).resolve().relative_to(self._skills_root.resolve())
            except ValueError:
                return PluginResult(
                    ok=False, kind=kind, plugin_path=plugin,
                    error=f"skill dir escapes skills root: {skill_dir}",
                )

        effective_timeout = (
            min(timeout_s, caps.timeout_s) if timeout_s is not None else caps.timeout_s
        )
        cwd = str(workspace) if workspace is not None else str(Path(skill_dir))

        body = _PluginRunBody(
            plugin_path=plugin_path,
            kind=kind,
            plugin=plugin,
            input_json=input_json,
            caps=caps,
            cwd=cwd,
            timeout_s=effective_timeout,
        )
        return await asyncio.to_thread(self._run_sync, body)

    # ── sync body (worker thread) ──────────────────────────────────────────
    def _run_sync(self, body: "_PluginRunBody") -> PluginResult:
        started = time.monotonic()
        payload = json.dumps(body.input_json).encode("utf-8")
        child_env = _build_plugin_env()
        try:
            proc = subprocess.Popen(
                [sys.executable, str(body.plugin_path)],
                cwd=body.cwd,
                env=child_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                start_new_session=True,
            )
        except OSError as exc:
            return PluginResult(
                ok=False, kind=body.kind, plugin_path=body.plugin,
                error=f"failed to spawn plugin: {exc}",
                duration_s=time.monotonic() - started,
                caps=body.caps,
            )

        watcher = _ResourceWatcher(proc.pid, body.caps) if psutil is not None else None
        if watcher is not None:
            watcher.start()
        try:
            try:
                stdout_bytes, stderr_bytes = proc.communicate(
                    input=payload, timeout=body.timeout_s
                )
            except subprocess.TimeoutExpired:
                _terminate_process_group_without_communicate(proc)
                return PluginResult(
                    ok=False, kind=body.kind, plugin_path=body.plugin,
                    returncode=proc.returncode, timed_out=True,
                    error=f"plugin timed out after {body.timeout_s}s",
                    duration_s=time.monotonic() - started,
                    caps=body.caps,
                )
            rss_exceeded = watcher.rss_exceeded if watcher else False
            cpu_exceeded = watcher.cpu_exceeded if watcher else False
            if rss_exceeded or cpu_exceeded:
                _terminate_process_group_without_communicate(proc)
                limit = "RSS" if rss_exceeded else "CPU"
                return PluginResult(
                    ok=False, kind=body.kind, plugin_path=body.plugin,
                    returncode=proc.returncode,
                    rss_exceeded=rss_exceeded, cpu_exceeded=cpu_exceeded,
                    error=f"plugin exceeded {limit} cap "
                          f"({body.caps.max_rss_mb}MB / {body.caps.max_cpu_s}s)",
                    duration_s=time.monotonic() - started,
                    caps=body.caps,
                )
            stdout_text = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr_text = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            if proc.returncode != 0:
                tail = _tail((stdout_text + "\n" + stderr_text).strip())
                return PluginResult(
                    ok=False, kind=body.kind, plugin_path=body.plugin,
                    returncode=proc.returncode,
                    raw_output=tail,
                    error=f"plugin exited non-zero (code={proc.returncode})",
                    duration_s=time.monotonic() - started,
                    caps=body.caps,
                )
            try:
                parsed = json.loads(stdout_text) if stdout_text.strip() else None
            except json.JSONDecodeError as exc:
                tail = _tail(stdout_text.strip())
                return PluginResult(
                    ok=False, kind=body.kind, plugin_path=body.plugin,
                    returncode=proc.returncode, raw_output=tail,
                    error=f"plugin emitted invalid JSON: {exc}",
                    duration_s=time.monotonic() - started,
                    caps=body.caps,
                )
            if not isinstance(parsed, dict):
                return PluginResult(
                    ok=False, kind=body.kind, plugin_path=body.plugin,
                    returncode=proc.returncode, raw_output=_tail(stdout_text.strip()),
                    error="plugin stdout was not a JSON object",
                    duration_s=time.monotonic() - started,
                    caps=body.caps,
                )
            return PluginResult(
                ok=True, kind=body.kind, plugin_path=body.plugin,
                output=parsed, raw_output=stdout_text,
                returncode=proc.returncode,
                duration_s=time.monotonic() - started,
                caps=body.caps,
            )
        finally:
            if watcher is not None:
                watcher.stop()


@dataclass
class _PluginRunBody:
    """Inputs bundled for the worker-thread sync body."""

    plugin_path: Path
    kind: PluginKind
    plugin: str
    input_json: dict[str, Any]
    caps: PluginCaps
    cwd: str
    timeout_s: float


def _tail(text: str, *, max_chars: int = 2000) -> str:
    """Return the trailing slice of ``text`` for error context."""
    if len(text) <= max_chars:
        return text
    return "…" + text[-max_chars:]


# ---------------------------------------------------------------------------
# Resource watcher (D6 — RSS / CPU caps)
# ---------------------------------------------------------------------------


class _ResourceWatcher:
    """Polls a live plugin subprocess's RSS / CPU and flags cap breaches (D6).

    The runner checks ``rss_exceeded`` / ``cpu_exceeded`` after ``communicate``
    returns; if a cap was breached the tree is killed and the result fails
    closed. Sampling cadence (0.1s) balances responsiveness against overhead —
    plugins are short-lived (bootstrap/preflight once per session; parser once
    per iteration).
    """

    _POLL_INTERVAL_S = 0.1

    def __init__(self, pid: int, caps: PluginCaps) -> None:
        self._pid = pid
        self._caps = caps
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.rss_exceeded = False
        self.cpu_exceeded = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _loop(self) -> None:
        try:
            proc = psutil.Process(self._pid)  # type: ignore[union-attr]
        except (psutil.NoSuchProcess, Exception):  # type: ignore[union-attr]
            return
        last_cpu = None
        while not self._stop.is_set():
            try:
                children = proc.children(recursive=True) + [proc]
                total_rss = 0
                total_cpu = 0.0
                for child in children:
                    try:
                        mem = child.memory_info()
                        total_rss += mem.rss
                        cpu = child.cpu_times()
                        total_cpu += (cpu.user or 0.0) + (cpu.system or 0.0)
                    except (psutil.NoSuchProcess, Exception):  # type: ignore[union-attr]
                        pass
                if total_rss > self._caps.max_rss_mb * 1024 * 1024:
                    self.rss_exceeded = True
                    return
                if last_cpu is not None and total_cpu - last_cpu > self._caps.max_cpu_s:
                    # CPU delta over one interval exceeding the whole cap ⇒ runaway.
                    self.cpu_exceeded = True
                    return
                last_cpu = total_cpu
            except (psutil.NoSuchProcess, Exception):  # type: ignore[union-attr]
                return
            self._stop.wait(self._POLL_INTERVAL_S)


__all__ = [
    "PluginResult",
    "PluginRunner",
    "_build_plugin_env",
]
