"""Governed subprocess runner for autoresearch agent commands."""

from __future__ import annotations

import codecs
import fcntl
import os
import re
import selectors
import signal
import stat
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Literal, Mapping

from src.core.command_policy import CommandDecision, evaluate_command_policy
from src.core.tool_access import ToolAccessContext

try:
    import psutil
except ImportError:  # pragma: no cover - dependency is declared for runtime.
    psutil = None  # type: ignore[assignment]


_MAX_OUTPUT_LEN = 60_000
_OUTPUT_CHUNK_SIZE = 8_192
_SESSION_LOG_QUOTA_BYTES = 64 * 1024 * 1024
_TRUNCATION_MARKER = "\n...(truncated)...\n"


class _HeadTailBuffer:
    """Retain a fixed-size head and rolling tail, including for newline-free data.

    >>> buf = _HeadTailBuffer(8)
    >>> buf.append("abc")
    >>> buf.append("defgh")
    >>> buf.getvalue()
    'abcdefgh'
    >>> buf.append("ijklmnop")
    >>> buf.getvalue() == "abcd" + _TRUNCATION_MARKER + "mnop"
    True
    >>> len(buf.head) + len(buf.tail) <= 8
    True
    """

    def __init__(self, limit: int = _MAX_OUTPUT_LEN) -> None:
        self.limit = max(0, limit)
        self.head = ""
        self.tail = ""
        self.total = 0

    def append(self, text: str) -> None:
        self.total += len(text)
        head_room = max(0, (self.limit + 1) // 2 - len(self.head))
        self.head += text[:head_room]
        tail_limit = self.limit // 2
        if tail_limit:
            self.tail = (self.tail + text[head_room:])[-tail_limit:]

    def getvalue(self) -> str:
        marker = _TRUNCATION_MARKER if self.total > self.limit else ""
        return self.head + marker + self.tail


class _SessionOutputLog:
    """Append child output under a shared session logs byte quota.

    Quota exhaustion stops disk writes, NOT pipe draining or callbacks. Never
    delete existing session files to reclaim space. Directory flock serializes
    cooperating writers across worker threads/processes; no global session map
    is retained. Other writers outside this helper do not participate.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as workspace:
    ...     first = _SessionOutputLog(workspace, quota_bytes=10)
    ...     second = _SessionOutputLog(workspace, quota_bytes=10)
    ...     first.write("abcde")
    ...     second.write("1234567890")
    ...     assert second.truncated
    ...     assert sum(p.stat().st_size for p in Path(workspace, "logs").iterdir()) == 10
    ...     first.close()
    ...     second.close()
    """

    def __init__(self, workspace: str, quota_bytes: int = _SESSION_LOG_QUOTA_BYTES):
        root = Path(workspace).resolve()
        directory = root / "logs"
        directory.mkdir(exist_ok=True)
        # Do not follow a workspace-provided logs symlink outside the session.
        self._dir_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.quota_bytes = max(0, quota_bytes)
        self.truncated = False
        self._file = None
        self.path: str | None = None
        self._directory = directory
        self.name = f"command-{uuid.uuid4().hex}.log"

    def _used_bytes(self, directory_fd: int, depth: int = 0) -> int:
        # Fail closed for adversarially deep trees; do not exhaust the stack/fds.
        if depth >= 32:
            return self.quota_bytes
        used = 0
        with os.scandir(directory_fd) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISREG(info.st_mode):
                    used += info.st_size
                elif stat.S_ISDIR(info.st_mode):
                    child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=directory_fd)
                    try:
                        used += self._used_bytes(child, depth + 1)
                    finally:
                        os.close(child)
                if used >= self.quota_bytes:
                    break
        return used

    def write(self, text: str) -> None:
        if not text or self.truncated:
            return
        data = text.encode("utf-8", errors="replace")
        fcntl.flock(self._dir_fd, fcntl.LOCK_EX)
        try:
            available = max(0, self.quota_bytes - self._used_bytes(self._dir_fd))
            if available and self._file is None:
                # Creation through the checked directory fd avoids path swaps.
                fd = os.open(self.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self._dir_fd)
                self._file = os.fdopen(fd, "wb", buffering=0)
                self.path = str(self._directory / self.name)
            if available:
                # Avoid ending the UTF-8 log inside a multibyte code point.
                part = data[:available].decode("utf-8", errors="ignore").encode("utf-8")
                self._file.write(part)
            self.truncated = len(data) > available
        finally:
            fcntl.flock(self._dir_fd, fcntl.LOCK_UN)

    def close(self) -> None:
        try:
            if self._file is not None:
                self._file.close()
        finally:
            os.close(self._dir_fd)


