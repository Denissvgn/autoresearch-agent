"""
Decorators and Middleware for Rate Limiting Integration

This module provides easy-to-use decorators and middleware for integrating
rate limiting into existing applications with minimal code changes.

Key Features:
- Function decorators for sync and async functions
- FastAPI middleware integration
- Flask middleware integration
- Configurable rate limiting with sensible defaults
- Automatic key generation based on function parameters
- Graceful error handling and fallback behavior

Design Principles:
- Minimal code changes required for integration
- Flexible configuration options
- Transparent operation (doesn't change function signatures)
- Comprehensive error handling
- Performance optimized for common use cases
"""
import asyncio
from dataclasses import dataclass
from enum import Enum
import functools
import hashlib
import inspect
import logging
import time
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional, TypeVar, Union, cast, overload

from .core import (
    RateLimitBackend,
    RateLimitExceededError,
    RateLimitStrategy,
    create_exchange_rate_limiter,
    create_rate_limiter,
)
from .metrics import get_metrics_collector

# Type variables for generic decorators
F = TypeVar('F', bound=Callable[..., Any])
AsyncF = TypeVar('AsyncF', bound=Callable[..., Awaitable[Any]])
SyncF = TypeVar('SyncF', bound=Callable[..., Any])


class KeyGenerationStrategy(str, Enum):
    """Strategies for generating rate limit keys."""
    GLOBAL = "global"  # Same key for all calls
    PER_FUNCTION = "per_function"  # One key per decorated function
    PER_USER = "per_user"  # Extract user ID from arguments
    PER_IP = "per_ip"  # Extract IP address from request
    PER_ARGS = "per_args"  # Hash function arguments
    CUSTOM = "custom"  # Use custom key function


class RateLimitMode(str, Enum):
    """Rate limiting enforcement modes."""
    BLOCK = "block"  # Block and wait for tokens
    REJECT = "reject"  # Immediately reject if no tokens
    LOG_ONLY = "log_only"  # Only log, don't enforce


def _generate_function_key(func: Callable, args: tuple, kwargs: dict, strategy: KeyGenerationStrategy) -> str:
    """
    Generate a rate limit key based on function and arguments.
    
    Args:
        func: The decorated function
        args: Function positional arguments
        kwargs: Function keyword arguments
        strategy: Key generation strategy
        
    Returns:
        Generated rate limit key
    """
    if strategy == KeyGenerationStrategy.GLOBAL:
        return "global"
    
    elif strategy == KeyGenerationStrategy.PER_FUNCTION:
        return f"func:{func.__module__}.{func.__qualname__}"
    
    elif strategy == KeyGenerationStrategy.PER_USER:
        # Try to extract user ID from common parameter names
        user_params = ["user_id", "user", "username", "uid", "account_id"]
        
        # Check kwargs first
        for param in user_params:
            if param in kwargs:
                return f"user:{kwargs[param]}"
        
        # Check if first argument looks like a user ID
        if args and isinstance(args[0], (str, int)):
            return f"user:{args[0]}"
        
        # Fallback to function-level limiting
        return f"func:{func.__module__}.{func.__qualname__}"
    
    elif strategy == KeyGenerationStrategy.PER_ARGS:
        # Create hash of arguments for deterministic key
        arg_str = str(args) + str(sorted(kwargs.items()))
        arg_hash = hashlib.md5(arg_str.encode()).hexdigest()[:12]
        return f"func:{func.__module__}.{func.__qualname__}:args:{arg_hash}"
    
    else:  # PER_FUNCTION as fallback
        return f"func:{func.__module__}.{func.__qualname__}"


def _extract_ip_from_request(request: Any) -> Optional[str]:
    """
    Extract IP address from request object.
    
    Supports FastAPI Request, Flask request, and other common patterns.
    """
    try:
        # FastAPI Request
        if hasattr(request, 'client') and hasattr(request.client, 'host'):
            return request.client.host
        
        # Flask request or similar
        if hasattr(request, 'remote_addr'):
            return request.remote_addr
        
        # Django request
        if hasattr(request, 'META'):
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            if forwarded:
                return forwarded.split(',')[0].strip()
            return request.META.get('REMOTE_ADDR')
        
        # Check for forwarded headers in other request types
        if hasattr(request, 'headers'):
            forwarded = request.headers.get('X-Forwarded-For')
            if forwarded:
                return forwarded.split(',')[0].strip()
            return request.headers.get('X-Real-IP')
        
    except Exception:
        pass
    
    return None


