"""Governed subprocess runner for skill-supplied plugins (ARC-011 X-004 / P5-005).

This module implements the **plugin execution contract** recorded in the X-004
security spike (§6; design recorded in this module's docstring). Every skill-supplied
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
  ``caps.fs_write == "workspace"``. Path confinement uses ``relative_to``
  checks against the declared roots.

The ``BootstrapRunner`` (P5-005, ``bootstrap_runner.py``) is the first
consumer; ``parser`` / ``preflight`` / ``resolve_identity`` plugins follow the
same contract.

Design decisions (P1-007 house style):

* **Sync subprocess + thread offload.** Like ``GovernedCommandRunner.run``,
  the blocking drain lives on a worker thread; the public ``run()`` is
  ``async`` and wraps the body in ``asyncio.to_thread`` so stop/cancel can
  reap the tree through the process registry and the bounded cleanup path.
* **No env inheritance.** The plugin child env is built fresh from the X-004
  §4.2 strict allow-list — it does NOT call ``command_runner._build_child_env``
  (that one is the agent path and carries experiment-legitimate creds plugins
  must never see).
* **Resource bounds.** ``src.core.process_limits`` enforces cumulative CPU,
  process-tree RSS, wall time, process count, and the configured output and
  filesystem quotas over the whole tree; breaches terminate immediately and
  the result is an attributed fail-closed record with explicit cleanup status.
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
from dataclasses import replace as _dataclass_replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping, Optional

from src.core.skill_manifest import PluginCaps, PluginKind

logger = logging.getLogger(__name__)

from src.core.isolation import (  # noqa: E402
    SANDBOXED_PREFIX,
    TRUSTED_LOCAL_CODE,
    IsolationPolicy,
    IsolationUnavailableError,
    UnsupportedCapabilityError,
    wrap_command,
)
from src.core.process_limits import (  # noqa: E402
    ProcessResourceCaps,
    TreeResourceGuard,
    UnenforceableResourceCapabilityError,
    bounded_drain,
    rlimit_prefix,
    signal_violation,
)

# ---------------------------------------------------------------------------
# X-004 §4.2 — strict plugin env contract
# ---------------------------------------------------------------------------

#: The base allow-list for plugin subprocesses (X-004 §4.2). Strictly narrower
#: than ``command_runner._CHILD_ENV_ALLOWLIST`` (the agent path): plugins get
#: shell/locale/runtime + venv only. No ``AWS_*``, no service tokens, no
#: ``MLFLOW_TRACKING_URI`` and no service URLs. Manifest-declared ``env``
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
        "AUTORESEARCH_MLFLOW_SERVICE_AUTH_TOKEN", "MLFLOW_SERVICE_AUTH_TOKEN",  # domain-coupling: denylist
        "SERVICE_AUTH_TOKEN",
        "AUTORESEARCH_INFERENCE_SERVICE_AUTH_TOKEN",
        "INFERENCE_SERVICE_AUTH_TOKEN",
        "AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER",
        "PRODUCTION_APPROVAL_VERIFIER",
        "AUTORESEARCH_RL_TRAINER_SERVICE_TOKEN", "RL_TRAINER_SERVICE_TOKEN",  # domain-coupling: denylist
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


def _declared_input_paths(input_json: Mapping[str, Any]) -> tuple[str, ...]:
    """Absolute path values in the input JSON that name existing host files.

    These are the run's declared input artifacts (e.g. the eval_set a
    bootstrap consumes). The isolation boundary mounts each read-only so a
    sandboxed plugin can read its inputs wherever the server staged them,
    without exposing any sibling files.
    """
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            if node.startswith("/") and os.path.isfile(node):
                found.append(node)
        elif isinstance(node, Mapping):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(input_json)
    return tuple(dict.fromkeys(found))


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
    #: Process-tree size cap breached (configured process-count quota).
    processes_exceeded: bool = False
    #: Output quota breached: the tree was terminated past the configured
    #: stdout+stderr byte bound (capture itself stays bounded).
    output_exceeded: bool = False
    #: Per-file write quota breached at the kernel (RLIMIT_FSIZE / SIGXFSZ).
    fsize_exceeded: bool = False
    #: Attributed violation kind ("cpu", "rss", "processes", "output",
    #: "file_size", "wall_time") or None for a clean run.
    violation: Optional[str] = None
    #: Explicit cleanup status: True when a descendant survived the bounded
    #: termination window (successful cleanup always reports False).
    cleanup_incomplete: bool = False
    error: Optional[str] = None
    #: Wall-clock duration in seconds (for audit / observability).
    duration_s: float = 0.0
    #: Resolved capability grant the run used (for the bootstrap artifact).
    caps: Optional[PluginCaps] = None
    #: Execution boundary label — ``"sandboxed:bwrap"`` only when the run was
    #: actually wrapped by the isolation backend; ``"trusted_local_code"`` for
    #: the operator's local-code policy, which is never advertised as sandboxed.
    isolation: str = ""
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
        proc_registry: Any = None,
        research_id: Optional[str] = None,
    ) -> PluginResult:
        """Run one plugin. See module docstring for the contract.

        ``workspace`` is the session workspace (CWD + write target when
        ``caps.fs_write == "workspace"``). ``timeout_s`` overrides
        ``caps.timeout_s`` when supplied (the caller may tighten, never loosen).
        ``proc_registry`` registers the live spawn so a session stop/cancel can
        reap the whole plugin tree through the bounded cleanup path.
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
        base_argv = [sys.executable, str(plugin_path)]

        isolation_label, spawn_argv, refusal = self._isolation_plan(
            skill_dir=Path(skill_dir),
            caps=caps,
            cwd=cwd,
            base_argv=base_argv,
            input_json=input_json,
        )
        if refusal is not None:
            # Fail-closed: never fall back to unsandboxed execution silently.
            return PluginResult(
                ok=False, kind=kind, plugin_path=plugin,
                error=refusal, caps=caps, isolation=isolation_label,
            )

        from src.config import get_settings

        _settings = get_settings()
        resource_caps = ProcessResourceCaps(
            wall_s=effective_timeout,
            cpu_s=caps.max_cpu_s,
            rss_mb=caps.max_rss_mb,
            max_processes=_settings.execution_max_processes,
            max_output_bytes=_settings.execution_max_output_bytes,
            max_file_write_bytes=_settings.execution_max_file_write_bytes,
        )
        body = _PluginRunBody(
            plugin_path=plugin_path,
            kind=kind,
            plugin=plugin,
            input_json=input_json,
            caps=caps,
            cwd=cwd,
            timeout_s=effective_timeout,
            spawn_argv=spawn_argv,
            isolation=isolation_label,
            resource_caps=resource_caps,
            proc_registry=proc_registry,
            research_id=research_id,
        )
        return await asyncio.to_thread(self._run_sync, body)

    def _isolation_plan(
        self, *, skill_dir: Path, caps: PluginCaps, cwd: str, base_argv: list[str],
        input_json: dict[str, Any],
    ) -> tuple[str, list[str], Optional[str]]:
        """Decide the execution boundary for one plugin run.

        Returns ``(label, spawn_argv, refusal)``. In enforced mode (the
        operator default) the plugin runs sandboxed with its declared caps
        enforced at the OS boundary; an unenforceable capability request or
        unavailable isolation returns a refusal instead of falling back to
        unsandboxed execution. The operator's ``trusted_local_code`` policy is
        separately labeled and never advertised as sandboxed.
        """
        from src.config import get_settings

        mode = get_settings().execution_isolation_mode
        if mode == "trusted_local_code":
            logger.warning(
                "plugin %s runs under the trusted local-code operator policy: "
                "capability grants are NOT enforced at the OS boundary",
                skill_dir,
            )
            return TRUSTED_LOCAL_CODE, list(base_argv), None

        workspace_roots = tuple(
            str(p) for p in (Path(cwd),) if p.is_dir()
        )
        # Read roots: the plugin's own skill package (its source and any
        # skill-internal helpers it imports), the pinned interpreter, the
        # session workspace, and every declared input artifact (absolute path
        # values in the input JSON — e.g. the eval_set file) mounted read-only.
        # Control-plane code (src/, server state), sibling runs (outside the
        # session workspace), the signing authority env, and host sockets are
        # not mounted / not passed (env allow-list + network default-deny).
        # The skill's own eval/ helpers stay readable — some bootstrap plugins
        # import them legitimately; ``masked_roots`` remains available for
        # operators that want to hide a package subtree.
        policy = IsolationPolicy(
            fs_write=caps.fs_write,
            network_egress=tuple(caps.network_egress),
            read_roots=(
                (str(skill_dir), sys.prefix, sys.base_prefix)
                + workspace_roots
                + _declared_input_paths(input_json)
            ),
            write_roots=workspace_roots if caps.fs_write == "workspace" else (),
            cwd=cwd,
        )
        try:
            spawn_argv = wrap_command(base_argv, policy=policy)
        except UnsupportedCapabilityError as exc:
            return (
                "refused",
                list(base_argv),
                f"unsupported capability request: {exc}",
            )
        except IsolationUnavailableError as exc:
            return (
                "refused",
                list(base_argv),
                f"isolation unavailable; refusing to run plugin unsandboxed: {exc}",
            )
        return SANDBOXED_PREFIX + "bwrap", spawn_argv, None

    # ── sync body (worker thread) ──────────────────────────────────────────
    def _run_sync(self, body: "_PluginRunBody") -> PluginResult:
        # Stamp the execution-boundary label on every exit path (the inner
        # body builds results at many fail-closed points).
        return _dataclass_replace(self._run_sync_inner(body), isolation=body.isolation)

    def _run_sync_inner(self, body: "_PluginRunBody") -> PluginResult:
        started = time.monotonic()
        payload = json.dumps(body.input_json).encode("utf-8")
        child_env = _build_plugin_env()
        try:
            rlimits = rlimit_prefix(body.resource_caps)
        except UnenforceableResourceCapabilityError as exc:
            return PluginResult(
                ok=False, kind=body.kind, plugin_path=body.plugin,
                error=f"unenforceable resource capability: {exc}",
                duration_s=time.monotonic() - started,
                caps=body.caps,
            )
        try:
            proc = subprocess.Popen(
                [*rlimits, *body.spawn_argv],
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

        if body.proc_registry is not None and body.research_id is not None:
            body.proc_registry.register(body.research_id, proc)
        guard = TreeResourceGuard(proc, body.resource_caps)
        guard.start()
        try:
            outcome = bounded_drain(
                proc, input_bytes=payload,
                caps=body.resource_caps, guard=guard,
            )
        finally:
            guard.stop()
            if body.proc_registry is not None and body.research_id is not None:
                body.proc_registry.unregister(body.research_id, proc)

        violation = outcome.violation or signal_violation(proc.returncode)
        cleanup_incomplete = outcome.cleanup_incomplete or guard.cleanup_incomplete
        stdout_text = outcome.stdout.decode("utf-8", errors="replace") if outcome.stdout else ""
        stderr_text = outcome.stderr.decode("utf-8", errors="replace") if outcome.stderr else ""
        if violation is not None:
            return _violation_result(
                body, proc=proc, started=started,
                violation=violation, timed_out=outcome.timed_out,
                cleanup_incomplete=cleanup_incomplete,
                raw=_tail((stdout_text + "\n" + stderr_text).strip()),
            )
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
    #: The full spawn argv — already wrapped in the isolation boundary when
    #: the run is sandboxed; plain ``[sys.executable, plugin]`` otherwise.
    spawn_argv: list[str]
    #: The boundary label for the run (see :attr:`PluginResult.isolation`).
    isolation: str
    #: Finite resource caps enforced over the whole process tree.
    resource_caps: ProcessResourceCaps
    #: Optional process registry so stop/cancel can reap the plugin tree.
    proc_registry: Any = None
    research_id: Optional[str] = None


def _tail(text: str, *, max_chars: int = 2000) -> str:
    """Return the trailing slice of ``text`` for error context."""
    if len(text) <= max_chars:
        return text
    return "…" + text[-max_chars:]


_VIOLATION_LABELS = {
    "wall_time": "wall-clock timeout",
    "cpu": "CPU cap",
    "rss": "RSS cap",
    "processes": "process-count cap",
    "output": "output quota",
    "file_size": "per-file write quota",
}


def _violation_result(
    body: "_PluginRunBody", *, proc: Any, started: float, violation: str,
    timed_out: bool, cleanup_incomplete: bool, raw: str,
) -> PluginResult:
    """Build the attributed failed result for one resource-cap breach."""
    caps = body.resource_caps
    detail = {
        "cpu": f"{caps.cpu_s}s",
        "rss": f"{caps.rss_mb}MB",
        "processes": str(caps.max_processes),
        "output": f"{caps.max_output_bytes} bytes",
        "file_size": f"{caps.max_file_write_bytes} bytes",
        "wall_time": f"{body.timeout_s}s",
    }.get(violation, "")
    label = _VIOLATION_LABELS.get(violation, violation)
    error = f"plugin exceeded {label} ({detail})" if detail else f"plugin exceeded {label}"
    if violation == "wall_time":
        error = f"plugin timed out after {body.timeout_s}s"
    if cleanup_incomplete:
        error += "; cleanup incomplete (descendants survived the termination bound)"
    return PluginResult(
        ok=False, kind=body.kind, plugin_path=body.plugin,
        returncode=proc.returncode, timed_out=timed_out,
        rss_exceeded=(violation == "rss"),
        cpu_exceeded=(violation == "cpu"),
        processes_exceeded=(violation == "processes"),
        output_exceeded=(violation == "output"),
        fsize_exceeded=(violation == "file_size"),
        violation=violation,
        cleanup_incomplete=cleanup_incomplete,
        raw_output=raw,
        error=error,
        duration_s=time.monotonic() - started,
        caps=body.caps,
    )




__all__ = [
    "PluginResult",
    "PluginRunner",
    "_build_plugin_env",
]
