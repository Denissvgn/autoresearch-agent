"""Managed process-driver host: custom drivers under qualified isolation.

A custom driver is an external program speaking a versioned JSONL
event/proposal transport on stdout. The host launches it in the qualified
isolation context — explicit environment, server-derived workspace,
rendered instruction artifacts, and a run-scoped credential — supervises
its process group, bounds its output, and normalizes its events.

Authority separation: the driver's ordinary shell activity is never
evaluator execution and never promotion authority. Its proposals are
candidates (model-proposed), its credential cannot carry operator or
approver permissions, and evidence and filesystem policy are enforced by
the host, not granted to the driver.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Optional

from src.core.harness_contract import (
    HARNESS_CONTRACT_VERSION,
    HarnessContractError,
)

MAX_EVENT_BYTES_DEFAULT = 64 * 1024
MAX_STDERR_BYTES = 16 * 1024
MAX_BUFFERED_EVENTS_DEFAULT = 256
MAX_PROTOCOL_ERRORS_DEFAULT = 32
START_DEADLINE_S_DEFAULT = 10.0
CLEANUP_DEADLINE_S_DEFAULT = 5.0

# Environment keys a driver may receive. Anything else from the host's
# environment is stripped — credential isolation by construction.
DRIVER_ENV_ALLOWLIST = frozenset(
    {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "PYTHONPATH",
        "AUTORESEARCH_AGENT_CREDENTIAL",
        "AUTORESEARCH_API_URL",
    }
)


@dataclass
class DriverHostConfig:
    """How one driver process is launched and bounded."""

    executable: tuple[str, ...]
    run_id: str
    workspace: str
    identity: Mapping[str, Any]
    credential: str = ""
    env: Mapping[str, str] = field(default_factory=dict)
    instruction_artifacts: Mapping[str, str] = field(default_factory=dict)
    max_event_bytes: int = MAX_EVENT_BYTES_DEFAULT
    max_buffered_events: int = MAX_BUFFERED_EVENTS_DEFAULT
    max_protocol_errors: int = MAX_PROTOCOL_ERRORS_DEFAULT
    start_deadline_s: float = START_DEADLINE_S_DEFAULT
    cleanup_deadline_s: float = CLEANUP_DEADLINE_S_DEFAULT


@dataclass
class DriverOutcome:
    """The attributed end state of one driver process."""

    status: str  # "completed" | "crashed" | "timeout" | "cancelled"
    exit_code: Optional[int]
    events_delivered: int
    protocol_errors: int
    oversized_events: int
    cleanup_s: float
    reason: str = ""


class DriverProtocolError(HarnessContractError):
    """The driver's transport violated the documented protocol."""


class _EventReader(threading.Thread):
    """Bounded stdout reader: normalizes JSONL, enforces size and queue
    bounds, and records protocol violations instead of trusting them."""

    def __init__(
        self,
        stream: Any,
        config: DriverHostConfig,
        on_event: Any,
    ) -> None:
        super().__init__(daemon=True)
        self._stream = stream
        self._config = config
        self._on_event = on_event
        self.protocol_errors = 0
        self.oversized_events = 0
        self.delivered = 0
        self.backpressure_waits = 0
        self._stop_event = threading.Event()

    def run(self) -> None:
        buffer = b""
        while not self._stop_event.is_set():
            chunk = self._stream.read(4096)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                self._handle_line(line)
                if self.protocol_errors >= self._config.max_protocol_errors:
                    self._stop_event.set()
                    return
            if len(buffer) > self._config.max_event_bytes:
                # an unterminated line past the size cap is never buffered
                self.oversized_events += 1
                buffer = buffer[-self._config.max_event_bytes :]
        if buffer.strip():
            # mid-event death leaves a partial line: malformed, not data
            self.protocol_errors += 1

    def _handle_line(self, line: bytes) -> None:
        if not line.strip():
            return
        if len(line) > self._config.max_event_bytes:
            self.oversized_events += 1
            return
        try:
            event = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.protocol_errors += 1
            return
        if not isinstance(event, dict) or not event.get("type"):
            self.protocol_errors += 1
            return
        self.delivered += 1
        self._on_event(event)