# Constant for fallback IP key
_UNKNOWN_IP_KEY = "ip:unknown"


@dataclass
class _RateLimitDecoratorConfig:
    """Configuration parameters for rate limit decorator."""
    rate: int = 10
    per_seconds: float = 1.0
    burst: Optional[int] = None
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    backend: RateLimitBackend = RateLimitBackend.MEMORY
    key_strategy: KeyGenerationStrategy = KeyGenerationStrategy.PER_FUNCTION
    key_func: Optional[Callable] = None
    mode: RateLimitMode = RateLimitMode.BLOCK
    timeout: Optional[float] = None
    redis_url: Optional[str] = None
    service_name: Optional[str] = None
    exchange: Optional[str] = None
    endpoint_type: Optional[str] = None
    on_limit_exceeded: Optional[Callable] = None


@dataclass
class _RateLimitContext:
    """Internal context for rate limit decorator execution."""
    limiter: Any
    metrics: Any
    key_strategy: KeyGenerationStrategy
    rate_mode: RateLimitMode
    timeout: Optional[float]
    exchange: Optional[str]
    endpoint_type: Optional[str]
    on_limit_exceeded: Optional[Callable]
    config_params: dict
    key_func: Optional[Callable]


def _resolve_rate_limit_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    ctx: _RateLimitContext
) -> str:
    """Resolve the rate limit key using custom function or strategy."""
    if ctx.key_func:
        return ctx.key_func(func, args, kwargs)
    return _generate_function_key(func, args, kwargs, ctx.key_strategy)


def _record_rate_limit_metrics(
    ctx: _RateLimitContext,
    key: str,
    result: Any,
    duration: float
) -> None:
    """Record rate limiting metrics if collector is available."""
    if not ctx.metrics:
        return
    ctx.metrics.record_request(
        key=key,
        allowed=result.allowed,
        remaining=result.remaining,
        wait_time=result.waited,
        duration=duration,
        strategy=ctx.config_params["strategy"].value,
        backend=ctx.config_params["backend"].value,
        exchange=ctx.exchange,
        endpoint_type=ctx.endpoint_type
    )


async def _acquire_rate_limit_async(
    ctx: _RateLimitContext,
    key: str
) -> Any:
    """Acquire rate limit token asynchronously with optional timeout."""
    if ctx.rate_mode != RateLimitMode.BLOCK:
        return await ctx.limiter.acquire(key, 1)
    
    if ctx.timeout is not None:
        async with asyncio.timeout(ctx.timeout):
            return await ctx.limiter.acquire_blocking(key, 1)
    return await ctx.limiter.acquire_blocking(key, 1)


def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get existing event loop or create a new one for sync context.
    
    Uses the recommended pattern for Python 3.10+ where get_event_loop()
    in a non-async context is deprecated.
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - create a new one for sync execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def _acquire_rate_limit_sync(
    ctx: _RateLimitContext,
    key: str
) -> Any:
    """Acquire rate limit token synchronously."""
    loop = _get_or_create_event_loop()
    
    if ctx.rate_mode != RateLimitMode.BLOCK:
        return loop.run_until_complete(ctx.limiter.acquire(key, 1))
    
    async def _acquire_with_timeout():
        if ctx.timeout is not None:
            async with asyncio.timeout(ctx.timeout):
                return await ctx.limiter.acquire_blocking(key, 1)
        return await ctx.limiter.acquire_blocking(key, 1)
    
    return loop.run_until_complete(_acquire_with_timeout())


async def _handle_limit_exceeded_async(
    ctx: _RateLimitContext,
    func: Callable,
    args: tuple,
    kwargs: dict,
    result: Any
) -> Any:
    """Handle rate limit exceeded for async functions."""
    if ctx.on_limit_exceeded:
        return await ctx.on_limit_exceeded(func, args, kwargs, result)
    raise RateLimitExceededError(result)


def _handle_limit_exceeded_sync(
    ctx: _RateLimitContext,
    func: Callable,
    args: tuple,
    kwargs: dict,
    result: Any
) -> Any:
    """Handle rate limit exceeded for sync functions."""
    if ctx.on_limit_exceeded:
        return ctx.on_limit_exceeded(func, args, kwargs, result)
    raise RateLimitExceededError(result)


