"""Governed subprocess runner for autoresearch agent commands."""

from __future__ import annotations

import re
import os
import signal
import subprocess
from dataclasses import dataclass

from server.core.command_policy import CommandDecision, evaluate_command_policy


_MAX_OUTPUT_LEN = 60_000
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|auth[_-]?token|password|secret|token)"
    r"(\s*[:=]\s*)"
    r"([^\s'\"<>]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


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

    def run(self, command: str, *, timeout_s: int) -> CommandRunResult:
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
        try:
            stdout, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            stdout, stderr = _terminate_process_group(proc)
            partial = _combine_output(stdout, stderr)
            if partial:
                partial = _truncate_output(redact_sensitive_text(partial))
            timeout_msg = f"\n[Command timed out after {timeout_s}s]"
            return CommandRunResult(
                output=(partial + timeout_msg) if partial else f"Command timed out after {timeout_s}s",
                decision=decision,
                returncode=proc.returncode,
                timed_out=True,
            )

        output = _combine_output(stdout, stderr)
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


def _truncate_output(output: str) -> str:
    if len(output) <= _MAX_OUTPUT_LEN:
        return output
    return output[:30_000] + "\n...(truncated)...\n" + output[-30_000:]


def _terminate_process_group(proc: subprocess.Popen[str]) -> tuple[str | None, str | None]:
    """Terminate a timed-out process and every child in its process group."""

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
