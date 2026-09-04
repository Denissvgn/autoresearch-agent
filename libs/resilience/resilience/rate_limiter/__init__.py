"""
Rate Limiter Shared Library Package

This package provides a comprehensive, production-ready rate limiting solution
for the TRAID platform and other applications.

Key Features:
- Multiple rate limiting strategies (token bucket, sliding window, fixed window)
- Pluggable backends (memory, Redis) with automatic failover
- Exchange-specific configurations for trading platforms
- Comprehensive Prometheus metrics integration
- Easy-to-use decorators and middleware
- Async/await support throughout
- Graceful degradation and error handling
- High performance with sub-millisecond latency

Architecture:
- Strategy Pattern: Pluggable algorithms for different use cases
- Backend Abstraction: Support for local and distributed storage
- Dependency Injection: Configurable components for testability
- Circuit Breaker: Fault tolerance for external dependencies
- Observability: Comprehensive metrics and logging

Usage Examples:

Basic Function Decoration:
```python
from resilience.rate_limiter import rate_limit

@rate_limit(rate=10, per_seconds=1.0)
async def api_call():
    return await some_api()
```

Exchange-Specific Limiting:
```python
@exchange_rate_limit("binance", "orders", rate=10, per_seconds=1.0)
async def place_order():
    return await binance_api.place_order()
```

FastAPI Middleware:
```python
from fastapi import FastAPI
from resilience.rate_limiter import FastAPIRateLimitMiddleware

app = FastAPI()
app.add_middleware(
    FastAPIRateLimitMiddleware,
    rate=100,
    per_seconds=60.0,
    strategy="token_bucket",
    backend="redis"
)
```

Direct Usage:
```python
from resilience.rate_limiter import create_rate_limiter

limiter = create_rate_limiter(
    strategy="sliding_window",
    rate=100,
    per_seconds=60.0,
    backend="memory"
)

result = await limiter.acquire("user:123", 1)
if result.allowed:
    # Process request
    pass
else:
    # Handle rate limit
    await asyncio.sleep(result.retry_after)
```

Configuration Examples:

Memory Backend (Single Instance):
```python
config = {
    "strategy": "token_bucket",
    "rate": 100,
    "per_seconds": 60.0,
    "burst": 150,
    "backend": "memory"
}
```

Redis Backend (Distributed):
```python
config = {
    "strategy": "sliding_window", 
    "rate": 1000,
    "per_seconds": 60.0,
    "backend": "redis",
    "redis_url": "redis://localhost:6379/0"
}
```

Exchange-Specific:
```python
# Automatically uses Binance-specific limits
limiter = create_exchange_rate_limiter("binance", "orders")
```

Performance Characteristics:
- Memory Backend: Sub-millisecond latency, high throughput
- Redis Backend: 1-5ms latency, distributed coordination
- Token Bucket: Best for bursty traffic patterns
- Sliding Window: Precise rate limiting, higher memory usage
- Fixed Window: Most efficient, potential boundary effects

Production Deployment:
- Use Redis backend for multi-instance deployments
- Configure appropriate timeouts and retries
- Monitor metrics for capacity planning
- Set up alerts on rate limit violations
- Use circuit breaker for external service dependencies

Integration Patterns:
- Service-level: Use middleware for HTTP request limiting
- Function-level: Use decorators for business logic limiting
- Custom: Use RateLimiter class directly for complex scenarios
- Multi-tier: Combine different strategies for different layers

Error Handling:
- Graceful degradation when backends are unavailable
- Configurable modes: block, reject, or log-only
- Comprehensive error context for debugging
- Circuit breaker prevents cascade failures

Metrics and Observability:
- Request rates and response times
- Backend performance and health
- Error rates and types
- Memory usage and cleanup efficiency
- Circuit breaker state transitions

Testing Support:
- Mock backends for unit testing
- Time manipulation for scenario testing
- Load testing utilities
- Performance benchmarking tools
"""

# Backend implementations (for advanced usage)
from .backends.memory import MemoryBackend
from .backends.redis import RedisBackend
from .core import (  # Core classes and functions; Exceptions; Factory functions
    RateLimitBackend,
    RateLimitConfig,
    RateLimiter,
    RateLimitExceededError,
    RateLimitResult,
    RateLimitStrategy,
    create_exchange_rate_limiter,
    create_rate_limiter,
)
from .decorators import (  # Middleware; Configuration enums; Decorators
    FastAPIRateLimitMiddleware,
    FlaskRateLimitMiddleware,
    KeyGenerationStrategy,
    RateLimitMode,
    exchange_rate_limit,
    rate_limit,
)
from .metrics import PrometheusMetricsCollector, get_metrics_collector  # Metrics
from .strategies.sliding_window import FixedWindowStrategy, SlidingWindowStrategy

# Strategy implementations (for advanced usage)
from .strategies.token_bucket import TokenBucketStrategy

# Version information
__version__ = "1.0.0"
__author__ = "TRAID Platform Team"
__description__ = "Production-ready rate limiting library with multiple strategies and backends"

# Public API
__all__ = [
    # Core API
    "RateLimiter",
    "RateLimitConfig", 
    "RateLimitResult",
    "RateLimitStrategy",
    "RateLimitBackend",
    
    # Exceptions
    "RateLimitExceededError",
    
    # Factory functions
    "create_rate_limiter",
    "create_exchange_rate_limiter",
    
    # Decorators and middleware
    "rate_limit",
    "exchange_rate_limit",
    "FastAPIRateLimitMiddleware",
    "FlaskRateLimitMiddleware",
    "KeyGenerationStrategy",
    "RateLimitMode",
    
    # Metrics
    "get_metrics_collector",
    "PrometheusMetricsCollector",
    
    # Advanced usage
    "TokenBucketStrategy",
    "SlidingWindowStrategy", 
    "FixedWindowStrategy",
    "MemoryBackend",
    "RedisBackend",
]

# Configuration shortcuts for common patterns
FAST_LIMITING = {
    "strategy": RateLimitStrategy.TOKEN_BUCKET,
    "rate": 10,
    "per_seconds": 1.0,
    "backend": RateLimitBackend.MEMORY
}

MODERATE_LIMITING = {
    "strategy": RateLimitStrategy.SLIDING_WINDOW,
    "rate": 100,
    "per_seconds": 60.0,
    "backend": RateLimitBackend.MEMORY
}

DISTRIBUTED_LIMITING = {
    "strategy": RateLimitStrategy.SLIDING_WINDOW,
    "rate": 1000,
    "per_seconds": 60.0,
    "backend": RateLimitBackend.REDIS
}

# Common decorator configurations
def fast_rate_limit(**kwargs):
    """Fast rate limiting with sensible defaults."""
    config = FAST_LIMITING.copy()
    config.update(kwargs)
    return rate_limit(**config)

def moderate_rate_limit(**kwargs):
    """Moderate rate limiting with sensible defaults."""
    config = MODERATE_LIMITING.copy()
    config.update(kwargs)
    return rate_limit(**config)

def distributed_rate_limit(**kwargs):
    """Distributed rate limiting with sensible defaults."""
    config = DISTRIBUTED_LIMITING.copy()
    config.update(kwargs)
    return rate_limit(**config)