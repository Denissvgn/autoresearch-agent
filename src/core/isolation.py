"""Enforced process isolation: mounts, identity, and network at the OS boundary.

This module is the universal execution boundary for candidate-controlled
subprocesses. It wraps a command behind an OS-enforced sandbox (the
selected Linux backend) instead of trusting in-process checks: filesystem
writes outside the declared write roots fail at the kernel, network access
is default-deny at the namespace, and every child process inherits the
same policy.

Backend spike (bounded, mount/identity/network/resource probes):

* **Container deployment (first candidate, docker 28.4.0):** enforcement
  demonstrated — ``--read-only`` refused writes at the mount layer,
  ``--user`` changed the process identity, ``--network none`` made all
  destinations unreachable, and resource flags bind through cgroups. It is
  the outer deployment boundary, but it fails the per-execution contract:
  the daemon is not available from inside the deployed service container,
  and mapping the pinned workspace interpreter into an image cannot
  preserve the interpreter pin across environments.
* **bubblewrap 0.11.1 (selected):** the same enforcement demonstrated
  with the exact pinned interpreter — read-only root and read-only
  workspace refused writes (``fs_write: none``), a writable bind
  permitted only workspace writes (``fs_write: workspace``), the shared
  user/mount/pid/net namespace made every destination unreachable and
  contained spawned children, and it runs unprivileged wherever user
  namespaces are permitted.

Network allowlists (``host:port`` egress) are **not enforceable** by
either backend at the OS boundary (namespaces are all-or-nothing without
host firewall authority). Requests for allowed destinations are refused
as unsupported capability requests — never silently widened — and full
allowlist enforcement remains qualification WAITING_EXTERNAL on host
firewall authority.

Trusted local-code mode is an operator policy, separately labeled and
never advertised as sandboxed: see ``TRUSTED_LOCAL_CODE``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Literal, Optional, Sequence

#: Result-label vocabulary. ``sandboxed`` is only ever claimed for runs the
#: backend actually wrapped; the operator's local-code policy is labeled
#: ``trusted_local_code`` and is never described as sandboxed.
SANDBOXED_PREFIX = "sandboxed:"
TRUSTED_LOCAL_CODE = "trusted_local_code"


class IsolationError(RuntimeError):
    """Base class for isolation boundary failures (always fail-closed)."""


class IsolationUnavailableError(IsolationError):
    """Host prerequisites for the isolation backend are missing."""


class UnsupportedCapabilityError(IsolationError):
    """A capability request the selected backend cannot enforce."""


@dataclass(frozen=True)
class IsolationPolicy:
    """The declared boundary for one candidate-controlled subprocess.

    ``fs_write`` is enforced at the mount layer (``none`` = read-only
    everywhere, ``workspace`` = writable session workspace only);
    ``network`` is enforced at the network namespace (``deny`` is the only
    enforceable mode — see the module docstring). Read roots are mounted
    read-only; nothing outside the declared roots is visible.
    """

    fs_write: Literal["none", "workspace"] = "none"
    #: Explicit network endpoints the plugin may reach (``host:port`` strings,
    #: matching :attr:`skill_manifest.PluginCaps.network_egress`). Empty tuple
    #: = default-deny (the only enforceable mode on this backend); non-empty is
    #: refused (UnsupportedCapabilityError) until host firewall authority exists.
    network_egress: tuple[str, ...] = ()
    #: Roots mounted read-only (skill package, interpreter, host configs...).
    read_roots: tuple[str, ...] = ()
    #: Roots mounted read-write — only consulted when ``fs_write == "workspace"``.
    write_roots: tuple[str, ...] = ()
    #: Paths hidden inside the sandbox (masked with an empty tmpfs after the
    #: binds) — e.g. the evaluator code a plugin must not read.
    masked_roots: tuple[str, ...] = ()
    #: The directory the process starts in (must be inside a declared root).
    cwd: Optional[str] = None


@dataclass(frozen=True)
class BwrapBackend:
    """The selected isolation backend (bubblewrap 0.11.1)."""

    name: str = "bwrap"

    def wrap(self, argv: Sequence[str], *, policy: IsolationPolicy) -> list[str]:
        """Return the sandboxed command line enforcing ``policy``.

        Raises :class:`UnsupportedCapabilityError` for any capability this
        backend cannot enforce at the OS boundary (network allowlists).
        """
        if policy.network_egress:
            raise UnsupportedCapabilityError(
                "network allowlist enforcement is not available at the OS "
                "boundary on this backend; capability refused (no fallback "
                "to unrestricted egress)"
            )
        cmd: list[str] = [
            "bwrap",
            # Process-tree containment: the sandbox dies with the caller and
            # every child inherits the same mounts/namespace policy.
            "--die-with-parent",
            "--unshare-all",
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            "--tmpfs", "/run",
        ]
        system_roots = ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc")
        seen: set[str] = set()
        for root in system_roots:
            if os.path.isdir(root):
                cmd += ["--ro-bind", root, root]
                seen.add(root)
        read_roots = [os.path.abspath(r) for r in policy.read_roots if r]
        if (
            policy.cwd
            and os.path.isdir(policy.cwd)
            and os.path.abspath(policy.cwd) not in read_roots
        ):
            # The start directory must always be visible (read-only unless a
            # declared write root) so chdir cannot fail on a hidden path.
            read_roots.append(os.path.abspath(policy.cwd))
        for root in read_roots:
            if root and os.path.exists(root) and root not in seen:
                # Files (declared input artifacts) bind read-only too.
                cmd += ["--ro-bind", root, root]
                seen.add(root)
        for root in policy.write_roots:
            root = os.path.abspath(root) if root else root
            if root and os.path.isdir(root):
                if policy.fs_write == "workspace":
                    cmd += ["--bind", root, root]
                else:
                    cmd += ["--ro-bind", root, root]
        for root in policy.masked_roots:
            root = os.path.abspath(root) if root else root
            if root and os.path.isdir(root):
                # Masked after the binds: the path exists but exposes nothing
                # (an empty tmpfs) — evaluator code stays unreadable.
                cmd += ["--tmpfs", root]
        if policy.cwd:
            cmd += ["--chdir", os.path.abspath(policy.cwd)]
        cmd += ["--", *argv]
        return cmd


def probe_host(*, bwrap_bin: Optional[str] = None) -> dict[str, object]:
    """Probe the host features the selected backend requires (real checks).

    Returns a diagnostic dict; ``ready`` is True only when every required
    feature (binary present, user namespaces permitted) is demonstrated.
    """
    binary = bwrap_bin or shutil.which("bwrap")
    info: dict[str, object] = {"backend": "bwrap", "binary": binary or ""}
    if not binary:
        info["ready"] = False
        info["reason"] = "bwrap binary not found"
        return info
    try:
        proc = subprocess.run(
            ["unshare", "--user", "--map-root-user", "/bin/true"],
            capture_output=True,
            timeout=10,
        )
        user_ns = proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        user_ns = False
    info["user_namespaces"] = user_ns
    info["ready"] = bool(user_ns)
    if not user_ns:
        info["reason"] = "user namespaces not permitted on this host"
    return info


def select_backend() -> BwrapBackend:
    """Select the isolation backend or raise :class:`IsolationUnavailableError`.

    Selection is a demonstrated one (see the module docstring): the backend
    is returned only when the host probe passes; unavailable host authority
    raises instead of falling back to unsandboxed execution.
    """
    info = probe_host()
    if not info.get("ready"):
        raise IsolationUnavailableError(
            f"isolation backend unavailable: {info.get('reason', 'host probe failed')}"
        )
    return BwrapBackend()


def wrap_command(
    argv: Sequence[str], *, policy: IsolationPolicy, backend: Optional[BwrapBackend] = None
) -> list[str]:
    """Wrap ``argv`` in the isolation boundary (selecting the backend if needed)."""
    if policy.network_egress:
        raise UnsupportedCapabilityError(
            "network allowlist enforcement is not available at the OS "
            "boundary on this backend; capability refused (no fallback "
            "to unrestricted egress)"
        )
    return (backend or select_backend()).wrap(argv, policy=policy)


__all__ = [
    "SANDBOXED_PREFIX",
    "TRUSTED_LOCAL_CODE",
    "IsolationError",
    "IsolationUnavailableError",
    "UnsupportedCapabilityError",
    "IsolationPolicy",
    "BwrapBackend",
    "probe_host",
    "select_backend",
    "wrap_command",
]