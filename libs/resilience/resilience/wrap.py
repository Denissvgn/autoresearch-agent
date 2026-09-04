from __future__ import annotations

import asyncio
from functools import wraps
from typing import Awaitable, Callable, ParamSpec, TypeVar

from .backoff import retry as _retry
from .breaker import CircuitBreaker

P = ParamSpec("P")
T = TypeVar("T")


def with_retry(*, attempts: int = 3, base_delay: float = 0.2, max_delay: float = 5.0, operation: str = "default") -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            async def call() -> T:
                return await fn(*args, **kwargs)
            return await _retry(call, attempts=attempts, base_delay=base_delay, max_delay=max_delay, operation=operation)
        return wrapper
    return decorator


def with_circuit_breaker(fn: Callable[P, Awaitable[T]], breaker: CircuitBreaker) -> Callable[P, Awaitable[T]]:
    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        async def call() -> T:
            return await fn(*args, **kwargs)
        return await breaker.call(call)
    return wrapper


def with_timeout(*, timeout: float) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await asyncio.wait_for(fn(*args, **kwargs), timeout=timeout)
        return wrapper
    return decorator

