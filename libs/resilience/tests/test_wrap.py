import pytest

from resilience import CircuitBreaker, with_circuit_breaker, with_retry
from resilience.wrap import with_timeout

pytestmark = pytest.mark.asyncio


async def test_with_retry_decorator():
    calls = {"n": 0}

    @with_retry(attempts=3, base_delay=0.0, max_delay=0.0)
    async def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ValueError
        return "ok"

    assert await fn() == "ok"
    assert calls["n"] == 2


async def test_with_circuit_breaker_decorator():
    br = CircuitBreaker(failure_threshold=1, reset_timeout=0.0)

    async def ok():
        return 1

    ok_wrapped = with_circuit_breaker(ok, br)
    assert await ok_wrapped() == 1


async def test_with_timeout_decorator():
    @with_timeout(timeout=0.01)
    async def slow():
        await asyncio.sleep(0.05)
        return 1
    with pytest.raises(Exception):
        await slow()

