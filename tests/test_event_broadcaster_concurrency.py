"""P0-014 — EventBroadcaster concurrency stress tests.

The backlog names this file explicitly (``ARC-011-backlog.md`` §3, task
P0-014). The existing broadcaster coverage in ``test_hardening_phase1_to_5.py``
uses a ``_FakeWS`` whose ``send_text`` has no suspension point, so
``asyncio.gather`` does not produce real interleaving — it cannot catch a
regression if the snapshot-before-iterate hardening were removed. These tests
use fake sockets that ``await asyncio.sleep(0)`` (or longer) inside
``send_text`` so the event loop interleaves broadcast, connect, and disconnect
for real.

Also covers the P0-013 per-send timeout (``_BROADCAST_SEND_TIMEOUT_S``): a
stuck client must not stall the fan-out indefinitely.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from src.ws import events as events_module
from src.ws.events import EventBroadcaster


class _YieldingFakeWS:
    """A fake WebSocket that yields to the event loop inside ``send_text``.

    The ``await asyncio.sleep(0)`` forces a genuine suspension point so
    ``asyncio.gather`` interleaves broadcast with connect/disconnect — the
    real concurrency window the P0-013 snapshot-before-iterate hardening
    protects against.
    """

    def __init__(self, *, fail: bool = False, name: str = "ws") -> None:
        self.fail = fail
        self.name = name
        self.sent: list[str] = []
        self.closed_code: int | None = None

    async def accept(self, *, subprotocol: str | None = None) -> None:
        return None

    async def close(self, *, code: int = 1000) -> None:
        self.closed_code = code

    async def send_text(self, payload: str) -> None:
        # Yield so concurrent coroutines (connect/disconnect/other sends) run.
        await asyncio.sleep(0)
        if self.fail:
            raise RuntimeError("dead socket")
        self.sent.append(payload)


class _SlowFakeWS:
    """A fake WebSocket whose ``send_text`` blocks past the send timeout."""

    def __init__(self, *, delay: float = 60.0) -> None:
        self.delay = delay
        self.sent: list[str] = []
        self.closed_code: int | None = None

    async def accept(self, *, subprotocol: str | None = None) -> None:
        return None

    async def close(self, *, code: int = 1000) -> None:
        self.closed_code = code

    async def send_text(self, payload: str) -> None:
        await asyncio.sleep(self.delay)
        self.sent.append(payload)


# ---------------------------------------------------------------------------
# Concurrent broadcast + disconnect / connect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_broadcast_and_disconnect_never_raises() -> None:
    bc = EventBroadcaster()
    ws_alive = _YieldingFakeWS(name="alive")
    ws_dead = _YieldingFakeWS(name="dead")
    await bc.connect(ws_alive)
    await bc.connect(ws_dead)

    # Concurrent broadcast + disconnect must not raise (snapshot hardening).
    await asyncio.gather(
        bc.broadcast({"event": "x"}),
        bc.disconnect(ws_dead),
    )

    assert ws_alive.sent  # alive socket received at least one event
    assert bc.client_count == 1  # strict — exactly the alive client remains


@pytest.mark.asyncio
async def test_connect_during_broadcast_is_safe() -> None:
    bc = EventBroadcaster()
    ws_a = _YieldingFakeWS(name="a")
    ws_b = _YieldingFakeWS(name="b")
    await bc.connect(ws_a)
    await bc.connect(ws_b)
    ws_new = _YieldingFakeWS(name="new")

    # Start a broadcast; the yielding send_text lets connect run mid-fan-out.
    broadcast_task = asyncio.create_task(bc.broadcast({"event": "y"}))
    await asyncio.sleep(0)  # let broadcast enter its loop
    await bc.connect(ws_new)  # mutation during iteration of the snapshot
    await broadcast_task

    # The new client may or may not have received (acceptable per broadcaster
    # semantics — it connected after the snapshot was taken). The invariant is
    # that no exception was raised and the client set is consistent.
    assert bc.client_count == 3
    # The two pre-existing clients definitely received the event.
    assert ws_a.sent and ws_b.sent


@pytest.mark.asyncio
async def test_broadcast_storm_with_churn() -> None:
    bc = EventBroadcaster()
    clients = [_YieldingFakeWS(name=f"c{i}") for i in range(50)]
    for ws in clients:
        await bc.connect(ws)

    # 20 broadcasts interleaved with random disconnects of the first few.
    disconnects = [
        bc.disconnect(clients[i]) for i in range(0, 10)
    ]
    broadcasts = [bc.broadcast({"event": f"e{i}", "i": i}) for i in range(20)]
    # No exception should escape the gather.
    await asyncio.gather(*broadcasts, *disconnects, return_exceptions=False)

    # Every still-connected client received at least one event.
    remaining = clients[10:]
    for ws in remaining:
        assert ws.sent, f"client {ws.name} received no events"
    assert bc.client_count == len(remaining)


@pytest.mark.asyncio
async def test_dead_client_pruned_exactly() -> None:
    bc = EventBroadcaster()
    ws_alive = _YieldingFakeWS(name="alive")
    ws_dead = _YieldingFakeWS(fail=True, name="dead")
    await bc.connect(ws_alive)
    await bc.connect(ws_dead)

    await bc.broadcast({"event": "z"})

    # The dead client raised and was pruned; exactly one remains.
    assert bc.client_count == 1
    assert ws_alive.sent


# ---------------------------------------------------------------------------
# P0-013 — per-send timeout: a stuck client must not stall the fan-out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slow_client_does_not_block_broadcast(monkeypatch) -> None:
    """A stuck/half-open WebSocket is pruned after the send timeout, not held
    indefinitely. The fan-out completes promptly and healthy clients still
    receive the event.
    """
    monkeypatch.setattr(events_module, "_BROADCAST_SEND_TIMEOUT_S", 0.1)
    bc = EventBroadcaster()
    ws_slow = _SlowFakeWS(delay=60.0)
    ws_healthy = _YieldingFakeWS(name="healthy")
    await bc.connect(ws_slow)
    await bc.connect(ws_healthy)

    start = time.monotonic()
    await bc.broadcast({"event": "timeout-test"})
    elapsed = time.monotonic() - start

    # The broadcast returns within a small multiple of the 0.1s timeout, not 60s.
    assert elapsed < 2.0, f"broadcast stalled for {elapsed:.1f}s"
    # The healthy client received the event.
    assert ws_healthy.sent
    # The stuck client was pruned as dead (timed-out send → TimeoutError → dead).
    assert bc.client_count == 1
    assert ws_slow.sent == []  # never actually received (send was cancelled)
