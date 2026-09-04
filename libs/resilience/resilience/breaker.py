from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from .exceptions import CircuitOpenError
from .metrics import (
    circuit_breaker_failures_total,
    circuit_breaker_rejections_total,
    circuit_breaker_state,
    circuit_breaker_state_changes_total,
    circuit_breaker_successes_total,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, calls blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: int = 0


@dataclass
class CircuitBreaker:
    """
    Circuit breaker pattern implementation for service calls.
    
    Prevents cascade failures by monitoring service call success/failure rates
    and temporarily blocking calls when failure threshold is exceeded.
    
    Provides enhanced functionality over the basic implementation including:
    - Thread-safe async operations with proper locking
    - Comprehensive statistics tracking
    - Half-open call limiting
    - Detailed metrics emission
    - Configurable parameters
    """
    
    failure_threshold: int
    reset_timeout: float  # seconds
    operation: str = "default"
    half_open_max_calls: int = field(default=1)
    name: Optional[str] = field(default=None)
    
    # Internal state
    state: CircuitBreakerState = field(default=CircuitBreakerState.CLOSED, init=False)
    stats: CircuitBreakerStats = field(default_factory=CircuitBreakerStats, init=False)
    opened_at: Optional[datetime] = field(default=None, init=False)
    half_open_calls: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self):
        """Initialize computed fields after dataclass initialization."""
        if self.name is None:
            self.name = self.operation
        self._set_state(CircuitBreakerState.CLOSED)

    def _set_state(self, new_state: CircuitBreakerState) -> None:
        """Set circuit breaker state and emit metrics."""
        previous_state = self.state
        self.state = new_state
        self.stats.state_changes += 1
        
        # Export numeric state: 0 closed, 1 open, 2 half_open
        state_value = {
            CircuitBreakerState.CLOSED: 0, 
            CircuitBreakerState.OPEN: 1, 
            CircuitBreakerState.HALF_OPEN: 2
        }.get(new_state, 0)
        
        try:
            circuit_breaker_state.labels(operation=self.operation).set(state_value)
            circuit_breaker_state_changes_total.labels(
                operation=self.operation, 
                state=new_state.value
            ).inc()
        except Exception as e:
            logger.warning(f"Failed to emit circuit breaker metrics: {e}")
        
        if previous_state != new_state:
            logger.info(f"Circuit breaker '{self.name}' state changed from {previous_state.value} to {new_state.value}")

    async def _should_allow_call(self) -> bool:
        """Determine if call should be allowed based on current state."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            self._maybe_half_open()
            return self.state != CircuitBreakerState.OPEN
        else:  # HALF_OPEN
            return self.half_open_calls < self.half_open_max_calls

    def _maybe_half_open(self) -> None:
        """Transition from OPEN to HALF_OPEN if timeout period has elapsed."""
        if self.state == CircuitBreakerState.OPEN and self.opened_at is not None:
            if datetime.utcnow() - self.opened_at >= timedelta(seconds=self.reset_timeout):
                self._set_state(CircuitBreakerState.HALF_OPEN)
                self.half_open_calls = 0

    async def _on_success(self) -> None:
        """Handle successful call."""
        self.stats.success_count += 1
        self.stats.last_success_time = time.time()
        
        try:
            circuit_breaker_successes_total.labels(operation=self.operation).inc()
        except Exception as e:
            logger.warning(f"Failed to emit success metrics: {e}")
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            # Success in half-open returns to closed and resets failure count
            self.stats.failure_count = 0
            self._set_state(CircuitBreakerState.CLOSED)

    async def _on_failure(self, exception: Exception) -> None:
        """Handle failed call."""
        self.stats.failure_count += 1
        self.stats.last_failure_time = time.time()
        
        try:
            circuit_breaker_failures_total.labels(operation=self.operation).inc()
        except Exception as e:
            logger.warning(f"Failed to emit failure metrics: {e}")
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1
            # Failure in half-open returns to open
            self._set_state(CircuitBreakerState.OPEN)
            self.opened_at = datetime.utcnow()
        elif self.stats.failure_count >= self.failure_threshold:
            if self.state != CircuitBreakerState.OPEN:
                logger.warning(
                    f"Circuit breaker '{self.name}' opening after "
                    f"{self.stats.failure_count} failures. Last error: {exception}"
                )
                self._set_state(CircuitBreakerState.OPEN)
                self.opened_at = datetime.utcnow()

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute (no arguments)
            
        Returns:
            Function result
            
        Raises:
            CircuitOpenError: When circuit is open
            Exception: Original function exceptions when circuit is closed/half-open
        """
        async with self._lock:
            if await self._should_allow_call():
                try:
                    result = await func()
                    await self._on_success()
                    return result
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    await self._on_failure(e)
                    raise
            else:
                try:
                    circuit_breaker_rejections_total.labels(operation=self.operation).inc()
                except Exception as e:
                    logger.warning(f"Failed to emit rejection metrics: {e}")
                raise CircuitOpenError(f"Circuit breaker '{self.name}' is {self.state.value}")

    async def call_with_args(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with arguments with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitOpenError: When circuit is open
            Exception: Original function exceptions when circuit is closed/half-open
        """
        async with self._lock:
            if await self._should_allow_call():
                try:
                    result = await func(*args, **kwargs)
                    await self._on_success()
                    return result
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    await self._on_failure(e)
                    raise
            else:
                try:
                    circuit_breaker_rejections_total.labels(operation=self.operation).inc()
                except Exception as e:
                    logger.warning(f"Failed to emit rejection metrics: {e}")
                raise CircuitOpenError(f"Circuit breaker '{self.name}' is {self.state.value}")

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "operation": self.operation,
            "state": self.state.value,
            "failure_count": self.stats.failure_count,
            "success_count": self.stats.success_count,
            "last_failure_time": self.stats.last_failure_time,
            "last_success_time": self.stats.last_success_time,
            "state_changes": self.stats.state_changes,
            "failure_threshold": self.failure_threshold,
            "reset_timeout": self.reset_timeout,
            "half_open_max_calls": self.half_open_max_calls
        }

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self.state = CircuitBreakerState.CLOSED
        self.stats = CircuitBreakerStats()
        self.half_open_calls = 0
        self.opened_at = None
        logger.info(f"Circuit breaker '{self.name}' reset to CLOSED state")


class CircuitBreakerManager:
    """Manages multiple circuit breakers with thread-safe access."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_circuit_breaker(
        self, 
        name: str, 
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        half_open_max_calls: int = 1,
        operation: Optional[str] = None
    ) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        async with self._lock:
            if name not in self.circuit_breakers:
                self.circuit_breakers[name] = CircuitBreaker(
                    failure_threshold=failure_threshold,
                    reset_timeout=reset_timeout,
                    operation=operation or name,
                    half_open_max_calls=half_open_max_calls,
                    name=name
                )
            return self.circuit_breakers[name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        return {name: cb.get_stats() for name, cb in self.circuit_breakers.items()}
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            cb.reset()


# Global circuit breaker manager instance
_circuit_breaker_manager = CircuitBreakerManager()


async def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get a circuit breaker instance from the global manager."""
    return await _circuit_breaker_manager.get_circuit_breaker(name, **kwargs)


async def call_with_circuit_breaker(
    func: Callable,
    *args,
    failure_threshold: int = 5,
    timeout: int = 60,
    half_open_requests: int = 1,
    operation: str = "default",
    **kwargs
) -> Any:
    """
    Execute function with circuit breaker protection.
    
    Args:
        func: Function to execute (can be sync or async)
        failure_threshold: Number of failures before opening circuit
        timeout: Seconds to wait before attempting recovery
        half_open_requests: Max calls allowed in half-open state
        operation: Operation name for metrics and logging
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
        
    Raises:
        CircuitOpenError: When circuit is open
        Exception: Original function exceptions
    """
    circuit_breaker = await get_circuit_breaker(
        name=operation,
        failure_threshold=failure_threshold,
        reset_timeout=float(timeout),
        half_open_max_calls=half_open_requests,
        operation=operation
    )
    
    if asyncio.iscoroutinefunction(func):
        return await circuit_breaker.call_with_args(func, *args, **kwargs)
    else:
        # Wrap sync function in async
        async def async_wrapper():
            return func(*args, **kwargs)
        return await circuit_breaker.call(async_wrapper)

