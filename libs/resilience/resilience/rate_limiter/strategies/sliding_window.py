"""
Sliding Window Rate Limiting Strategy

This module implements the sliding window algorithm for rate limiting.
The sliding window algorithm provides more precise rate limiting by tracking
individual request timestamps within a moving time window.

Algorithm Overview:
1. Maintain a log of request timestamps within a sliding time window
2. For each new request, remove expired timestamps outside the window
3. Check if adding the new request would exceed the rate limit
4. Allow or deny the request based on current count vs limit

Key Properties:
- More precise than fixed windows (no boundary effects)
- Prevents gaming at window boundaries
- Memory usage grows with request rate
- Exact rate limiting behavior
- Self-cleaning (old timestamps are automatically removed)

Trade-offs:
- Higher memory usage than token bucket
- More CPU intensive due to timestamp management
- Better precision than fixed window
- No burst allowance (unless explicitly configured)
"""
import asyncio
import time
from typing import Any, Dict, List, TypedDict, Union

from ..core import RateLimitConfig, RateLimitResult, RateLimitStrategyImpl, StorageBackend


class WindowData(TypedDict):
    """Type definition for sliding window data structure."""
    events: List[float]
    last_cleanup: float


class SlidingWindowStrategy(RateLimitStrategyImpl):
    """
    Sliding window rate limiting strategy implementation.
    
    This strategy maintains a sliding window of request timestamps and enforces
    the rate limit by ensuring no more than the configured number of requests
    occur within any window of the configured duration.
    """
    
    def __init__(self, config: RateLimitConfig, backend: StorageBackend):
        super().__init__(config, backend)
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a per-key lock for thread safety."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
    
    def _cleanup_expired_events(self, events: List[float], window_start: float) -> List[float]:
        """
        Remove events that are outside the sliding window.
        
        Args:
            events: List of event timestamps
            window_start: Start of the current window
            
        Returns:
            Cleaned list of events within the window
        """
        # Filter out events outside the window
        return [event for event in events if event >= window_start]
    
    def _calculate_wait_time(self, events: List[float], now: float, tokens: int) -> float:
        """
        Calculate how long to wait before the request can be allowed.
        
        Args:
            events: Current events in the window
            now: Current timestamp
            tokens: Number of tokens requested
            
        Returns:
            Wait time in seconds
        """
        if not events or len(events) + tokens <= self.config.effective_burst:
            return 0.0
        
        # Find the Nth oldest event that would need to expire
        # to make room for the new request(s)
        events_to_expire = len(events) + tokens - self.config.effective_burst
        
        if events_to_expire <= 0 or events_to_expire > len(events):
            return 0.0
        
        # Sort events to find the Nth oldest
        sorted_events = sorted(events)
        oldest_relevant = sorted_events[events_to_expire - 1]
        
        # Calculate when this event will expire from the window
        event_expiry = oldest_relevant + self.config.per_seconds
        wait_time = max(0.0, event_expiry - now)
        
        return wait_time
    
    def _get_reset_time(self, events: List[float], now: float) -> float:
        """
        Calculate when the rate limit will reset (window will have space).
        
        Args:
            events: Current events in the window
            now: Current timestamp
            
        Returns:
            Unix timestamp when rate limit resets
        """
        if len(events) < self.config.effective_burst:
            return now  # Already has space
        
        if not events:
            return now + self.config.per_seconds
        
        # Find when the oldest event will expire
        oldest_event = min(events)
        return oldest_event + self.config.per_seconds
    
    async def check_rate_limit(self, key: str, tokens: int = 1) -> RateLimitResult:
        """
        Check if request is allowed under sliding window rate limit.
        
        This method maintains a list of timestamps for each key and slides
        the window to enforce precise rate limiting.
        """
        if tokens <= 0:
            # Edge case: requesting 0 or negative tokens
            current_state = await self.backend.get_state(key)
            events = current_state.get("events", [])
            
            return RateLimitResult(
                allowed=True,
                remaining=max(0, self.config.effective_burst - len(events)),
                reset_time=self._get_reset_time(events, time.time()),
                strategy_used="sliding_window",
                backend_used=self.config.backend.value
            )
        
        if tokens > self.config.effective_burst:
            # Request exceeds window capacity - can never be satisfied
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=time.time() + self.config.per_seconds,
                retry_after=float('inf'),  # Never
                strategy_used="sliding_window",
                backend_used=self.config.backend.value
            )
        
        # Use atomic update to ensure consistency
        def update_state(current_state: Dict[str, Any]) -> Dict[str, Any]:
            now = time.time()
            window_start = now - self.config.per_seconds
            
            # Get current events and clean up expired ones
            events = current_state.get("events", [])
            active_events = self._cleanup_expired_events(events, window_start)
            
            # Check if request can be satisfied
            if len(active_events) + tokens <= self.config.effective_burst:
                # Add new events for the tokens being consumed
                new_events = active_events + [now] * tokens
                remaining = max(0, self.config.effective_burst - len(new_events))
                
                return {
                    "events": new_events,
                    "last_cleanup": now,
                    "allowed": True,
                    "remaining": remaining,
                    "reset_time": self._get_reset_time(new_events, now)
                }
            else:
                # Request cannot be satisfied
                wait_time = self._calculate_wait_time(active_events, now, tokens)
                remaining = max(0, self.config.effective_burst - len(active_events))
                
                return {
                    "events": active_events,
                    "last_cleanup": now,
                    "allowed": False,
                    "remaining": remaining,
                    "reset_time": self._get_reset_time(active_events, now),
                    "retry_after": wait_time
                }
        
        try:
            # Set TTL to prevent memory leaks - keep data for 2 windows
            ttl = self.config.per_seconds * 2
            new_state = await self.backend.atomic_update(key, update_state, ttl)
            
            return RateLimitResult(
                allowed=new_state["allowed"],
                remaining=new_state["remaining"],
                reset_time=new_state["reset_time"],
                retry_after=new_state.get("retry_after"),
                strategy_used="sliding_window",
                backend_used=self.config.backend.value,
                cache_hit=True
            )
            
        except Exception as e:
            if self.config.strict_mode:
                raise
            
            # Graceful degradation - allow request but log error
            import logging
            logging.error(f"Sliding window backend error for key {key}: {e}")
            
            return RateLimitResult(
                allowed=True,
                remaining=self.config.effective_burst,
                reset_time=time.time() + self.config.per_seconds,
                strategy_used="sliding_window",
                backend_used=self.config.backend.value,
                cache_hit=False
            )
    
    async def reset_rate_limit(self, key: str) -> None:
        """Reset the sliding window by clearing all events."""
        reset_state = {
            "events": [],
            "last_cleanup": time.time()
        }
        
        # Keep state for 2 windows after reset
        ttl = self.config.per_seconds * 2
        await self.backend.set_state(key, reset_state, ttl)
    
    def get_info(self) -> Dict[str, Any]:
        """Get strategy information for debugging and monitoring."""
        return {
            "strategy": "sliding_window",
            "rate": self.config.rate,
            "per_seconds": self.config.per_seconds,
            "window_capacity": self.config.effective_burst,
            "backend": self.config.backend.value,
            "algorithm": {
                "type": "sliding_window",
                "description": "Tracks individual request timestamps in sliding window",
                "properties": {
                    "precise_rate_limiting": True,
                    "no_boundary_effects": True,
                    "memory_usage_scales_with_rate": True,
                    "exact_behavior": True,
                    "self_cleaning": True
                }
            },
            "configuration": {
                "strict_mode": self.config.strict_mode,
                "cleanup_interval": self.config.cleanup_interval,
                "max_wait_time": self.config.max_wait_time
            }
        }


