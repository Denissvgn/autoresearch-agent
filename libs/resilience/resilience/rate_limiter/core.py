"""
TRAID Platform - Shared Rate Limiter Library

This module provides a flexible, high-performance rate limiting implementation
that can be shared across all TRAID platform services.

Key Features:
- Multiple rate limiting strategies (token bucket, sliding window, fixed window)
- Pluggable storage backends (memory, Redis)
- Exchange-specific configuration support
- Prometheus metrics integration
- Async/await support with thread-safe synchronous variants
- Dependency injection for testability
- Graceful degradation and error handling

Design Principles:
- Strategy Pattern: Pluggable rate limiting algorithms
- Backend Abstraction: Storage-agnostic implementation
- Performance: Sub-millisecond latency for memory backend
- Observability: Comprehensive metrics and logging
- Resilience: Graceful degradation when dependencies fail
- Compatibility: Drop-in replacement for existing implementations
"""
from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from enum import Enum
import logging
import time
from typing import Any, Callable, Dict, Optional, Protocol

logger = logging.getLogger(__name__)

# Module-level set to prevent garbage collection of fire-and-forget tasks
# Tasks are removed from the set when they complete via a done callback
_background_tasks: set[asyncio.Task[None]] = set()


class RateLimitStrategy(str, Enum):
    """Available rate limiting strategies."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


class RateLimitBackend(str, Enum):
    """Available storage backends."""
    MEMORY = "memory"
    REDIS = "redis"


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for rate limiting behavior."""
    
    # Basic rate limiting parameters
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    rate: int = 10  # requests allowed
    per_seconds: float = 1.0  # time window
    burst: Optional[int] = None  # max burst capacity (defaults to rate)
    
    # Backend configuration
    backend: RateLimitBackend = RateLimitBackend.MEMORY
    redis_url: Optional[str] = None
    redis_key_prefix: str = "rate_limit"
    redis_pool_size: int = 10
    redis_socket_timeout: float = 1.0
    
    # Advanced options
    strict_mode: bool = False  # Fail fast vs graceful degradation
    cleanup_interval: float = 300.0  # Clean up old data every 5 minutes
    max_wait_time: float = 60.0  # Maximum time to wait for tokens
    
    # Exchange-specific settings (for backwards compatibility)
    exchange: Optional[str] = None
    endpoint_type: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.rate <= 0:
            raise ValueError("Rate must be positive")
        if self.per_seconds <= 0:
            raise ValueError("Time window must be positive")
        if self.burst is not None and self.burst < self.rate:
            raise ValueError("Burst capacity cannot be less than rate")
        if self.redis_pool_size <= 0:
            raise ValueError("Redis pool size must be positive")
        if self.max_wait_time < 0:
            raise ValueError("Max wait time cannot be negative")
    
    @property
    def effective_burst(self) -> int:
        """Get the effective burst capacity."""
        return self.burst or self.rate
    
    @property
    def key_prefix(self) -> str:
        """Generate a key prefix for this rate limiter configuration."""
        parts = [self.redis_key_prefix]
        if self.exchange:
            parts.append(self.exchange)
        if self.endpoint_type:
            parts.append(self.endpoint_type)
        return ":".join(parts)


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    
    allowed: bool  # Whether the request was allowed
    remaining: int  # Remaining capacity
    reset_time: float  # When the rate limit resets (Unix timestamp)
    retry_after: Optional[float] = None  # Seconds to wait before retry
    waited: float = 0.0  # Time spent waiting (for blocking calls)
    
    # Metadata for observability
    strategy_used: str = ""
    backend_used: str = ""
    cache_hit: bool = False


class MetricsCollector(Protocol):
    """Protocol for collecting rate limiter metrics."""
    
    def record_request(
        self, 
        key: str, 
        allowed: bool, 
        remaining: int, 
        wait_time: float = 0.0,
        **labels: Any
    ) -> None:
        """Record a rate limit request."""
        ...
    
    def record_backend_operation(
        self, 
        backend: str, 
        operation: str, 
        duration: float, 
        success: bool
    ) -> None:
        """Record backend operation metrics."""
        ...


