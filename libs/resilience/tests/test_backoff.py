import pytest

from resilience import RetryError, retry

pytestmark = pytest.mark.asyncio


async def test_retry_succeeds_within_attempts():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("boom")
        return 42

    result = await retry(flaky, attempts=5, base_delay=0.0, max_delay=0.0)
    assert result == 42
    assert calls["n"] == 3


async def test_retry_raises_after_attempts():
    async def always_fail():
        raise RuntimeError("nope")

    with pytest.raises(RetryError):
        await retry(always_fail, attempts=2, base_delay=0.0, max_delay=0.0)