class SynchronousSlidingWindowStrategy:
    """
    Synchronous version of sliding window strategy for thread-based applications.
    
    This provides the same algorithm as SlidingWindowStrategy but uses threading
    primitives instead of asyncio.
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._windows: Dict[str, WindowData] = {}
        
        # Use threading lock for synchronous operation
        import threading
        self._lock = threading.RLock()
    
    def _cleanup_expired_events(self, events: List[float], window_start: float) -> List[float]:
        """Remove events outside the sliding window (same as async version)."""
        return [event for event in events if event >= window_start]
    
    def _calculate_wait_time(self, events: List[float], now: float, tokens: int) -> float:
        """Calculate wait time (same as async version)."""
        if not events or len(events) + tokens <= self.config.effective_burst:
            return 0.0
        
        events_to_expire = len(events) + tokens - self.config.effective_burst
        
        if events_to_expire <= 0 or events_to_expire > len(events):
            return 0.0
        
        sorted_events = sorted(events)
        oldest_relevant = sorted_events[events_to_expire - 1]
        event_expiry = oldest_relevant + self.config.per_seconds
        
        return max(0.0, event_expiry - now)
    
    def check_rate_limit(self, key: str, tokens: int = 1) -> RateLimitResult:
        """Synchronous sliding window rate limit check."""
        if tokens <= 0:
            with self._lock:
                default_window: WindowData = {"events": [], "last_cleanup": 0.0}
                window = self._windows.get(key, default_window)
                events = window["events"]
                return RateLimitResult(
                    allowed=True,
                    remaining=max(0, self.config.effective_burst - len(events)),
                    reset_time=time.time() + self.config.per_seconds,
                    strategy_used="sliding_window_sync",
                    backend_used="memory"
                )
        
        if tokens > self.config.effective_burst:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=time.time() + self.config.per_seconds,
                retry_after=float('inf'),
                strategy_used="sliding_window_sync",
                backend_used="memory"
            )
        
        with self._lock:
            now = time.time()
            window_start = now - self.config.per_seconds
            
            # Get current window or create new one
            default_window: WindowData = {"events": [], "last_cleanup": 0.0}
            window = self._windows.get(key, default_window)
            events = window["events"]
            
            # Clean up expired events
            active_events = self._cleanup_expired_events(events, window_start)
            
            if len(active_events) + tokens <= self.config.effective_burst:
                # Allow request
                new_events = active_events + [now] * tokens
                remaining = max(0, self.config.effective_burst - len(new_events))
                
                self._windows[key] = {
                    "events": new_events,
                    "last_cleanup": now
                }
                
                # Calculate reset time
                reset_time = now
                if len(new_events) >= self.config.effective_burst:
                    oldest_event = min(new_events) if new_events else now
                    reset_time = oldest_event + self.config.per_seconds
                
                return RateLimitResult(
                    allowed=True,
                    remaining=remaining,
                    reset_time=reset_time,
                    strategy_used="sliding_window_sync",
                    backend_used="memory"
                )
            else:
                # Deny request
                remaining = max(0, self.config.effective_burst - len(active_events))
                wait_time = self._calculate_wait_time(active_events, now, tokens)
                
                self._windows[key] = {
                    "events": active_events,
                    "last_cleanup": now
                }
                
                return RateLimitResult(
                    allowed=False,
                    remaining=remaining,
                    reset_time=now + wait_time,
                    retry_after=wait_time,
                    strategy_used="sliding_window_sync",
                    backend_used="memory"
                )
    
    def reset_rate_limit(self, key: str) -> None:
        """Reset window by clearing all events."""
        with self._lock:
            self._windows[key] = {
                "events": [],
                "last_cleanup": time.time()
            }
    
    def cleanup(self) -> None:
        """Clean up old windows to prevent memory leaks."""
        with self._lock:
            now = time.time()
            expired_keys = []
            
            for key, window in self._windows.items():
                # Remove windows that haven't been used recently
                last_cleanup = window["last_cleanup"]
                if now - last_cleanup > self.config.cleanup_interval:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._windows[key]


class FixedWindowStrategy(RateLimitStrategyImpl):
    """
    Fixed window rate limiting strategy (simpler alternative to sliding window).
    
    This strategy divides time into fixed windows and allows a fixed number
    of requests per window. It's less precise than sliding window but more
    memory efficient.
    """
    
    async def check_rate_limit(self, key: str, tokens: int = 1) -> RateLimitResult:
        """Check rate limit using fixed time windows."""
        if tokens <= 0:
            return RateLimitResult(
                allowed=True,
                remaining=self.config.effective_burst,
                reset_time=time.time(),
                strategy_used="fixed_window",
                backend_used=self.config.backend.value
            )
        
        if tokens > self.config.effective_burst:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=time.time() + self.config.per_seconds,
                retry_after=float('inf'),
                strategy_used="fixed_window",
                backend_used=self.config.backend.value
            )
        
        def update_state(current_state: Dict[str, Any]) -> Dict[str, Any]:
            now = time.time()
            window_id = int(now // self.config.per_seconds)
            
            current_window = current_state.get("window_id", 0)
            current_count = current_state.get("count", 0)
            
            if window_id != current_window:
                # New window - reset count
                current_count = 0
            
            if current_count + tokens <= self.config.effective_burst:
                # Allow request
                new_count = current_count + tokens
                remaining = self.config.effective_burst - new_count
                
                # Calculate next window start
                next_window_start = (window_id + 1) * self.config.per_seconds
                
                return {
                    "window_id": window_id,
                    "count": new_count,
                    "allowed": True,
                    "remaining": remaining,
                    "reset_time": next_window_start
                }
            else:
                # Deny request - wait for next window
                next_window_start = (window_id + 1) * self.config.per_seconds
                wait_time = next_window_start - now
                
                return {
                    "window_id": window_id,
                    "count": current_count,
                    "allowed": False,
                    "remaining": max(0, self.config.effective_burst - current_count),
                    "reset_time": next_window_start,
                    "retry_after": wait_time
                }
        
        try:
            # TTL should cover at least one window
            ttl = self.config.per_seconds * 2
            new_state = await self.backend.atomic_update(key, update_state, ttl)
            
            return RateLimitResult(
                allowed=new_state["allowed"],
                remaining=new_state["remaining"],
                reset_time=new_state["reset_time"],
                retry_after=new_state.get("retry_after"),
                strategy_used="fixed_window",
                backend_used=self.config.backend.value,
                cache_hit=True
            )
            
        except Exception as e:
            if self.config.strict_mode:
                raise
            
            # Graceful degradation
            import logging
            logging.error(f"Fixed window backend error for key {key}: {e}")
            
            return RateLimitResult(
                allowed=True,
                remaining=self.config.effective_burst,
                reset_time=time.time() + self.config.per_seconds,
                strategy_used="fixed_window",
                backend_used=self.config.backend.value,
                cache_hit=False
            )
    
    async def reset_rate_limit(self, key: str) -> None:
        """Reset the fixed window."""
        now = time.time()
        window_id = int(now // self.config.per_seconds)
        
        reset_state = {
            "window_id": window_id,
            "count": 0
        }
        
        ttl = self.config.per_seconds * 2
        await self.backend.set_state(key, reset_state, ttl)
    
    def get_info(self) -> Dict[str, Any]:
        """Get strategy information."""
        return {
            "strategy": "fixed_window",
            "rate": self.config.rate,
            "per_seconds": self.config.per_seconds,
            "window_capacity": self.config.effective_burst,
            "backend": self.config.backend.value,
            "algorithm": {
                "type": "fixed_window",
                "description": "Fixed time windows with request counts",
                "properties": {
                    "memory_efficient": True,
                    "simple": True,
                    "boundary_effects": True,
                    "burst_at_boundaries": True
                }
            }
        }