def _handle_rate_limit_error(
    error: Exception,
    func: Callable,
    rate_mode: RateLimitMode
) -> bool:
    """Handle rate limiting errors. Returns True if original function should be called."""
    if isinstance(error, RateLimitExceededError):
        raise error
    
    logging.error(f"Rate limiting error in {func.__name__}: {error}")
    
    if rate_mode != RateLimitMode.LOG_ONLY:
        raise error
    
    return True


def _parse_enum_value(value: Any, enum_cls: type) -> Any:
    """Parse string to enum value if needed."""
    return enum_cls(value) if isinstance(value, str) else value


def _parse_decorator_config(**kwargs) -> _RateLimitDecoratorConfig:
    """Parse and validate decorator parameters into config object."""
    return _RateLimitDecoratorConfig(
        rate=kwargs.get('rate', 10),
        per_seconds=kwargs.get('per_seconds', 1.0),
        burst=kwargs.get('burst'),
        strategy=_parse_enum_value(kwargs.get('strategy', RateLimitStrategy.TOKEN_BUCKET), RateLimitStrategy),
        backend=_parse_enum_value(kwargs.get('backend', RateLimitBackend.MEMORY), RateLimitBackend),
        key_strategy=_parse_enum_value(kwargs.get('key_strategy', KeyGenerationStrategy.PER_FUNCTION), KeyGenerationStrategy),
        key_func=kwargs.get('key_func'),
        mode=_parse_enum_value(kwargs.get('mode', RateLimitMode.BLOCK), RateLimitMode),
        timeout=kwargs.get('timeout'),
        redis_url=kwargs.get('redis_url'),
        service_name=kwargs.get('service_name'),
        exchange=kwargs.get('exchange'),
        endpoint_type=kwargs.get('endpoint_type'),
        on_limit_exceeded=kwargs.get('on_limit_exceeded')
    )


def _create_rate_limit_context(cfg: _RateLimitDecoratorConfig) -> _RateLimitContext:
    """Create rate limit context with all necessary components."""
    config_params = {
        "strategy": cfg.strategy,
        "rate": cfg.rate,
        "per_seconds": cfg.per_seconds,
        "burst": cfg.burst,
        "backend": cfg.backend,
        "redis_url": cfg.redis_url,
    }
    
    limiter = _create_limiter(cfg.exchange, cfg.endpoint_type, config_params)
    
    return _RateLimitContext(
        limiter=limiter,
        metrics=get_metrics_collector(cfg.service_name),
        key_strategy=cfg.key_strategy,
        rate_mode=cfg.mode,
        timeout=cfg.timeout,
        exchange=cfg.exchange,
        endpoint_type=cfg.endpoint_type,
        on_limit_exceeded=cfg.on_limit_exceeded,
        config_params=config_params,
        key_func=cfg.key_func
    )


def _create_limiter(
    exchange: Optional[str],
    endpoint_type: Optional[str],
    config_params: dict
) -> Any:
    """Create the appropriate rate limiter based on configuration."""
    if exchange:
        return create_exchange_rate_limiter(
            exchange,
            endpoint_type or "requests",
            strategy=config_params["strategy"],
            rate=config_params["rate"],
            per_seconds=config_params["per_seconds"],
            burst=config_params["burst"],
            backend=config_params["backend"],
            redis_url=config_params["redis_url"]
        )
    return create_rate_limiter(**config_params)


def _create_async_wrapper(func: F, ctx: _RateLimitContext) -> F:
    """Create async wrapper for rate-limited function."""
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.monotonic()
        
        try:
            key = _resolve_rate_limit_key(func, args, kwargs, ctx)
            result = await _acquire_rate_limit_async(ctx, key)
            duration = time.monotonic() - start_time
            
            _record_rate_limit_metrics(ctx, key, result, duration)
            
            if not result.allowed and ctx.rate_mode == RateLimitMode.REJECT:
                return await _handle_limit_exceeded_async(ctx, func, args, kwargs, result)
            
            return await func(*args, **kwargs)
            
        except Exception as e:
            if _handle_rate_limit_error(e, func, ctx.rate_mode):
                return await func(*args, **kwargs)
    
    return cast(F, async_wrapper)


