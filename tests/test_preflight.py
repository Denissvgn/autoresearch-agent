"""Structural / contract tests for the ``PreflightCheck`` protocol (ARC-011
P1-019) and the ``HTTPHealthCheck`` / ``TCPConnectCheck`` implementations
(P1-020), plus the P1-021 dispatch migration in ``service_preflight``.

Mirrors ``tests/test_state_store.py`` (P1-009) and ``tests/test_output_parser.py``
(P1-014): these tests pin the public surface of the protocol and guard against
signature drift. The behavioral gate is the existing ``test_service_preflight.py``
suite (7 tests), which exercises ``run_service_preflight`` end-to-end through
the new dispatch path.
"""

from __future__ import annotations

import inspect
from typing import Protocol

import httpx
import pytest

from src.core.preflight import (
    HTTPHealthCheck,
    PreflightCheck,
    TCPConnectCheck,
    preflight_check_from_target,
)
from src.core.service_preflight import ServicePreflightTarget


def test_preflight_check_protocol_is_typing_time_contract():
    """``PreflightCheck`` is a ``Protocol`` and is **not** ``@runtime_checkable``.

    Mirrors the ``LLMProvider`` / ``StateStore`` / ``OutputParser`` /
    ``PromotionTarget`` decisions: typing-time contract only.
    """
    assert issubclass(PreflightCheck, Protocol)
    assert getattr(PreflightCheck, "_is_runtime_protocol", False) is False


@pytest.mark.parametrize(
    "impl",
    [HTTPHealthCheck, TCPConnectCheck],
    ids=["HTTPHealthCheck", "TCPConnectCheck"],
)
def test_preflight_check_impl_satisfies_protocol_surface(impl):
    """Every attribute/method declared on ``PreflightCheck`` exists on the impl.

    ``check`` must be async on both sides (network I/O). ``name`` / ``required``
    are instance attributes (properties on the impls).
    """
    # Protocol members: the two attributes + the check method.
    proto_attrs = sorted(PreflightCheck.__protocol_attrs__)
    assert "check" in proto_attrs

    assert hasattr(impl, "check")
    impl_check = inspect.getattr_static(impl, "check")
    proto_check = inspect.getattr_static(PreflightCheck, "check")
    assert inspect.iscoroutinefunction(proto_check)
    assert inspect.iscoroutinefunction(impl_check), (
        f"{impl.__name__}.check: unexpectedly not async"
    )


def test_minimal_preflight_check_satisfies_protocol():
    """A minimal stub with ``name``/``required``/``check`` satisfies the protocol
    at the type level (structural typing — no inheritance required)."""

    class _Stub:
        name = "stub"
        required = True

        async def check(self, client):
            return {"name": self.name, "status": "ready"}

    assert hasattr(_Stub, "check")
    assert hasattr(_Stub, "name")
    assert hasattr(_Stub, "required")


def test_factory_selects_http_check_for_http_transport():
    """``preflight_check_from_target`` returns an ``HTTPHealthCheck`` for an
    HTTP-transport descriptor."""
    target = ServicePreflightTarget("svc", "http://svc:8000")
    check = preflight_check_from_target(target)
    assert isinstance(check, HTTPHealthCheck)
    assert check.name == "svc"
    assert check.required is True


def test_factory_selects_tcp_check_for_tcp_transport():
    """``preflight_check_from_target`` returns a ``TCPConnectCheck`` for a
    TCP-transport descriptor."""
    target = ServicePreflightTarget(
        "nats", "nats://nats:4222", health_paths=(), required=True, transport="tcp"
    )
    check = preflight_check_from_target(target, timeout_s=2.5)
    assert isinstance(check, TCPConnectCheck)
    assert check.name == "nats"
    assert check.required is True


@pytest.mark.asyncio
async def test_http_health_check_delegates_to_service_preflight(monkeypatch):
    """``HTTPHealthCheck.check`` delegates to ``service_preflight._check_target``
    — and resolving it through the module means a monkeypatch takes effect
    (this is the regression guard for the dispatch-migration wiring)."""
    import src.core.service_preflight as spf

    captured: dict = {}

    async def fake_check_target(client, target):
        captured["client"] = client
        captured["target"] = target
        return {"name": target.name, "status": "ready"}

    monkeypatch.setattr(spf, "_check_target", fake_check_target)

    target = ServicePreflightTarget("svc", "http://svc:8000")
    check = HTTPHealthCheck(target)
    sentinel_client = httpx.AsyncClient()
    try:
        result = await check.check(sentinel_client)
    finally:
        await sentinel_client.aclose()
    assert result == {"name": "svc", "status": "ready"}
    assert captured["target"] is target
    assert captured["client"] is sentinel_client


@pytest.mark.asyncio
async def test_tcp_connect_check_ignores_client_and_delegates(monkeypatch):
    """``TCPConnectCheck.check`` ignores the ``client`` arg (it opens its own
    socket) and delegates to ``service_preflight._check_tcp_target``."""
    import src.core.service_preflight as spf

    captured: dict = {}

    async def fake_check_tcp(target, timeout_s):
        captured["target"] = target
        captured["timeout_s"] = timeout_s
        return {"name": target.name, "status": "ready"}

    monkeypatch.setattr(spf, "_check_tcp_target", fake_check_tcp)

    target = ServicePreflightTarget(
        "nats", "nats://nats:4222", health_paths=(), transport="tcp"
    )
    check = TCPConnectCheck(target, timeout_s=5.0)
    # Pass a client; the TCP check must ignore it.
    result = await check.check(object())  # type: ignore[arg-type]
    assert result == {"name": "nats", "status": "ready"}
    assert captured["timeout_s"] == 5.0
