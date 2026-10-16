"""Bounded resource use, output, and cancellation for candidate subprocesses.

This module is the resource layer of the universal execution boundary. Every
candidate-controlled subprocess (skill plugins, governed evaluator commands)
runs under finite, configurable caps and is stopped as a whole process tree the
moment a cap is breached — the parent never waits for the child to finish
before reacting, and never buffers output without a bound.

Enforcement map (kernel where available, parent-side where not):

* **cumulative CPU** — the tree guard sums CPU across the whole process tree
  against the cap (true cumulative accounting, not per-interval deltas) and
  terminates immediately; ``prlimit --cpu`` adds a per-process kernel backstop.
* **process-tree memory** — the tree guard sums RSS across the tree and
  terminates immediately on breach.
* **wall time** — the drain loop enforces the deadline and terminates
  immediately on expiry.
* **process count** — the tree guard counts descendants and terminates
  immediately above the cap.
* **filesystem quota** — ``prlimit --fsize`` (kernel, per-file). This is the
  one cap with no parent-side enforcement: when it is configured and the
  ``prlimit`` binary is unavailable the capability is **rejected** rather than
  run unbounded.
* **output quota** — the drain loop counts delivered bytes and terminates
  immediately past the configured bound; capture itself is chunk-bounded.

Termination is bounded: :data:`TERMINATION_BOUND_S` is the documented tested
bound from the moment a violation is observed to the moment the process tree
is gone (SIGTERM, short bounded wait, SIGKILL, short bounded wait). Callers
receive an explicit ``cleanup_incomplete`` status when descendants survive
that window; successful cleanup leaves no orphaned child.
"""
from __future__ import annotations

import os
import selectors
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

try:
    import psutil
except ImportError:  # pragma: no cover - dependency is declared for runtime.
    psutil = None  # type: ignore[assignment]

#: Documented tested bound (seconds) from observed violation to terminated
#: tree. The termination probes in the test suite assert against this value.
TERMINATION_BOUND_S = 5.0

#: Read granularity for bounded output draining.
_DRAIN_CHUNK_BYTES = 8_192


class UnenforceableResourceCapabilityError(RuntimeError):
    """A configured resource cap cannot be enforced on this host (fail-closed)."""


@dataclass(frozen=True)
class ProcessResourceCaps:
    """Finite resource caps for one candidate-controlled subprocess tree.

    ``None`` means the cap is not requested for this run. Every configured
    value is enforced at the OS boundary or the parent boundary as described
    in the module docstring; unenforceable configured caps raise
    :class:`UnenforceableResourceCapabilityError` at spawn time.
    """

    #: Wall-clock seconds (parent deadline).
    wall_s: Optional[float] = None
    #: Cumulative CPU seconds across the process tree.
    cpu_s: Optional[float] = None
    #: Sum of RSS across the process tree, megabytes.
    rss_mb: Optional[int] = None
    #: Maximum number of live processes in the tree.
    max_processes: Optional[int] = None
    #: Maximum total bytes delivered on stdout+stderr before termination.
    max_output_bytes: Optional[int] = None
    #: Maximum size of any single file the tree writes (kernel, RLIMIT_FSIZE).
    max_file_write_bytes: Optional[int] = None


def terminate_process_tree(proc: "subprocess.Popen") -> bool:
    """Terminate one subprocess tree within a bounded cleanup window.

    SIGTERM the tree, wait up to half the termination bound, SIGKILL the
    remainder, wait again. Returns ``True`` when no descendant survives
    (successful cleanup); ``False`` means cleanup is incomplete and the
    caller must surface that status explicitly.
    """
    if psutil is None:  # pragma: no cover - dependency is declared for runtime.
        try:
            proc.terminate()
            proc.wait(timeout=TERMINATION_BOUND_S)
            return True
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            return False
    try:
        root = psutil.Process(proc.pid)
        targets = root.children(recursive=True) + [root]
    except psutil.NoSuchProcess:
        try:
            proc.wait(timeout=0.2)
        except Exception:
            pass
        return True
    for process in targets:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    try:
        # Reap the root through the Popen handle first (exactly once) so its
        # returncode reflects the real exit status — a psutil reap would make
        # Popen report 0 via ECHILD.
        proc.wait(timeout=TERMINATION_BOUND_S / 2)
    except subprocess.TimeoutExpired:
        pass
    _, alive = psutil.wait_procs(targets, timeout=TERMINATION_BOUND_S / 2)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    if alive:
        _, alive = psutil.wait_procs(alive, timeout=TERMINATION_BOUND_S / 2)
    if proc.poll() is None:
        try:
            proc.kill()
            proc.wait(timeout=0.5)
        except Exception:
            pass
    return not alive and proc.poll() is not None


