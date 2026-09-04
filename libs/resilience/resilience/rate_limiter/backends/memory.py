"""
In-Memory Storage Backend for Rate Limiting

This module provides a fast, thread-safe in-memory storage backend for rate limiting.
It's ideal for single-instance deployments or when you don't need distributed 
rate limiting across multiple servers.

Key Features:
- Thread-safe operations using asyncio locks
- Automatic cleanup of expired data to prevent memory leaks
- High performance (sub-millisecond latency)
- No external dependencies
- Graceful degradation under memory pressure

Performance Characteristics:
- Get operations: O(1)
- Set operations: O(1) 
- Atomic updates: O(1) with locking
- Cleanup: O(n) where n is number of stored keys
- Memory usage: Proportional to number of active rate limit keys

Use Cases:
- Single-instance services
- Development and testing
- High-performance scenarios where network latency is critical
- Fallback when Redis is unavailable
"""
import asyncio
from collections import defaultdict
import time
from typing import Any, Callable, Dict, Optional

from ..core import RateLimitConfig, StorageBackend

# Module-level set to prevent fire-and-forget tasks from being garbage collected
_background_tasks: set = set()


class MemoryBackend(StorageBackend):
    """
    In-memory storage backend for rate limiting state.
    
    This backend stores all rate limiting state in memory using Python
    dictionaries and provides thread-safe access through asyncio locks.
    It includes automatic cleanup mechanisms to prevent memory leaks.
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        
        # Main storage for rate limiting state
        self._data: Dict[str, Dict[str, Any]] = {}
        
        # Track access times for cleanup
        self._access_times: Dict[str, float] = {}
        
        # Per-key locks for atomic operations
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # Global lock for cleanup operations
        self._cleanup_lock = asyncio.Lock()
        
        # Track memory usage (approximate)
        self._memory_usage = 0
        self._max_memory_mb = 100  # Default limit: 100MB
        
        # Performance metrics
        self._operations = {
            "get": 0,
            "set": 0, 
            "update": 0,
            "cleanup": 0
        }
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown = False
        
        # Start cleanup if configured
        if config.cleanup_interval > 0:
            self._start_cleanup_task()
    
    def _estimate_memory_usage(self, data: Dict[str, Any]) -> int:
        """
        Estimate memory usage of stored data in bytes.
        
        This is a rough estimate for memory management purposes.
        """
        # Simple estimation based on data structure
        size = 0
        
        for key, value in data.items():
            size += len(str(key)) * 2  # Unicode overhead
            
            if isinstance(value, (int, float)):
                size += 8
            elif isinstance(value, str):
                size += len(value) * 2
            elif isinstance(value, list):
                size += len(value) * 8  # Assuming numbers/timestamps
            elif isinstance(value, dict):
                size += self._estimate_memory_usage(value)
            else:
                size += 50  # Rough estimate for other types
        
        return size
    
    def _update_memory_usage(self, key: str, old_data: Optional[Dict[str, Any]], new_data: Dict[str, Any]) -> None:
        """Update memory usage tracking."""
        if old_data:
            self._memory_usage -= self._estimate_memory_usage(old_data)
        
        self._memory_usage += self._estimate_memory_usage(new_data)
        
        # Rough estimate of key overhead
        self._memory_usage += len(key) * 2
    
    async def get_state(self, key: str) -> Dict[str, Any]:
        """
        Get current state for a rate limit key.
        
        Args:
            key: The rate limit key
            
        Returns:
            Dictionary containing current state (empty if key doesn't exist)
        """
        self._operations["get"] += 1
        
        # Update access time
        self._access_times[key] = time.monotonic()
        
        # Return copy to prevent external modifications
        data = self._data.get(key, {})
        return dict(data) if data else {}
    
    async def set_state(self, key: str, state: Dict[str, Any], ttl: Optional[float] = None) -> None:
        """
        Set state for a rate limit key.
        
        Args:
            key: The rate limit key
            state: State data to store
            ttl: Time to live in seconds (stored for cleanup purposes)
        """
        self._operations["set"] += 1
        
        async with self._locks[key]:
            # Track old data for memory calculation
            old_data = self._data.get(key)
            
            # Store new data with TTL information
            new_state = dict(state)
            if ttl:
                new_state["_ttl"] = time.monotonic() + ttl
            
            self._data[key] = new_state
            self._access_times[key] = time.monotonic()
            
            # Update memory tracking
            self._update_memory_usage(key, old_data, new_state)
    
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
        self._operations["update"] += 1
        
        async with self._locks[key]:
            # Get current state (without TTL metadata)
            current_state = dict(self._data.get(key, {}))
            current_state.pop("_ttl", None)  # Remove TTL from state passed to update function
            
            # Apply update function
            new_state = update_func(current_state)
            
            # Track old data for memory calculation
            old_data = self._data.get(key)
            
            # Add TTL if specified
            if ttl:
                new_state["_ttl"] = time.monotonic() + ttl
            
            # Store updated state
            self._data[key] = new_state
            self._access_times[key] = time.monotonic()
            
            # Update memory tracking
            self._update_memory_usage(key, old_data, new_state)
            
            # Return state without TTL metadata
            result = dict(new_state)
            result.pop("_ttl", None)
            return result
    
    async def cleanup(self) -> None:
        """
        Clean up expired data to prevent memory leaks.
        
        This method removes:
        - Keys that have exceeded their TTL
        - Keys that haven't been accessed recently
        - Oldest keys if memory usage is too high
        """
        if self._cleanup_lock.locked():
            return  # Cleanup already in progress
        
        async with self._cleanup_lock:
            self._operations["cleanup"] += 1
            
            now = time.monotonic()
            expired_keys = self._find_expired_keys(now)
            
            # Remove expired keys
            for key in expired_keys:
                self._remove_key(key)
            
            # If memory usage is still too high, evict oldest keys
            self._evict_oldest_keys_if_needed()
            
            # Ensure memory usage doesn't go negative due to estimation errors
            self._memory_usage = max(0, self._memory_usage)
    
    def _find_expired_keys(self, now: float) -> list:
        """Find keys that are expired by TTL or access time."""
        expired_keys = []
        max_idle_time = self.config.cleanup_interval * 2
        
        for key, data in self._data.items():
            if self._is_key_expired(key, data, now, max_idle_time):
                expired_keys.append(key)
        
        return expired_keys
    
    def _is_key_expired(self, key: str, data: Dict[str, Any], now: float, max_idle_time: float) -> bool:
        """Check if a key has expired by TTL or access time."""
        # Check TTL expiration
        ttl = data.get("_ttl")
        if ttl and now > ttl:
            return True
        
        # Check access time expiration
        last_access = self._access_times.get(key, 0)
        return now - last_access > max_idle_time
    
    def _remove_key(self, key: str) -> None:
        """Remove a key and update memory tracking."""
        old_data = self._data.pop(key, None)
        self._access_times.pop(key, None)
        
        if old_data:
            self._memory_usage -= self._estimate_memory_usage(old_data)
            self._memory_usage -= len(key) * 2
        
        # Remove lock if no longer needed
        if key in self._locks:
            del self._locks[key]
    
    def _evict_oldest_keys_if_needed(self) -> None:
        """Evict oldest keys if memory usage exceeds limit."""
        max_bytes = self._max_memory_mb * 1024 * 1024
        target_bytes = max_bytes * 0.8  # Target 80% of max
        
        if self._memory_usage <= max_bytes or not self._access_times:
            return
        
        # Sort by access time and remove oldest
        sorted_keys = sorted(self._access_times.items(), key=lambda x: x[1])
        
        for key, _ in sorted_keys:
            if self._memory_usage <= target_bytes:
                break
            self._remove_key(key)
    
    async def health_check(self) -> bool:
        """
        Check if backend is healthy.
        
        Returns:
            True if backend is operational
        """
        try:
            # Simple health check - try to perform basic operations
            test_key = "_health_check_test"
            test_data = {"test": time.monotonic()}
            
            await self.set_state(test_key, test_data)
            retrieved = await self.get_state(test_key)
            
            # Clean up test data
            self._data.pop(test_key, None)
            self._access_times.pop(test_key, None)
            
            return retrieved.get("test") == test_data["test"]
            
        except Exception:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get backend statistics for monitoring.
        
        Returns:
            Dictionary with performance and usage statistics
        """
        return {
            "backend_type": "memory",
            "total_keys": len(self._data),
            "memory_usage_bytes": self._memory_usage,
            "memory_usage_mb": round(self._memory_usage / (1024 * 1024), 2),
            "memory_limit_mb": self._max_memory_mb,
            "operations": dict(self._operations),
            "locks_active": len(self._locks),
            "cleanup_interval": self.config.cleanup_interval,
            "health": "healthy"
        }
    
    def set_memory_limit(self, limit_mb: int) -> None:
        """Set memory usage limit in megabytes."""
        if limit_mb < 1:
            raise ValueError("Memory limit must be at least 1MB")
        self._max_memory_mb = limit_mb
    
    def _start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        async def cleanup_loop():
            while not self._shutdown:
                try:
                    await asyncio.sleep(self.config.cleanup_interval)
                    if not self._shutdown:
                        await self.cleanup()
                except Exception as e:
                    # Log error but continue cleanup loop
                    # Note: asyncio.CancelledError is a BaseException, not Exception,
                    # so it will propagate automatically and not be caught here
                    import logging
                    logging.error(f"Memory backend cleanup error: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the backend."""
        self._shutdown = True
        
        try:
            if self._cleanup_task:
                self._cleanup_task.cancel()
                # Use gather with return_exceptions=True to:
                # 1. Collect the expected CancelledError from our cancel() without raising
                # 2. Still propagate external cancellation of shutdown() itself
                #    (per Python docs: "If gather() itself is cancelled, the 
                #    cancellation is propagated regardless of return_exceptions")
                await asyncio.gather(self._cleanup_task, return_exceptions=True)
            
            # Final cleanup
            await self.cleanup()
        finally:
            # Clear all data (runs even if cancelled, then CancelledError re-raises)
            self._data.clear()
            self._access_times.clear()
            self._locks.clear()
            self._memory_usage = 0
    
    def __del__(self) -> None:
        """Cleanup on deletion."""
        if not self._shutdown and hasattr(asyncio, 'get_event_loop'):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Store task in module-level set to prevent garbage collection
                    # before completion. Task removes itself when done.
                    task = asyncio.create_task(self.shutdown())
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)
            except RuntimeError:
                # Event loop may not be available during shutdown
                pass


class SynchronousMemoryBackend:
    """
    Synchronous version of memory backend for thread-based applications.
    
    This provides the same functionality as MemoryBackend but uses threading
    primitives instead of asyncio. Useful for synchronous web frameworks or
    applications that don't use asyncio.
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        
        # Storage and threading primitives
        import threading
        
        self._data: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = threading.RLock()
        self._memory_usage = 0
        self._max_memory_mb = 100
        
        # Operation counters
        self._operations = {
            "get": 0,
            "set": 0,
            "update": 0,
            "cleanup": 0
        }
    
    def get_state(self, key: str) -> Dict[str, Any]:
        """Synchronous get state."""
        with self._lock:
            self._operations["get"] += 1
            self._access_times[key] = time.monotonic()
            
            data = self._data.get(key, {})
            return dict(data) if data else {}
    
    def set_state(self, key: str, state: Dict[str, Any], ttl: Optional[float] = None) -> None:
        """Synchronous set state."""
        with self._lock:
            self._operations["set"] += 1
            
            new_state = dict(state)
            if ttl:
                new_state["_ttl"] = time.monotonic() + ttl
            
            self._data[key] = new_state
            self._access_times[key] = time.monotonic()
    
    def atomic_update(
        self, 
        key: str, 
        update_func: Callable[[Dict[str, Any]], Dict[str, Any]], 
        ttl: Optional[float] = None
    ) -> Dict[str, Any]:
        """Synchronous atomic update."""
        with self._lock:
            self._operations["update"] += 1
            
            # Get current state without TTL
            current_state = dict(self._data.get(key, {}))
            current_state.pop("_ttl", None)
            
            # Apply update
            new_state = update_func(current_state)
            
            # Add TTL if specified
            if ttl:
                new_state["_ttl"] = time.monotonic() + ttl
            
            # Store updated state
            self._data[key] = new_state
            self._access_times[key] = time.monotonic()
            
            # Return without TTL
            result = dict(new_state)
            result.pop("_ttl", None)
            return result
    
    def cleanup(self) -> None:
        """Synchronous cleanup."""
        with self._lock:
            self._operations["cleanup"] += 1
            
            now = time.monotonic()
            expired_keys = []
            
            # Find expired keys
            for key, data in self._data.items():
                ttl = data.get("_ttl")
                if ttl and now > ttl:
                    expired_keys.append(key)
                    continue
                
                last_access = self._access_times.get(key, 0)
                if now - last_access > self.config.cleanup_interval * 2:
                    expired_keys.append(key)
            
            # Remove expired keys
            for key in expired_keys:
                self._data.pop(key, None)
                self._access_times.pop(key, None)
    
    def health_check(self) -> bool:
        """Synchronous health check."""
        try:
            test_key = "_health_check_test"
            test_data = {"test": time.monotonic()}
            
            self.set_state(test_key, test_data)
            retrieved = self.get_state(test_key)
            
            # Cleanup
            with self._lock:
                self._data.pop(test_key, None)
                self._access_times.pop(test_key, None)
            
            return retrieved.get("test") == test_data["test"]
            
        except Exception:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get backend statistics."""
        with self._lock:
            return {
                "backend_type": "memory_sync",
                "total_keys": len(self._data),
                "operations": dict(self._operations),
                "memory_limit_mb": self._max_memory_mb,
                "health": "healthy"
            }