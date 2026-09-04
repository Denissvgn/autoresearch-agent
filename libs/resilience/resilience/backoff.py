from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable, Optional, TypeVar

from .exceptions import RetryError
from .metrics import resilience_retry_attempts_total, resilience_retry_failures_total

T = TypeVar("T")


async def retry(
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.2,
    max_delay: float = 5.0,
    operation: str = "default",
    retry_predicate: Optional[Callable[[Exception], bool]] = None,
) -> T:
    """
    Retry an async function with exponential backoff and full jitter.

    - attempts includes the final attempt
    - full jitter: random.uniform(0, min(max_delay, base * 2**n))
    - retry_predicate can filter which exceptions are retried (default: all)
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    last_exc: Optional[Exception] = None
    for i in range(attempts):
        try:
            resilience_retry_attempts_total.labels(operation=operation).inc()
            return await func()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if retry_predicate and not retry_predicate(e):
                break
            if i == attempts - 1:
                break
            delay = random.uniform(0, min(max_delay, base_delay * (2 ** i)))
            await asyncio.sleep(delay)
    resilience_retry_failures_total.labels(operation=operation).inc()
    assert last_exc is not None
    raise RetryError(str(last_exc)) from last_exc