def rlimit_prefix(caps: ProcessResourceCaps) -> list[str]:
    """Spawn prefix applying kernel rlimits, or a refusal for unenforceable caps.

    ``prlimit`` (util-linux) sets the limits on the spawn root; descendants
    inherit them. Per-file write quota (RLIMIT_FSIZE) has no parent-side
    enforcement, so a configured value without ``prlimit`` raises
    :class:`UnenforceableResourceCapabilityError` instead of running
    unbounded.
    """
    if caps.max_file_write_bytes is None and caps.cpu_s is None:
        return []
    binary = shutil.which("prlimit")
    if binary is None:
        if caps.max_file_write_bytes is not None:
            raise UnenforceableResourceCapabilityError(
                "filesystem write quota (RLIMIT_FSIZE) requires the prlimit "
                "binary; capability rejected rather than run unbounded"
            )
        return []
    prefix = [binary]
    if caps.cpu_s is not None:
        cpu = max(1, int(caps.cpu_s))
        prefix += [f"--cpu={cpu}:{cpu + 1}"]
    if caps.max_file_write_bytes is not None:
        fsize = int(caps.max_file_write_bytes)
        prefix += [f"--fsize={fsize}"]
    prefix += ["--"]
    return prefix


class TreeResourceGuard:
    """Polls one subprocess tree and terminates it the moment a cap is breached.

    Cumulative CPU is summed across the whole tree and compared against the
    cap directly (never per-interval deltas); RSS is summed across the tree;
    process count includes the root. On the first breach the guard terminates
    the tree itself — there is no flag-for-later-check phase — and records the
    attributed violation kind.
    """

    _POLL_INTERVAL_S = 0.1

    def __init__(self, proc: "subprocess.Popen", caps: ProcessResourceCaps) -> None:
        self._proc = proc
        self._caps = caps
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.violation: Optional[str] = None
        self.cleanup_incomplete = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _record(self, kind: str) -> None:
        with self._lock:
            if self.violation is None:
                self.violation = kind
        if not terminate_process_tree(self._proc):
            self.cleanup_incomplete = True

    def _loop(self) -> None:
        if psutil is None:  # pragma: no cover - dependency is declared for runtime.
            return
        try:
            root = psutil.Process(self._proc.pid)
        except (psutil.NoSuchProcess, Exception):  # noqa: B014
            return
        while not self._stop.is_set():
            try:
                members = root.children(recursive=True) + [root]
            except psutil.NoSuchProcess:
                return
            total_rss = 0
            total_cpu = 0.0
            live = 0
            for member in members:
                try:
                    total_rss += member.memory_info().rss
                    cpu = member.cpu_times()
                    total_cpu += (cpu.user or 0.0) + (cpu.system or 0.0)
                    live += 1
                except (psutil.NoSuchProcess, Exception):  # noqa: B014
                    pass
            if self._caps.max_processes is not None and live > self._caps.max_processes:
                self._record("processes")
                return
            if self._caps.rss_mb is not None and total_rss > self._caps.rss_mb * 1024 * 1024:
                self._record("rss")
                return
            # Cumulative CPU across the tree, compared against the cap itself.
            if self._caps.cpu_s is not None and total_cpu > self._caps.cpu_s:
                self._record("cpu")
                return
            self._stop.wait(self._POLL_INTERVAL_S)


@dataclass(frozen=True)
class DrainOutcome:
    """Result of one bounded drain: captured bytes plus attributed status."""

    stdout: bytes
    stderr: bytes
    timed_out: bool = False
    #: Attributed violation kind ("cpu", "rss", "processes", "output",
    #: "file_size", "wall_time") or None when the run finished normally.
    violation: Optional[str] = None
    #: True when the tree could not be fully reaped within the bound.
    cleanup_incomplete: bool = False


