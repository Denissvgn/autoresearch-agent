#!/usr/bin/env python3
"""
Task 13 validation test - focused on the implemented components
"""
import asyncio
import time

import pytest

from resilience.rate_limiter.core import (
    RateLimitBackend,
    RateLimitConfig,
    RateLimitStrategy,
    create_rate_limiter,
)


class TestTask13RedisFailover:
    """Test Redis backend failover scenarios (Task 13 implementation)."""
    
    @pytest.fixture
    async def redis_limiter_graceful(self):
        """Redis rate limiter with graceful mode."""
        RateLimitConfig(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            rate=10,
            per_seconds=1.0,
            burst=15,
            backend=RateLimitBackend.REDIS,
            redis_url="redis://invalid:6379/0",  # Invalid to trigger failover
            strict_mode=False  # Graceful degradation
        )
        limiter = create_rate_limiter(
            strategy="token_bucket",
            rate=10,
            per_seconds=1.0,
            burst=15,
            backend="redis",
            redis_url="redis://invalid:6379/0",
            strict_mode=False
        )
        yield limiter
        await limiter.shutdown()
    
    async def test_redis_connection_failure_graceful_mode(self, redis_limiter_graceful):
        """Test Redis connection failure with graceful degradation (Task 13)."""
        # Should fallback to allowing requests when Redis is unavailable
        result = await redis_limiter_graceful.acquire("test_key", 1)
        
        # In graceful mode, should allow requests when Redis is down
        assert result.allowed is True
        assert result.backend_used == "redis"  # Still reports Redis backend
        
        # Multiple requests should still work in graceful mode
        for i in range(5):
            result = await redis_limiter_graceful.acquire(f"test_key_{i}", 1)
            assert result.allowed is True
    
    async def test_performance_benchmark_memory(self):
        """Test memory backend performance benchmark (Task 13)."""
        limiter = create_rate_limiter(
            strategy="token_bucket",
            rate=10000,  # High rate for performance testing
            per_seconds=1.0,
            backend="memory"
        )
        
        # Performance test - measure throughput
        start_time = time.time()
        successful_requests = 0
        
        for i in range(1000):
            result = await limiter.acquire(f"perf_test_{i % 100}", 1)
            if result.allowed:
                successful_requests += 1
        
        elapsed = time.time() - start_time
        throughput = successful_requests / elapsed
        
        # Should handle at least 1000 requests/second
        assert throughput > 1000, f"Throughput {throughput:.2f} req/s too low"
        
        await limiter.shutdown()
    
    async def test_metrics_validation(self):
        """Test metrics accuracy validation (Task 13)."""
        limiter = create_rate_limiter(
            strategy="token_bucket",
            rate=5,
            per_seconds=1.0,
            burst=5,
            backend="memory"
        )
        
        key = "metrics_test"
        
        # Use all tokens
        for i in range(5):
            result = await limiter.acquire(key, 1)
            assert result.allowed is True
            assert result.remaining == 4 - i  # Decreasing remaining
        
        # Next request should fail
        result = await limiter.acquire(key, 1)
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after is not None
        assert result.retry_after > 0
        
        await limiter.shutdown()
    
    async def test_concurrent_requests(self):
        """Test concurrent request handling (Task 13)."""
        limiter = create_rate_limiter(
            strategy="token_bucket",
            rate=100,
            per_seconds=1.0,
            burst=200,
            backend="memory"
        )
        
        async def worker(worker_id: int):
            results = []
            for _i in range(10):
                result = await limiter.acquire(f"worker_{worker_id}", 1)
                results.append(result.allowed)
            return results
        
        # Run 10 workers concurrently
        tasks = [worker(i) for i in range(10)]
        all_results = await asyncio.gather(*tasks)
        
        # Count successful requests
        total_allowed = sum(sum(results) for results in all_results)
        
        # Should handle most requests successfully
        assert total_allowed >= 80, f"Only {total_allowed}/100 requests succeeded"
        
        await limiter.shutdown()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])