def _create_sync_wrapper(func: F, ctx: _RateLimitContext) -> F:
    """Create sync wrapper for rate-limited function."""
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.monotonic()
        
        try:
            key = _resolve_rate_limit_key(func, args, kwargs, ctx)
            result = _acquire_rate_limit_sync(ctx, key)
            duration = time.monotonic() - start_time
            
            _record_rate_limit_metrics(ctx, key, result, duration)
            
            if not result.allowed and ctx.rate_mode == RateLimitMode.REJECT:
                return _handle_limit_exceeded_sync(ctx, func, args, kwargs, result)
            
            return func(*args, **kwargs)
            
        except Exception as e:
            if _handle_rate_limit_error(e, func, ctx.rate_mode):
                return func(*args, **kwargs)
    
    return cast(F, sync_wrapper)


def rate_limit(
    rate: int = 10,
    per_seconds: float = 1.0,
    burst: Optional[int] = None,
    strategy: Union[str, RateLimitStrategy] = RateLimitStrategy.TOKEN_BUCKET,
    backend: Union[str, RateLimitBackend] = RateLimitBackend.MEMORY,
    key_strategy: Union[str, KeyGenerationStrategy] = KeyGenerationStrategy.PER_FUNCTION,
    mode: Union[str, RateLimitMode] = RateLimitMode.BLOCK,
    enabled: bool = True,
    **kwargs
) -> Callable[[F], F]:
    """
    Decorator for adding rate limiting to functions.
    
    Args:
        rate: Number of requests allowed per time period
        per_seconds: Time period in seconds
        burst: Maximum burst capacity (defaults to rate)
        strategy: Rate limiting strategy (token_bucket, sliding_window, fixed_window)
        backend: Storage backend (memory, redis)
        key_strategy: How to generate rate limit keys
        mode: Enforcement mode (block, reject, log_only)
        enabled: Whether rate limiting is enabled
        **kwargs: Additional options:
            - key_func: Custom function for generating keys
            - timeout: Maximum time to wait for tokens (blocking mode)
            - redis_url: Redis connection URL (for Redis backend)
            - service_name: Service name for metrics
            - exchange: Exchange name (for exchange-specific limiting)
            - endpoint_type: Endpoint type (for exchange-specific limiting)
            - on_limit_exceeded: Callback function when limit is exceeded
        
    Returns:
        Decorated function
    """
    
    def decorator(func: F) -> F:
        if not enabled:
            return func
        
        cfg = _parse_decorator_config(
            rate=rate, per_seconds=per_seconds, burst=burst,
            strategy=strategy, backend=backend, key_strategy=key_strategy,
            mode=mode, **kwargs
        )
        ctx = _create_rate_limit_context(cfg)
        
        if inspect.iscoroutinefunction(func):
            return _create_async_wrapper(func, ctx)
        return _create_sync_wrapper(func, ctx)
    
    return decorator


def exchange_rate_limit(
    exchange: str,
    endpoint_type: str = "requests",
    **kwargs
) -> Callable[[F], F]:
    """
    Convenience decorator for exchange-specific rate limiting.
    
    Args:
        exchange: Exchange name (binance, okx, etc.)
        endpoint_type: Type of endpoint (requests, orders, weight)
        **kwargs: Additional rate_limit decorator arguments
        
    Returns:
        Decorated function
    """
    return rate_limit(exchange=exchange, endpoint_type=endpoint_type, **kwargs)


