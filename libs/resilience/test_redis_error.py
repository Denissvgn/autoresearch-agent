#!/usr/bin/env python3
"""Test Redis backend error handling directly"""
import asyncio

from resilience.rate_limiter.backends.redis import RedisBackend
from resilience.rate_limiter.core import RateLimitBackend, RateLimitConfig, RateLimitStrategy


async def test_redis_error():
    config = RateLimitConfig(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        rate=10,
        per_seconds=1.0,
        backend=RateLimitBackend.REDIS,
        redis_url="redis://invalid:6379/0",
        strict_mode=False
    )
    
    backend = RedisBackend(config)
    
    try:
        # This should trigger the error
        await backend.get_state("test_key")
        print("Redis operation succeeded unexpectedly")
    except Exception as e:
        print(f"Redis error (expected): {type(e).__name__}: {e}")
        # Check what the actual error is
        print(f"Error type: {type(e)}")
        print(f"Error bases: {type(e).__bases__}")
    
    try:
        await backend.health_check()
        print("Health check succeeded unexpectedly")
    except Exception as e:
        print(f"Health check error (expected): {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_redis_error())