_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|auth[_-]?token|password|secret|token)"
    r"(\s*[:=]\s*)"
    r"([^\s'\"<>]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")

# --- Governed-subprocess environment (ARC-011 P0-023) -----------------------
# The child of a governed command is built from this allow-list (default-deny):
# anything not enumerated below is dropped from the inherited environment.
# See ARC-011 security spike §4.3 (agent-path env contract).
_CHILD_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Shell / locale / runtime
        "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE",
        "TERM", "TMPDIR", "TMP",
        # Python / venv (PYTHON* / LC_* also kept via prefix match below)
        "VIRTUAL_ENV", "PKG_CONFIG_PATH",
        # Host config / workspace roots (setup.py, direction/prepare.py, enrich_rl_dataset.py)
        "HOST_CONFIGS_PATH", "AUTORESEARCH_HOST_CONFIGS_PATH",
        "AUTORESEARCH_WORKSPACE_ROOT", "WORKSPACE_ROOT",
        # Optional S3-compatible artifact store credentials (boto3-based
        # skill scripts). Skills bring their own service credentials.
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION", "AWS_REGION", "AWS_SESSION_TOKEN",
        "S3_ENDPOINT_URL", "MINIO_ENDPOINT_URL", "MLFLOW_S3_ENDPOINT_URL",
        # mlflow tracking URI only (never any promotion/service token).
        "MLFLOW_TRACKING_URI",
    }
)
# Kept by prefix so the Python family (PYTHONUNBUFFERED, PYTHONPATH, ...) and
# locale family propagate without enumerating every member.
_CHILD_ENV_PREFIXES: tuple[str, ...] = ("PYTHON", "LC_")

# Defense-in-depth: unambiguous server control-plane secrets never needed by an
# experiment script. Subtracted last so a name cannot leak even if it were to
# appear in the allow-list above.
#
# NOTE: ML_ADMIN_TOKEN was historically a platform admin-token alias; it is
# now stripped like the other control-plane secrets.
_FORBIDDEN_CHILD_ENV: frozenset[str] = frozenset(
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
    }
)

# PYTHON* variables that alter interpreter/module resolution. Removed
# even though the PYTHON prefix keep-list would otherwise retain them.
_PATH_AFFECTING_PYTHON_ENV: frozenset[str] = frozenset(
    {
        "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE",
        "PYTHONEXECUTABLE",
    }
)


