"""``PreflightCheck`` protocol + concrete checks (ARC-011 P1-019..021).

This module introduces the ``PreflightCheck`` protocol — the abstraction over a
single service-dependency health check. It formalizes the dispatch fork that
previously lived inline in ``service_preflight.run_service_preflight`` (the
``if target.transport == "tcp": _check_tcp_target(...) else: _check_target(...)``
branch):

* ``HTTPHealthCheck`` (P1-020) — wraps ``service_preflight._check_target``.
* ``TCPConnectCheck`` (P1-020) — wraps ``service_preflight._check_tcp_target``
  (generic TCP-connect probe for skill-declared ``tcp`` preflight targets).

``service_preflight.build_service_preflight_targets`` (P1-021) now returns
``list[PreflightCheck]`` and ``run_service_preflight`` dispatches via
``target.check(client)`` instead of the transport fork. The four public free
functions (``run_service_preflight``, ``build_not_run_preflight``,
``require_preflight_ready``, ``sanitize_service_url``) keep their signatures so
the consumers (``session_manager._run_preflight``, ``main.py`` readiness /
monitoring endpoints, ``research_manifest``) are unchanged. The 7
``test_service_preflight.py`` tests are the behavioral gate.

The extraction is **behavior-identical**: every check body is unchanged. Mirrors
the P1-010..012 ``OutputParser``, P1-015..017 ``PromotionTarget``, and
P1-006/007 ``StateStore`` precedents.

Design decisions baked in here:

* **Not ``@runtime_checkable``.** Typing-time contract only — mirrors
  ``LLMProvider`` / ``StateStore`` / ``OutputParser`` / ``PromotionTarget``.
* **``check`` is async.** Health checks are network I/O (HTTP GET or TCP
  connect); the protocol keeps them async. The TCP check ignores the ``client``
  arg (it opens its own socket) — the protocol documents this.
* **``ServicePreflightTarget`` stays in ``service_preflight.py``** as the frozen
  dataclass descriptor; the check classes are constructed from it. This keeps
  the descriptor (a value object) separate from the check (a behavior object),
  matching the existing structure.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from src.core import service_preflight as _spf
from src.core.service_preflight import ServicePreflightTarget


class PreflightCheck(Protocol):
    """A single service-dependency health check (ARC-011 P1-019).

    A concrete check (``HTTPHealthCheck`` / ``TCPConnectCheck`` in P1-020)
    implements this surface. ``run_service_preflight`` (P1-021) dispatches a
    list of ``PreflightCheck`` instances via ``check(client)``.

    The ``client`` arg is the shared ``httpx.AsyncClient`` for HTTP checks; TCP
    checks ignore it (they open their own socket) — see ``TCPConnectCheck``.
    """

    name: str
    required: bool

    async def check(self, client: httpx.AsyncClient | None) -> dict[str, Any]:
        """Run the health check, returning a result dict shaped like
        ``service_preflight._check_target``'s output (``name``, ``url``,
        ``required``, ``status``, ``health_paths``, ``transport``,
        ``checked_url``, ``status_code``, ``latency_ms``, ``error``)."""
        ...


class HTTPHealthCheck:
    """HTTP health-endpoint probe (ARC-011 P1-020).

    Wraps ``service_preflight._check_target`` unchanged. Iterates the target's
    ``health_paths``, GETs each, and treats 2xx-3xx as ready.
    """

    def __init__(self, target: ServicePreflightTarget) -> None:
        self._target = target

    @property
    def name(self) -> str:
        return self._target.name

    @property
    def required(self) -> bool:
        return self._target.required

    async def check(self, client: httpx.AsyncClient | None) -> dict[str, Any]:
        """Delegate to ``service_preflight._check_target`` (behavior-identical).

        Resolved through the ``service_preflight`` module at call time so test
        monkeypatches of ``service_preflight._check_target`` take effect.
        """
        # ``run_service_preflight`` always supplies a client for HTTP checks.
        assert client is not None, "HTTPHealthCheck requires an httpx.AsyncClient"
        return await _spf._check_target(client, self._target)


class TCPConnectCheck:
    """TCP-connect probe (ARC-011 P1-020).

    Wraps ``service_preflight._check_tcp_target`` unchanged. Used for generic
    skill-declared ``tcp`` targets. Opens its own socket via ``asyncio.open_connection`` —
    the ``client`` arg is ignored.
    """

    def __init__(
        self, target: ServicePreflightTarget, *, timeout_s: float = 3.0
    ) -> None:
        self._target = target
        self._timeout_s = timeout_s

    @property
    def name(self) -> str:
        return self._target.name

    @property
    def required(self) -> bool:
        return self._target.required

    async def check(self, client: httpx.AsyncClient | None) -> dict[str, Any]:
        """Delegate to ``service_preflight._check_tcp_target`` (behavior-identical).

        ``client`` is ignored — the TCP check opens its own socket. Resolved
        through the ``service_preflight`` module at call time so test
        monkeypatches of ``service_preflight._check_tcp_target`` take effect.
        """
        return await _spf._check_tcp_target(self._target, self._timeout_s)


def preflight_check_from_target(
    target: ServicePreflightTarget,
    *,
    timeout_s: float = 3.0,
) -> PreflightCheck:
    """Build the right ``PreflightCheck`` for a ``ServicePreflightTarget``.

    P1-021 helper: replaces the ``if target.transport == "tcp"`` dispatch fork
    in ``run_service_preflight`` with a polymorphic ``check()`` call. The
    transport string on the descriptor still selects the check class.
    """
    if target.transport == "tcp":
        return TCPConnectCheck(target, timeout_s=timeout_s)  # type: ignore[return-value]
    return HTTPHealthCheck(target)  # type: ignore[return-value]


__all__ = [
    "HTTPHealthCheck",
    "PreflightCheck",
    "TCPConnectCheck",
    "preflight_check_from_target",
]