# FastAPI Middleware
try:
    from fastapi import HTTPException, Request, Response
    from fastapi.responses import JSONResponse
    
    class FastAPIRateLimitMiddleware:
        """
        FastAPI middleware for rate limiting HTTP requests.
        
        This middleware applies rate limiting to incoming HTTP requests
        based on configurable criteria like IP address, user ID, or endpoint.
        """
        
        def __init__(
            self,
            app,
            rate: int = 100,
            per_seconds: float = 60.0,
            burst: Optional[int] = None,
            strategy: Union[str, RateLimitStrategy] = RateLimitStrategy.TOKEN_BUCKET,
            backend: Union[str, RateLimitBackend] = RateLimitBackend.MEMORY,
            key_strategy: Union[str, KeyGenerationStrategy] = KeyGenerationStrategy.PER_IP,
            key_func: Optional[Callable[[Request], str]] = None,
            redis_url: Optional[str] = None,
            service_name: str = "fastapi",
            exclude_paths: Optional[list[str]] = None,
            on_limit_exceeded: Optional[Callable] = None,
            enabled: bool = True
        ):
            self.app = app
            self.enabled = enabled
            
            if not enabled:
                return
            
            # Configuration
            self.rate = rate
            self.per_seconds = per_seconds
            self.key_strategy = KeyGenerationStrategy(key_strategy) if isinstance(key_strategy, str) else key_strategy
            self.key_func = key_func
            self.exclude_paths = set(exclude_paths or [])
            self.on_limit_exceeded = on_limit_exceeded
            
            # Create rate limiter
            config_params = {
                "strategy": RateLimitStrategy(strategy) if isinstance(strategy, str) else strategy,
                "rate": rate,
                "per_seconds": per_seconds,
                "burst": burst,
                "backend": RateLimitBackend(backend) if isinstance(backend, str) else backend,
                "redis_url": redis_url
            }
            
            self.limiter = create_rate_limiter(**config_params)
            self.metrics = get_metrics_collector(service_name)
        
        def _generate_key(self, request: Request) -> str:
            """Generate rate limit key for request."""
            if self.key_func:
                return self.key_func(request)
            
            if self.key_strategy == KeyGenerationStrategy.PER_IP:
                ip = _extract_ip_from_request(request)
                return f"ip:{ip}" if ip else _UNKNOWN_IP_KEY
            
            elif self.key_strategy == KeyGenerationStrategy.PER_USER:
                # Try to extract user from request (requires authentication middleware)
                user_id = getattr(request.state, 'user_id', None)
                if user_id:
                    return f"user:{user_id}"
                
                # Fallback to IP
                ip = _extract_ip_from_request(request)
                return f"ip:{ip}" if ip else _UNKNOWN_IP_KEY
            
            elif self.key_strategy == KeyGenerationStrategy.PER_FUNCTION:
                return f"endpoint:{request.method}:{request.url.path}"
            
            else:
                return "global"
        
        async def __call__(self, request: Request, call_next):
            if not self.enabled:
                return await call_next(request)
            
            # Check if path should be excluded
            if request.url.path in self.exclude_paths:
                return await call_next(request)
            
            start_time = time.monotonic()
            
            try:
                # Generate rate limit key
                key = self._generate_key(request)
                
                # Check rate limit
                result = await self.limiter.acquire(key, 1)
                
                duration = time.monotonic() - start_time
                
                # Record metrics
                if self.metrics:
                    self.metrics.record_request(
                        key=key,
                        allowed=result.allowed,
                        remaining=result.remaining,
                        duration=duration,
                        strategy=self.limiter.config.strategy.value,
                        backend=self.limiter.config.backend.value
                    )
                
                # Handle rate limit exceeded
                if not result.allowed:
                    if self.on_limit_exceeded:
                        return await self.on_limit_exceeded(request, result)
                    else:
                        return JSONResponse(
                            status_code=429,
                            content={
                                "error": "Rate limit exceeded",
                                "retry_after": result.retry_after,
                                "remaining": result.remaining,
                                "reset_time": result.reset_time
                            },
                            headers={
                                "Retry-After": str(int(result.retry_after or 60)),
                                "X-RateLimit-Remaining": str(result.remaining),
                                "X-RateLimit-Reset": str(int(result.reset_time))
                            }
                        )
                
                # Process request
                response = await call_next(request)
                
                # Add rate limit headers to response
                response.headers["X-RateLimit-Remaining"] = str(result.remaining)
                response.headers["X-RateLimit-Reset"] = str(int(result.reset_time))
                
                return response
                
            except Exception as e:
                # Log error but don't fail the request
                import logging
                logging.error(f"Rate limiting middleware error: {e}")
                
                return await call_next(request)

except ImportError:
    # FastAPI not available
    FastAPIRateLimitMiddleware = None  # type: ignore


