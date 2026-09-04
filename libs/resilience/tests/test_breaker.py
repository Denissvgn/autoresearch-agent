import asyncio

import pytest

from resilience import CircuitBreaker, CircuitOpenError

pytestmark = pytest.mark.asyncio


async def test_breaker_transitions():
    br = CircuitBreaker(failure_threshold=2, reset_timeout=0.01, operation="test")

    async def fail():
        raise ValueError("x")

    # Two failures from closed -> open
    with pytest.raises(ValueError):
        await br.call(fail)
    with pytest.raises(ValueError):
        await br.call(fail)
    assert br.state == "open"

    # While open before timeout -> CircuitOpenError
    with pytest.raises(CircuitOpenError):
        await br.call(fail)

    # Wait for half-open transition
    await asyncio.sleep(0.02)
    # Now call fails from half-open back to open
    with pytest.raises(ValueError):
        await br.call(fail)
    assert br.state == "open"


async def test_breaker_success_resets():
    br = CircuitBreaker(failure_threshold=1, reset_timeout=0.01)

    async def ok():
        return 1

    async def fail():
        raise RuntimeError("b")

    # One fail opens
    with pytest.raises(RuntimeError):
        await br.call(fail)
    assert br.state == "open"
    await asyncio.sleep(0.02)
    # Success from half-open closes
    assert await br.call(ok) == 1
    assert br.state == "closed"

