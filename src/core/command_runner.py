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
from typing import Callable, Literal

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


class GovernedCommandRunner:
    """Validate and execute one approved command without invoking a shell."""

    def __init__(
        self,
        *,
        workspace_root: str,
        session_workspace: str | None = None,
    ) -> None:
        self._workspace_root = workspace_root
        self._session_workspace = session_workspace

    def run(
        self,
        command: str,
        *,
        timeout_s: int,
        output_callback: OutputCallback | None = None,
    ) -> CommandRunResult:
        decision = evaluate_command_policy(
            command,
            workspace_root=self._workspace_root,
            session_workspace=self._session_workspace,
        )
        if not decision.allowed:
            reason = decision.reason or "Command is not allowed"
            return CommandRunResult(
                output=f"Command rejected by policy: {reason}",
                decision=decision,
            )

        proc = subprocess.Popen(
            decision.argv,
            cwd=self._workspace_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
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