class DriverHost:
    """Supervises one custom driver process through the JSONL transport."""

    def __init__(self, config: DriverHostConfig) -> None:
        self._config = config
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[_EventReader] = None
        self._events: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._started_at = 0.0
        self._handshake_ok = False
        self._outcome: Optional[DriverOutcome] = None
        self._stderr_tail = ""
        self._stderr_bytes = 0

    # -- lifecycle ----------------------------------------------------
    def start(self) -> None:
        """Launch the driver in its isolated context.

        The environment is an allowlist: the driver receives its
        credential and declared settings and nothing else from the host.
        Workspace and instruction artifacts are prepared server-side.
        """
        os.makedirs(self._config.workspace, exist_ok=True)
        for name, content in self._config.instruction_artifacts.items():
            with open(
                os.path.join(self._config.workspace, name), "w"
            ) as handle:
                handle.write(content)
        env = {
            key: os.environ[key]
            for key in DRIVER_ENV_ALLOWLIST
            if key in os.environ
        }
        env.update({k: str(v) for k, v in self._config.env.items()})
        if self._config.credential:
            env["AUTORESEARCH_AGENT_CREDENTIAL"] = self._config.credential
        self._started_at = time.monotonic()
        try:
            self._process = subprocess.Popen(
                list(self._config.executable),
                cwd=self._config.workspace,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,  # its own process group: descendants
            )
        except OSError as exc:
            raise HarnessContractError(
                f"driver executable unavailable: {exc}"
            ) from None
        self._reader = _EventReader(
            self._process.stdout, self._config, self._record
        )
        self._reader.start()
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, daemon=True
        )
        self._stderr_thread.start()

    def _drain_stderr(self) -> None:
        """Bounded stderr capture: never unbounded, never lost silently."""
        assert self._process is not None and self._process.stderr is not None
        collected = b""
        while True:
            chunk = self._process.stderr.read(4096)
            if not chunk:
                break
            if len(collected) < MAX_STDERR_BYTES:
                collected += chunk
            self._stderr_bytes += len(chunk)
        self._stderr_tail = collected[-MAX_STDERR_BYTES:].decode(
            "utf-8", "replace"
        )

    def _record(self, event: dict[str, Any]) -> None:
        with self._lock:
            if len(self._events) >= self._config.max_buffered_events:
                # backpressure: bounded buffer, oldest retained; the pipe
                # fills and the driver blocks rather than the host growing
                self._events.pop(0)
            self._events.append(event)
        if event.get("type") == "hello":
            version = event.get("contract_version")
            self._handshake_ok = version == HARNESS_CONTRACT_VERSION

    def events(self, *, wait_s: float = 0.0) -> list[dict[str, Any]]:
        """Drain the normalized events delivered so far."""
        if wait_s > 0:
            time.sleep(wait_s)
        with self._lock:
            drained = list(self._events)
            self._events.clear()
        return drained

    def wait(self, *, timeout_s: float) -> DriverOutcome:
        """Wait for the driver to finish; enforce the start deadline."""
        assert self._process is not None and self._reader is not None
        deadline = time.monotonic() + max(0.0, timeout_s)
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                break
            if (
                not self._handshake_ok
                and time.monotonic() - self._started_at
                > self._config.start_deadline_s
            ):
                self.cancel(reason="start deadline exceeded")
                return self._finish("timeout", "start deadline exceeded")
            time.sleep(0.02)
        else:
            self.cancel(reason="run deadline exceeded")
            return self._finish("timeout", "run deadline exceeded")
        self._reader.join(timeout=self._config.cleanup_deadline_s)
        status = "completed"
        reason = ""
        if self._reader.protocol_errors and not self._handshake_ok:
            status = "crashed"
            reason = "no valid handshake"
        elif self._process.returncode not in (0, None):
            status = "crashed"
            reason = f"exit code {self._process.returncode}"
        return self._finish(status, reason)

    def cancel(self, *, reason: str = "") -> None:
        """Terminate the driver's whole process group, bounded in time."""
        if self._process is None or self._process.poll() is not None:
            return
        try:
            os.killpg(self._process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + self._config.cleanup_deadline_s
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                return
            time.sleep(0.02)
        try:
            os.killpg(self._process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self._process.wait(timeout=self._config.cleanup_deadline_s)

    def _finish(self, status: str, reason: str) -> DriverOutcome:
        if self._outcome is not None:
            return self._outcome
        assert self._reader is not None
        self._outcome = DriverOutcome(
            status=status,
            exit_code=self._process.returncode if self._process else None,
            events_delivered=self._reader.delivered,
            protocol_errors=self._reader.protocol_errors,
            oversized_events=self._reader.oversized_events,
            cleanup_s=0.0,
            reason=reason,
        )
        return self._outcome

    @property
    def outcome(self) -> Optional[DriverOutcome]:
        return self._outcome

    @property
    def stderr_tail(self) -> str:
        """The bounded tail of the driver's stderr (diagnostics)."""
        return self._stderr_tail

    @property
    def handshake_ok(self) -> bool:
        return self._handshake_ok