def _build_child_env(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the env dict handed to a governed subprocess (ARC-011 P0-023).

    Default-deny: only names in ``_CHILD_ENV_ALLOWLIST`` or matching
    ``_CHILD_ENV_PREFIXES`` are kept, then ``_FORBIDDEN_CHILD_ENV`` is
    subtracted. Closes the secret-inheritance gap documented in
    the ARC-011 security spike §4.1 while preserving the experiment-
    legitimate vars the six ``_ALLOWED_SCRIPTS`` entries (and their known
    training children) read.
    """
    source = environ if environ is not None else MappingProxyType(os.environ)
    kept = {
        name: value
        for name, value in source.items()
        if name in _CHILD_ENV_ALLOWLIST
        or any(name.startswith(prefix) for prefix in _CHILD_ENV_PREFIXES)
    }
    for forbidden in _FORBIDDEN_CHILD_ENV:
        kept.pop(forbidden, None)
    # Import/search-path hygiene. The ``PYTHON*`` prefix keep exists for
    # warning/locale knobs, but path-affecting variables would let anything
    # that sets them shadow interpreter or evaluator dependencies, so they
    # are subtracted and user site-packages is disabled outright. Evaluator
    # commands additionally run with ``-E -s`` (see command_policy).
    for name in _PATH_AFFECTING_PYTHON_ENV:
        kept.pop(name, None)
    kept["PYTHONNOUSERSITE"] = "1"
    return kept


OutputStream = Literal["stdout", "stderr"]
OutputCallback = Callable[[OutputStream, str], None]


@dataclass(frozen=True)
class CommandRunResult:
    output: str
    decision: CommandDecision
    returncode: int | None = None
    timed_out: bool = False
    log_path: str | None = None
    log_truncated: bool = False

    @property
    def rejected(self) -> bool:
        return not self.decision.allowed


class CommandProcessRegistry:
    """Thread-safe registry of in-flight governed subprocesses, keyed by session.

    ARC-011 P0-006: ``GovernedCommandRunner.run`` executes inside a worker
    thread (via ``asyncio.to_thread``), so cancelling the awaiting task on a
    hard-timeout or operator stop cannot interrupt the poll loop that owns the
    ``Popen`` handle. The orchestrator's cancel handler therefore calls
    ``kill_all`` to reap the process tree through the existing psutil
    SIGTERM->SIGKILL path (``_terminate_process_group_without_communicate``)
    rather than letting the child leak until its own per-command timeout.

    Written from worker threads (``register``/``unregister``) and read + killed
    from the event-loop thread (``kill_all``); a ``threading.Lock`` serializes
    the dict mutation across both.
    """

    def __init__(self) -> None:
        self._procs: dict[str, set[subprocess.Popen[str]]] = {}
        self._lock = threading.Lock()

    def register(self, research_id: str, proc: subprocess.Popen[str]) -> None:
        with self._lock:
            self._procs.setdefault(research_id, set()).add(proc)

    def unregister(self, research_id: str, proc: subprocess.Popen[str]) -> None:
        with self._lock:
            procs = self._procs.get(research_id)
            if procs is None:
                return
            procs.discard(proc)
            if not procs:
                self._procs.pop(research_id, None)

    @property
    def size(self) -> int:
        """Number of sessions with at least one registered subprocess."""
        with self._lock:
            return len(self._procs)

    def kill_all(self, research_id: str) -> None:
        """Best-effort terminate every still-running subprocess tree for a session.

        Snapshots under the lock, then kills outside it so the psutil wait
        (up to ~10s) does not block worker-thread ``register``/``unregister``.
        Already-exited procs (``poll()`` is not ``None``) are skipped.
        """
        with self._lock:
            procs = list(self._procs.get(research_id, ()))
        for proc in procs:
            try:
                if proc.poll() is None:
                    _terminate_process_group_without_communicate(proc)
            except Exception:
                pass


class GovernedCommandRunner:
    """Validate and execute one approved command without invoking a shell."""

    def __init__(
        self,
        *,
        workspace_root: str,
        session_workspace: str | None = None,
        policy_extension: Mapping[str, Any] | None = None,
        access: ToolAccessContext | None = None,
    ) -> None:
        self._workspace_root = workspace_root
        self._session_workspace = session_workspace
        # ARC-011 review C2: per-skill command-policy extension (manifest
        # ``command_policy:`` section). ``None`` (legacy sessions) keeps the
        # hardcoded validator sets exactly as before.
        self._policy_extension = policy_extension
        # Shared file-operation authorization context (the same one the file
        # tools use). ``None`` derives one inside the policy evaluator.
        self._access = access

    def run(
        self,
        command: str,
        *,
        timeout_s: int,
        output_callback: OutputCallback | None = None,
        proc_registry: CommandProcessRegistry | None = None,
        research_id: str | None = None,
        extra_env: Mapping[str, str] | None = None,
        cwd: str | None = None,
    ) -> CommandRunResult:
        """Validate and execute one approved command without invoking a shell.

        ``cwd`` (P2 per-workdir state) optionally overrides the subprocess
        working directory — used for trial-directory execution. The policy
        still validates against the session workspace (a trial dir lives
        inside it), so the override never widens what a command may touch.
        """
        decision = evaluate_command_policy(
            command,
            workspace_root=self._workspace_root,
            session_workspace=self._session_workspace,
            policy_extension=self._policy_extension,
            access=self._access,
        )
        if not decision.allowed:
            reason = decision.reason or "Command is not allowed"
            return CommandRunResult(
                output=f"Command rejected by policy: {reason}",
                decision=decision,
            )

        # ARC-011 P4-002: build the governed env, then merge session-scoped
        # extra_env (e.g. AUTORESEARCH_SESSION_NONCE) AFTER the forbidden-
        # secret subtraction so the nonce can never be stripped. The extra_env
        # is per-call (per-session) so it never bleeds across concurrent
        # sessions (the static _CHILD_ENV_ALLOWLIST would bleed).
        child_env = _build_child_env()
        if extra_env:
            child_env.update(extra_env)
        argv = decision.argv
        if (
            cwd is not None
            and argv
            and not os.path.isabs(argv[0])
            and os.path.sep in argv[0]
        ):
            # P2 trial-directory execution: a path-like executable (the
            # sanctioned ``.venv/bin/python``) lives beside the workspace
            # root, outside the session workspace, so trial staging cannot
            # carry it into the trial dir. Resolve it against the same root
            # the default cwd used; bare executable names (cp, cat) keep
            # PATH lookup, which the cwd override never affected.
            argv = [os.path.join(self._workspace_root, argv[0]), *argv[1:]]
        proc = subprocess.Popen(
            argv,
            cwd=cwd if cwd is not None else self._workspace_root,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        # ARC-011 P0-006: register the live Popen so a hard-timeout / operator
        # stop cancel can reap this process tree from outside the worker thread
        # (cancelling asyncio.to_thread cannot interrupt this poll loop).
        if proc_registry is not None and research_id is not None:
            proc_registry.register(research_id, proc)
        try:
            stdout, stderr, timed_out, log_path, log_truncated = _collect_process_output(
                proc, timeout_s=timeout_s,
                workspace=self._session_workspace or self._workspace_root,
                output_callback=output_callback,
            )
            output = _truncate_output(redact_sensitive_text(_combine_output(stdout, stderr)))
            if timed_out:
                output = (output + f"\n[Command timed out after {timeout_s}s]"
                          if output else f"Command timed out after {timeout_s}s")
            elif proc.returncode != 0:
                output += f"\n[exit code: {proc.returncode}]"
            if log_path:
                output += f"\n[command log: {log_path}]"
            if log_truncated:
                output += "\n[command log truncated: session logs quota reached or log unavailable]"
            return CommandRunResult(
                output=output or "(no output)",
                decision=decision,
                returncode=proc.returncode,
                timed_out=timed_out,
                log_path=log_path,
                log_truncated=log_truncated,
            )
        finally:
            if proc_registry is not None and research_id is not None:
                proc_registry.unregister(research_id, proc)


def redact_sensitive_text(text: str) -> str:
    """Redact token-like values from command text and subprocess output."""

    text = _BEARER_RE.sub("Bearer <redacted>", text)
    return _SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", text)


def _combine_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    output = ""
    if stdout:
        output += _to_text(stdout)
    if stderr:
        stderr_text = _to_text(stderr)
        output += ("\n--- stderr ---\n" + stderr_text) if output else stderr_text
    return output


def _to_text(value: str | bytes) -> str:
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="replace")


def _collect_process_output(
    proc: subprocess.Popen,
    *,
    timeout_s: float,
    workspace: str,
    output_callback: OutputCallback | None = None,
    log: _SessionOutputLog | None = None,
) -> tuple[str, str, bool, str | None, bool]:
    """Drain both pipes incrementally, without communicate(), threads or queues.

    Keep callbacks line-oriented for ordinary output; exceptionally long lines
    are delivered in bounded fragments. A dead child holding inherited pipes
    open cannot defeat the deadline. Logging failures never stop pipe draining.

    >>> import sys, tempfile
    >>> with tempfile.TemporaryDirectory() as workspace:
    ...     counts = {"stdout": 0, "stderr": 0}
    ...     def callback(name, text):
    ...         assert len(text) <= _OUTPUT_CHUNK_SIZE + 32
    ...         counts[name] += len(text)
    ...     code = "import os; os.write(1, b'x' * 2000000); os.write(2, b'y' * 2000000)"
    ...     proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
    ...                             stderr=subprocess.PIPE, start_new_session=True)
    ...     out, err, expired, path, clipped = _collect_process_output(
    ...         proc, timeout_s=10, workspace=workspace, output_callback=callback)
    ...     assert not expired and not clipped and proc.returncode == 0
    ...     assert len(out) <= 60_020 and len(err) <= 60_020
    ...     assert counts == {"stdout": 2000000, "stderr": 2000000}
    ...     assert Path(path).stat().st_size == 4000000
    ...     log = _SessionOutputLog(workspace, quota_bytes=1)
    ...     proc = subprocess.Popen([sys.executable, "-c", "print('still drained')"],
    ...                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ...                             start_new_session=True)
    ...     out, _, expired, _, clipped = _collect_process_output(
    ...         proc, timeout_s=10, workspace=workspace, log=log)
    ...     assert "still drained" in out and clipped and not expired
    ...     proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
    ...                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ...                             start_new_session=True)
    ...     result = _collect_process_output(proc, timeout_s=0.05, workspace=workspace)
    ...     assert result[2] and proc.poll() is not None
    """
    buffers = {name: _HeadTailBuffer() for name in ("stdout", "stderr")}
    pending = {name: "" for name in buffers}
    decoders = {name: codecs.getincrementaldecoder("utf-8")("replace") for name in buffers}
    log_failed = False
    timed_out = False
    deadline = time.monotonic() + timeout_s

    def emit(name: OutputStream, text: str) -> None:
        nonlocal log_failed
        text = redact_sensitive_text(text)
        buffers[name].append(text)
        if log is not None and not log_failed:
            try:
                log.write(text)
            except OSError:
                log_failed = True
        if output_callback:
            output_callback(name, text)

    # Prefix retained across fragments prevents splitting a token-like key.
    secret_continuation: dict[str, str | None] = {name: None for name in buffers}

    def consume(name: OutputStream, text: str, final: bool = False) -> None:
        pending[name] += text
        while pending[name]:
            continuation = secret_continuation[name]
            if continuation:
                match = re.match(continuation, pending[name])
                if match:
                    pending[name] = pending[name][match.end():]
                if not pending[name]:
                    break
                secret_continuation[name] = None
            newline = pending[name].find("\n", 0, _OUTPUT_CHUNK_SIZE)
            if newline >= 0:
                size = newline + 1
            elif len(pending[name]) >= _OUTPUT_CHUNK_SIZE:
                size = _OUTPUT_CHUNK_SIZE - 128
                # If a redacted value runs through the cut, suppress its
                # continuation too rather than leaking the remainder next time.
                for pattern, continuation_pattern in (
                    (_BEARER_RE, r"[A-Za-z0-9._~+/=-]+"),
                    (_SECRET_VALUE_RE, r"[^\s'\"<>]+"),
                ):
                    for match in pattern.finditer(pending[name]):
                        if match.start() < size <= match.end():
                            if match.start() >= size - 128:
                                size = match.start()
                            else:
                                secret_continuation[name] = continuation_pattern
                            break
                if not secret_continuation[name]:
                    # Keep a potential key suffix intact across the cut.
                    suffix = re.search(r"[A-Za-z_-]+$", pending[name][:size])
                    if suffix and 0 < size - suffix.start() < 128:
                        size = suffix.start()
            elif final:
                size = len(pending[name])
            else:
                break
            emit(name, pending[name][:size])
            pending[name] = pending[name][size:]

    try:
        if log is None:
            try:
                log = _SessionOutputLog(workspace)
            except OSError:
                log_failed = True
        with selectors.DefaultSelector() as selector:
            for name, pipe in (("stdout", proc.stdout), ("stderr", proc.stderr)):
                if pipe is not None:
                    os.set_blocking(pipe.fileno(), False)
                    selector.register(pipe, selectors.EVENT_READ, name)
            while selector.get_map() or proc.poll() is None:
                now = time.monotonic()
                if now >= deadline:
                    if timed_out:
                        break  # escaped descendants may still own pipe handles
                    timed_out = True
                    _terminate_process_group_without_communicate(proc)
                    deadline = time.monotonic() + 2
                for key, _ in selector.select(timeout=0.05):
                    name = key.data
                    try:
                        chunk = os.read(key.fd, _OUTPUT_CHUNK_SIZE)
                    except BlockingIOError:
                        continue
                    consume(name, decoders[name].decode(chunk, final=not chunk), final=not chunk)
                    if not chunk:
                        selector.unregister(key.fileobj)
            for name in buffers:
                consume(name, "", final=True)
        return (
            buffers["stdout"].getvalue(), buffers["stderr"].getvalue(), timed_out,
            log.path if log else None, log_failed or bool(log and log.truncated),
        )
    finally:
        try:
            if proc.poll() is None:
                _terminate_process_group_without_communicate(proc)
        finally:
            for pipe in (proc.stdout, proc.stderr):
                if pipe is not None:
                    pipe.close()
            if log is not None:
                log.close()


def _truncate_output(output: str) -> str:
    if len(output) <= _MAX_OUTPUT_LEN:
        return output
    return output[:30_000] + "\n...(truncated)...\n" + output[-30_000:]


def _terminate_process_group_without_communicate(proc: subprocess.Popen[str]) -> None:
    """Terminate a timed-out process tree without accumulating pipe output."""

    if psutil is not None:
        try:
            root = psutil.Process(proc.pid)
            targets = root.children(recursive=True) + [root]
            for process in targets:
                try:
                    process.terminate()
                except psutil.NoSuchProcess:
                    pass
            _, alive = psutil.wait_procs(targets, timeout=5)
            for process in alive:
                try:
                    process.kill()
                except psutil.NoSuchProcess:
                    pass
            if alive:
                psutil.wait_procs(alive, timeout=5)
        except psutil.NoSuchProcess:
            pass
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            proc.wait(timeout=5)
        return

    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)