class RateLimitError(Exception):
    """Base exception for rate limiting errors."""
    pass


class RateLimitExceededError(RateLimitError):
    """Raised when rate limit is exceeded in strict mode."""
    
    def __init__(self, result: RateLimitResult):
        self.result = result
        super().__init__(f"Rate limit exceeded. Retry after {result.retry_after} seconds")


class BackendError(RateLimitError):
    """Raised when backend operations fail in strict mode."""
    pass


# Storage backend interface
class StorageBackend(ABC):
    """Abstract interface for rate limiter storage backends."""
    
    @abstractmethod
    async def get_state(self, key: str) -> Dict[str, Any]:
        """
        Get current state for a rate limit key.
        
        Returns:
            Dictionary containing state data specific to the strategy
        """
        ...
    
    @abstractmethod
    async def set_state(self, key: str, state: Dict[str, Any], ttl: Optional[float] = None) -> None:
        """
        Set state for a rate limit key.
        
        Args:
            key: The rate limit key
            state: State data to store
            ttl: Time to live in seconds (None for no expiration)
        """
        ...
    
    @abstractmethod
    async def atomic_update(
        self, 
        key: str, 
        update_func: Callable[[Dict[str, Any]], Dict[str, Any]], 
        ttl: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Atomically update state using a function.
        
        Args:
            key: The rate limit key
            update_func: Function that takes current state and returns new state
            ttl: Time to live in seconds
            
        Returns:
            New state after update
        """
        ...
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up backend resources."""
        ...
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if backend is healthy."""
        ...


# Rate limiting strategy interface
class RateLimitStrategyImpl(ABC):
    """Abstract interface for rate limiting strategies."""
    
    def __init__(self, config: RateLimitConfig, backend: StorageBackend):
        self.config = config
        self.backend = backend
    
    @abstractmethod
    async def check_rate_limit(self, key: str, tokens: int = 1) -> RateLimitResult:
        """
        Check if request is allowed under rate limit.
        
        Args:
            key: Unique identifier for the rate limit bucket
            tokens: Number of tokens to consume
            
        Returns:
            RateLimitResult indicating if request is allowed
        """
        ...
    
    @abstractmethod
    async def reset_rate_limit(self, key: str) -> None:
        """Reset rate limit state for a key."""
        ...
    
    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Get strategy information for debugging."""
        ...


class RateLimiter:
    """
    Main rate limiter class that coordinates strategy and backend.
    
    This is the primary interface that services will interact with.
    It provides both blocking and non-blocking variants of rate limiting.
    """
    
    def __init__(
        self,
        config: RateLimitConfig,
        backend: Optional[StorageBackend] = None,
        strategy: Optional[RateLimitStrategyImpl] = None,
        metrics_collector: Optional[MetricsCollector] = None
    ):
        self.config = config
        self._backend = backend
        self._strategy = strategy
        self._metrics_collector = metrics_collector
        self._shutdown = False
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Start cleanup task if configured
        if config.cleanup_interval > 0:
            self._start_cleanup_task()
    
    @property
    def backend(self) -> StorageBackend:
        """Get or create the storage backend."""
        if self._backend is None:
            self._backend = self._create_backend()
        return self._backend
    
    @property 
    def strategy(self) -> RateLimitStrategyImpl:
        """Get or create the rate limiting strategy."""
        if self._strategy is None:
            self._strategy = self._create_strategy()
        return self._strategy
    
    def _create_backend(self) -> StorageBackend:
        """Create appropriate backend based on configuration."""
        if self.config.backend == RateLimitBackend.REDIS:
            from .backends.redis import RedisBackend
            if not self.config.redis_url:
                raise ValueError("Redis URL required for Redis backend")
            return RedisBackend(self.config)
        else:
            from .backends.memory import MemoryBackend
            return MemoryBackend(self.config)
    
    def _create_strategy(self) -> RateLimitStrategyImpl:
        """Create appropriate strategy based on configuration."""
        if self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            from .strategies.sliding_window import SlidingWindowStrategy
            return SlidingWindowStrategy(self.config, self.backend)
        elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
            from .strategies.sliding_window import FixedWindowStrategy
            return FixedWindowStrategy(self.config, self.backend)
        else:
            from .strategies.token_bucket import TokenBucketStrategy
            return TokenBucketStrategy(self.config, self.backend)
    
    async def acquire(self, key: str = "default", tokens: int = 1) -> RateLimitResult:
        """
        Try to acquire tokens immediately (non-blocking).
        
        Args:
            key: Unique identifier for the rate limit bucket
            tokens: Number of tokens to request
            
        Returns:
            RateLimitResult with the outcome
        """
        start_time = time.monotonic()
        
        try:
            result = await self.strategy.check_rate_limit(key, tokens)
            
            # Collect metrics
            if self._metrics_collector:
                duration = time.monotonic() - start_time
                self._metrics_collector.record_request(
                    key=key,
                    allowed=result.allowed,
                    remaining=result.remaining,
                    wait_time=duration,
                    strategy=self.config.strategy.value,
                    backend=self.config.backend.value,
                    exchange=self.config.exchange,
                    endpoint_type=self.config.endpoint_type
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Rate limiter error for key {key}: {e}")
            
            if self.config.strict_mode:
                raise BackendError(f"Rate limiter backend error: {e}") from e
            
            # Graceful degradation - allow request but log error
            return RateLimitResult(
                allowed=True,
                remaining=self.config.effective_burst,
                reset_time=time.time() + self.config.per_seconds,
                strategy_used=self.config.strategy.value,
                backend_used=self.config.backend.value
            )
    
    async def acquire_blocking(
        self, 
        key: str = "default", 
        tokens: int = 1
    ) -> RateLimitResult:
        """
        Acquire tokens, waiting if necessary (blocking).
        
        Uses config.max_wait_time as the timeout. If you need a different timeout,
        wrap this call with asyncio.timeout() context manager.
        
        Args:
            key: Unique identifier for the rate limit bucket
            tokens: Number of tokens to request
            
        Returns:
            RateLimitResult with the outcome
            
        Raises:
            RateLimitExceededError: If timeout is exceeded (in strict mode)
            TimeoutError: If max_wait_time is exceeded (in non-strict mode)
        """
        start_time = time.monotonic()
        
        try:
            async with asyncio.timeout(self.config.max_wait_time):
                while True:
                    result = await self.acquire(key, tokens)
                    
                    if result.allowed:
                        result.waited = time.monotonic() - start_time
                        return result
                    
                    if not result.retry_after:
                        # No retry guidance, return current result to avoid infinite loop
                        result.waited = time.monotonic() - start_time
                        return result
                    
                    await asyncio.sleep(result.retry_after)
                    
        except TimeoutError:
            # Timeout exceeded - do one final attempt
            final_result = await self.acquire(key, tokens)
            final_result.waited = time.monotonic() - start_time
            
            if self.config.strict_mode and not final_result.allowed:
                raise RateLimitExceededError(final_result)
            
            return final_result
    
    async def reset(self, key: str) -> None:
        """Reset rate limit state for a specific key."""
        await self.strategy.reset_rate_limit(key)
    
    async def get_status(self, key: str) -> Dict[str, Any]:
        """Get current status for a rate limit key."""
        result = await self.acquire(key, 0)  # Check without consuming tokens
        return {
            "key": key,
            "remaining": result.remaining,
            "reset_time": result.reset_time,
            "strategy": result.strategy_used,
            "backend": result.backend_used,
            "config": {
                "rate": self.config.rate,
                "per_seconds": self.config.per_seconds,
                "burst": self.config.effective_burst
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of rate limiter and its dependencies."""
        health = {
            "rate_limiter": "healthy",
            "backend": "unknown",
            "strategy": self.config.strategy.value,
            "config_valid": True
        }
        
        try:
            backend_healthy = await self.backend.health_check()
            health["backend"] = "healthy" if backend_healthy else "unhealthy"
        except Exception as e:
            health["backend"] = f"error: {e}"
            health["rate_limiter"] = "degraded"
        
        return health
    
    def _start_cleanup_task(self) -> None:
        """Start background cleanup task.
        
        This method gracefully handles the case where no event loop is running
        (e.g., when decorating sync functions at module load time). In such cases,
        cleanup will be deferred until the first async acquire operation.
        """
        async def cleanup_loop():
            while not self._shutdown:
                try:
                    await asyncio.sleep(self.config.cleanup_interval)
                    if not self._shutdown:
                        # Trigger backend cleanup
                        await self.backend.cleanup()
                except asyncio.CancelledError:
                    # Expected during shutdown - re-raise to properly terminate
                    raise
                except Exception as e:
                    logger.error(f"Cleanup task error: {e}")
        
        try:
            # Only create task if there's a running event loop
            asyncio.get_running_loop()
            self._cleanup_task = asyncio.create_task(cleanup_loop())
        except RuntimeError:
            # No running event loop - this is normal when decorating sync functions
            # at module load time. Cleanup task will be started lazily on first
            # async acquire if needed, or cleanup can be triggered manually.
            self._cleanup_task = None
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the rate limiter.
        
        This method properly handles cancellation - if shutdown() itself is
        cancelled externally, the CancelledError will propagate after cleanup.
        """
        self._shutdown = True
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            # Use gather with return_exceptions=True to:
            # 1. Handle expected CancelledError from our cancel() call
            # 2. Propagate external CancelledError if shutdown() is cancelled
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
        
        if self._backend:
            await self._backend.cleanup()
    
    def __del__(self) -> None:
        """Cleanup on deletion."""
        try:
            # Only attempt cleanup if there's an active event loop
            if not self._shutdown:
                loop = asyncio.get_running_loop()
                if loop and not loop.is_closed():
                    task = asyncio.create_task(self.shutdown())
                    # Prevent garbage collection by adding to module-level set
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)
        except RuntimeError:
            # No event loop running - this is normal during interpreter shutdown
            # Just mark as shutdown to prevent further cleanup attempts
            self._shutdown = True


# Factory functions for common use cases
def create_rate_limiter(
    strategy: str = "token_bucket",
    rate: int = 10,
    per_seconds: float = 1.0,
    burst: Optional[int] = None,
    backend: str = "memory",
    **kwargs
) -> RateLimiter:
    """Create a rate limiter with common configuration patterns."""
    config = RateLimitConfig(
        strategy=RateLimitStrategy(strategy),
        rate=rate,
        per_seconds=per_seconds,
        burst=burst,
        backend=RateLimitBackend(backend),
        **kwargs
    )
    return RateLimiter(config)


def create_exchange_rate_limiter(
    exchange: str,
    endpoint_type: str = "requests",
    **kwargs
) -> RateLimiter:
    """Create a rate limiter configured for a specific exchange endpoint."""
    # Exchange-specific defaults (can be overridden)
    exchange_defaults = {
        "binance": {"rate": 20, "burst": 40},
        "okx": {"rate": 30, "burst": 60}, 
        "kraken": {"rate": 10, "burst": 20},
        "coinbase": {"rate": 10, "burst": 20},
        "poloniex": {"rate": 10, "burst": 20}
    }
    
    defaults = exchange_defaults.get(exchange.lower(), {"rate": 10, "burst": 20})
    config_params = {**defaults, **kwargs}
    
    # Convert string strategy/backend to enum if needed
    if "strategy" in config_params and isinstance(config_params["strategy"], str):
        config_params["strategy"] = RateLimitStrategy(config_params["strategy"])
    if "backend" in config_params and isinstance(config_params["backend"], str):
        config_params["backend"] = RateLimitBackend(config_params["backend"])
    
    config = RateLimitConfig(
        exchange=exchange,
        endpoint_type=endpoint_type,
        **config_params
    )
    return RateLimiter(config)