# Flask Middleware
try:
    from flask import Flask, g, jsonify, request
    
    class FlaskRateLimitMiddleware:
        """
        Flask middleware for rate limiting HTTP requests.
        """
        
        def __init__(
            self,
            app: Flask,
            rate: int = 100,
            per_seconds: float = 60.0,
            burst: Optional[int] = None,
            strategy: Union[str, RateLimitStrategy] = RateLimitStrategy.TOKEN_BUCKET,
            backend: Union[str, RateLimitBackend] = RateLimitBackend.MEMORY,
            key_strategy: Union[str, KeyGenerationStrategy] = KeyGenerationStrategy.PER_IP,
            key_func: Optional[Callable] = None,
            redis_url: Optional[str] = None,
            service_name: str = "flask",
            exclude_paths: Optional[list[str]] = None,
            enabled: bool = True
        ):
            self.app = app
            self.enabled = enabled
            
            if not enabled:
                return
            
            # Configuration
            self.key_strategy = KeyGenerationStrategy(key_strategy) if isinstance(key_strategy, str) else key_strategy
            self.key_func = key_func
            self.exclude_paths = set(exclude_paths or [])
            
            # Create rate limiter
            config_params = {
                "strategy": RateLimitStrategy(strategy) if isinstance(strategy, str) else strategy,
                "rate": rate,
                "per_seconds": per_seconds,
                "burst": burst,
                "backend": RateLimitBackend(backend) if isinstance(backend, str) else backend,
                "redis_url": redis_url
            }
            
            self.limiter = create_rate_limiter(**config_params)
            self.metrics = get_metrics_collector(service_name)
            
            # Register middleware
            app.before_request(self._before_request)
            app.after_request(self._after_request)
        
        def _generate_key(self) -> str:
            """Generate rate limit key for request."""
            if self.key_func:
                return self.key_func()
            
            if self.key_strategy == KeyGenerationStrategy.PER_IP:
                ip = _extract_ip_from_request(request)
                return f"ip:{ip}" if ip else _UNKNOWN_IP_KEY
            
            elif self.key_strategy == KeyGenerationStrategy.PER_USER:
                # Try to extract user from g or session
                user_id = getattr(g, 'user_id', None) or getattr(g, 'user', {}).get('id')
                if user_id:
                    return f"user:{user_id}"
                
                # Fallback to IP
                ip = _extract_ip_from_request(request)
                return f"ip:{ip}" if ip else _UNKNOWN_IP_KEY
            
            elif self.key_strategy == KeyGenerationStrategy.PER_FUNCTION:
                return f"endpoint:{request.method}:{request.path}"
            
            else:
                return "global"
        
        def _before_request(self):
            if not self.enabled or request.path in self.exclude_paths:
                return
            
            start_time = time.monotonic()
            g._rate_limit_start = start_time
            
            try:
                # Generate rate limit key
                key = self._generate_key()
                g._rate_limit_key = key
                
                # Check rate limit (non-blocking for Flask)
                import asyncio
                
                loop = None
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                result = loop.run_until_complete(self.limiter.acquire(key, 1))
                g._rate_limit_result = result
                
                # Handle rate limit exceeded
                if not result.allowed:
                    response = jsonify({
                        "error": "Rate limit exceeded",
                        "retry_after": result.retry_after,
                        "remaining": result.remaining,
                        "reset_time": result.reset_time
                    })
                    response.status_code = 429
                    response.headers["Retry-After"] = str(int(result.retry_after or 60))
                    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
                    response.headers["X-RateLimit-Reset"] = str(int(result.reset_time))
                    
                    return response
                
            except Exception as e:
                # Log error but don't fail the request
                import logging
                logging.error(f"Rate limiting middleware error: {e}")
        
        def _after_request(self, response):
            if not self.enabled or not hasattr(g, '_rate_limit_result'):
                return response
            
            try:
                # Add rate limit headers
                result = g._rate_limit_result
                response.headers["X-RateLimit-Remaining"] = str(result.remaining)
                response.headers["X-RateLimit-Reset"] = str(int(result.reset_time))
                
                # Record metrics
                if self.metrics and hasattr(g, '_rate_limit_start'):
                    duration = time.monotonic() - g._rate_limit_start
                    key = getattr(g, '_rate_limit_key', 'unknown')
                    
                    self.metrics.record_request(
                        key=key,
                        allowed=result.allowed,
                        remaining=result.remaining,
                        duration=duration,
                        strategy=self.limiter.config.strategy.value,
                        backend=self.limiter.config.backend.value
                    )
                
            except Exception as e:
                import logging
                logging.error(f"Rate limiting after_request error: {e}")
            
            return response

except ImportError:
    # Flask not available
    FlaskRateLimitMiddleware = None  # type: ignore