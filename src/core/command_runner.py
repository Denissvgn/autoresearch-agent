"""Governed subprocess runner for autoresearch agent commands."""

from __future__ import annotations

import os
import queue
import re
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Literal, Mapping

from src.core.command_policy import CommandDecision, evaluate_command_policy

try:
    import psutil
except ImportError:  # pragma: no cover - dependency is declared for runtime.
    psutil = None  # type: ignore[assignment]


_MAX_OUTPUT_LEN = 60_000
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|auth[_-]?token|password|secret|token)"
    r"(\s*[:=]\s*)"
    r"([^\s'\"<>]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")

# --- Governed-subprocess environment (ARC-011 P0-023) -----------------------
# The child of a governed command is built from this allow-list (default-deny):
# anything not enumerated below is dropped from the inherited environment.
# See docs/adr/ARC-011-security-spike.md §4.3 (agent-path env contract).
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
# NOTE: ML_ADMIN_TOKEN is intentionally NOT forbidden. In config.py it is an
# alias for BOTH rl_trainer_service_token (which rl/prepare.py needs to call
# rl-trainer) AND mlflow_service_auth_token (the production-promotion token).
# It cannot be cleanly stripped by name without breaking RL auth; splitting
# that alias is tracked as a follow-up to P0-023.
_FORBIDDEN_CHILD_ENV: frozenset[str] = frozenset(
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
    }
)


def _build_child_env(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the env dict handed to a governed subprocess (ARC-011 P0-023).

    Default-deny: only names in ``_CHILD_ENV_ALLOWLIST`` or matching
    ``_CHILD_ENV_PREFIXES`` are kept, then ``_FORBIDDEN_CHILD_ENV`` is
    subtracted. Closes the secret-inheritance gap documented in
    docs/adr/ARC-011-security-spike.md §4.1 while preserving the experiment-
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
    return kept


OutputStream = Literal["stdout", "stderr"]
OutputCallback = Callable[[OutputStream, str], None]


@dataclass(frozen=True)
class CommandRunResult:
    output: str
    decision: CommandDecision
    returncode: int | None = None
    timed_out: bool = False

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
    ) -> None:
        self._workspace_root = workspace_root
        self._session_workspace = session_workspace
        # ARC-011 review C2: per-skill command-policy extension (manifest
        # ``command_policy:`` section). ``None`` (legacy sessions) keeps the
        # hardcoded validator sets exactly as before.
        self._policy_extension = policy_extension

    def run(
        self,
        command: str,
        *,
        timeout_s: int,
        output_callback: OutputCallback | None = None,
        proc_registry: CommandProcessRegistry | None = None,
        research_id: str | None = None,
        extra_env: Mapping[str, str] | None = None,
    ) -> CommandRunResult:
        decision = evaluate_command_policy(
            command,
            workspace_root=self._workspace_root,
            session_workspace=self._session_workspace,
            policy_extension=self._policy_extension,
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
        proc = subprocess.Popen(
            decision.argv,
            cwd=self._workspace_root,
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
            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []
            output_queue: queue.Queue[tuple[OutputStream, str]] = queue.Queue()
            readers = _start_output_readers(proc, output_queue)
            timed_out = False
            started_at = time.monotonic()

            while True:
                _drain_output_queue(
                    output_queue, stdout_chunks, stderr_chunks, output_callback,
                )
                if proc.poll() is not None:
                    if all(not reader.is_alive() for reader in readers):
                        _drain_output_queue(
                            output_queue, stdout_chunks, stderr_chunks, output_callback,
                        )
                        break
                elif time.monotonic() - started_at > timeout_s:
                    timed_out = True
                    _terminate_process_group_without_communicate(proc)

                if timed_out:
                    for reader in readers:
                        reader.join(timeout=1)
                    _drain_output_queue(
                        output_queue, stdout_chunks, stderr_chunks, output_callback,
                    )
                    partial = _combine_output(
                        "".join(stdout_chunks), "".join(stderr_chunks),
                    )
                    if partial:
                        partial = _truncate_output(redact_sensitive_text(partial))
                    timeout_msg = f"\n[Command timed out after {timeout_s}s]"
                    return CommandRunResult(
                        output=(
                            (partial + timeout_msg)
                            if partial
                            else f"Command timed out after {timeout_s}s"
                        ),
                        decision=decision,
                        returncode=proc.returncode,
                        timed_out=True,
                    )

                time.sleep(0.05)

            output = _combine_output("".join(stdout_chunks), "".join(stderr_chunks))
            output = _truncate_output(redact_sensitive_text(output))
            if proc.returncode != 0:
                output += f"\n[exit code: {proc.returncode}]"
            return CommandRunResult(
                output=output or "(no output)",
                decision=decision,
                returncode=proc.returncode,
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


def _start_output_readers(
    proc: subprocess.Popen[str],
    output_queue: queue.Queue[tuple[OutputStream, str]],
) -> list[threading.Thread]:
    def reader(stream_name: OutputStream, pipe) -> None:
        if pipe is None:
            return
        try:
            for line in iter(pipe.readline, ""):
                if line:
                    output_queue.put((stream_name, line))
        finally:
            try:
                pipe.close()
            except OSError:
                pass

    readers = [
        threading.Thread(
            target=reader, args=("stdout", proc.stdout), daemon=True,
        ),
        threading.Thread(
            target=reader, args=("stderr", proc.stderr), daemon=True,
        ),
    ]
    for thread in readers:
        thread.start()
    return readers


def _drain_output_queue(
    output_queue: queue.Queue[tuple[OutputStream, str]],
    stdout_chunks: list[str],
    stderr_chunks: list[str],
    output_callback: OutputCallback | None,
) -> None:
    while True:
        try:
            stream_name, chunk = output_queue.get_nowait()
        except queue.Empty:
            return
        if stream_name == "stderr":
            stderr_chunks.append(chunk)
        else:
            stdout_chunks.append(chunk)
        if output_callback:
            output_callback(stream_name, redact_sensitive_text(chunk))


def _truncate_output(output: str) -> str:
    if len(output) <= _MAX_OUTPUT_LEN:
        return output
    return output[:30_000] + "\n...(truncated)...\n" + output[-30_000:]


def _terminate_process_group_without_communicate(proc: subprocess.Popen[str]) -> None:
    """Terminate a timed-out process tree while reader threads drain pipes."""

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


def _terminate_process_group(proc: subprocess.Popen[str]) -> tuple[str | None, str | None]:
    """Terminate a timed-out process and its descendant tree."""

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
        try:
            return proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return proc.communicate()

    # Fallback for environments that have not installed psutil yet.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        return proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return proc.communicate()