def bounded_drain(
    proc: "subprocess.Popen",
    *,
    input_bytes: Optional[bytes],
    caps: ProcessResourceCaps,
    guard: Optional[TreeResourceGuard] = None,
) -> DrainOutcome:
    """Run one subprocess to completion under bounded capture and caps.

    The input payload is written and stdin closed up front (payloads are
    server-built and fit the pipe buffer). stdout/stderr are drained in fixed
    chunks and counted against ``max_output_bytes``; capture retains a
    bounded head and rolling tail only. The wall deadline, the output quota,
    and the guard's violations all terminate the tree immediately from the
    drain loop — never after an unbounded ``communicate`` — and the loop
    reacts within one poll interval.
    """
    stdout_buf = bytearray()
    stderr_buf = bytearray()
    tail_limit = 64 * 1024
    total = 0
    violation: Optional[str] = None
    timed_out = False
    cleanup_incomplete = False

    if input_bytes is not None:
        try:
            assert proc.stdin is not None
            proc.stdin.write(input_bytes)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    sel = selectors.DefaultSelector()
    for stream, name in ((proc.stdout, "stdout"), (proc.stderr, "stderr")):
        if stream is not None:
            sel.register(stream, selectors.EVENT_READ, name)

    deadline = time.monotonic() + caps.wall_s if caps.wall_s else None
    idle_after_exit = 0
    while True:
        if guard is not None and guard.violation is not None:
            violation = guard.violation
            cleanup_incomplete = guard.cleanup_incomplete
            break
        now = time.monotonic()
        if deadline is not None and now >= deadline:
            violation = "wall_time"
            timed_out = True
            break
        timeout = 0.1
        if deadline is not None:
            timeout = min(timeout, max(0.0, deadline - now))
        events = sel.select(timeout)
        if events:
            idle_after_exit = 0
        elif proc.poll() is not None:
            # Root exited: a grandchild may hold the inherited pipes open.
            # Drain nothing for a short grace, then stop — capture is bounded
            # and the tree cleanup below reaps any such holder.
            idle_after_exit += 1
            if idle_after_exit >= 3:
                break
        for key, _mask in events:
            try:
                chunk = os.read(key.fd, _DRAIN_CHUNK_BYTES)
            except (OSError, ValueError):
                chunk = b""
            if not chunk:
                sel.unregister(key.fileobj)
                continue
            total += len(chunk)
            if caps.max_output_bytes is not None and total > caps.max_output_bytes:
                violation = "output"
                break
            buf = stdout_buf if key.data == "stdout" else stderr_buf
            buf.extend(chunk)
            if len(buf) > tail_limit:
                del buf[:-tail_limit]
        if violation is not None:
            break
        if not sel.get_map() and proc.poll() is not None:
            break

    sel.close()
    if violation is not None and not cleanup_incomplete:
        if not terminate_process_tree(proc):
            cleanup_incomplete = True
        if guard is not None and guard.cleanup_incomplete:
            cleanup_incomplete = True
    else:
        try:
            proc.wait(timeout=TERMINATION_BOUND_S)
        except subprocess.TimeoutExpired:
            cleanup_incomplete = not terminate_process_tree(proc)
    if guard is not None and guard.violation and (
        violation is None or violation == "wall_time"
    ):
        # The guard kills the tree out-of-band; its attribution explains an
        # otherwise-unattributed early exit (closed pipes) precisely.
        violation = guard.violation
    if violation is None:
        # Kernel rlimit deaths (SIGXCPU / SIGXFSZ) attribute to their cap.
        violation = signal_violation(proc.returncode)
    return DrainOutcome(
        stdout=bytes(stdout_buf),
        stderr=bytes(stderr_buf),
        timed_out=timed_out,
        violation=violation,
        cleanup_incomplete=cleanup_incomplete,
    )


def _has_pending(sel: "selectors.DefaultSelector") -> bool:
    """True while any stream is still registered (pipes may be idle but open)."""
    return bool(sel.get_map())


def signal_violation(returncode: Optional[int]) -> Optional[str]:
    """Attribute a signal death to its resource cap (kernel enforcement path)."""
    if returncode == -getattr(signal, "SIGXFSZ", 25):
        return "file_size"
    if returncode == -getattr(signal, "SIGXCPU", 24):
        return "cpu"
    return None


__all__ = [
    "TERMINATION_BOUND_S",
    "UnenforceableResourceCapabilityError",
    "ProcessResourceCaps",
    "DrainOutcome",
    "TreeResourceGuard",
    "terminate_process_tree",
    "rlimit_prefix",
    "bounded_drain",
    "signal_violation",
]
