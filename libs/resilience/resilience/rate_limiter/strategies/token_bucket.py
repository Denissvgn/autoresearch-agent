"""
Token Bucket Rate Limiting Strategy

This module implements the token bucket algorithm for rate limiting.
The token bucket algorithm is excellent for allowing bursts while maintaining
an average rate over time.

Algorithm Overview:
1. Tokens are added to a bucket at a fixed rate
2. Each request consumes one or more tokens
3. If sufficient tokens are available, the request is allowed
4. If not enough tokens are available, the request is denied or delayed
5. The bucket has a maximum capacity (burst limit)

Key Properties:
- Allows bursts up to the bucket capacity
- Maintains average rate over time
- Self-regulating - unused capacity accumulates
- Predictable behavior under varying load
"""
import asyncio
import time
from typing import Any, Dict

from ..core import RateLimitConfig, RateLimitResult, RateLimitStrategyImpl, StorageBackend


class TokenBucketStrategy(RateLimitStrategyImpl):
    """
    Token bucket rate limiting strategy implementation.
    
    This strategy maintains a bucket of tokens that are refilled at a constant rate.
    Requests consume tokens from the bucket, and are allowed only if sufficient 
    tokens are available.
    """
    
    def __init__(self, config: RateLimitConfig, backend: StorageBackend):
        super().__init__(config, backend)
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a per-key lock for thread safety."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
    
    def _calculate_tokens(self, current_tokens: float, last_update: float, now: float) -> float:
        """
        Calculate current token count based on elapsed time.
        
        Args:
            current_tokens: Current token count in bucket
            last_update: Last update timestamp
            now: Current timestamp
            
        Returns:
            Updated token count
        """
        if last_update <= 0:
            # First time - start with full bucket
            return float(self.config.effective_burst)
        
        elapsed = now - last_update
        if elapsed <= 0:
            return current_tokens
        
        # Calculate tokens to add based on elapsed time and rate
        tokens_to_add = elapsed * (self.config.rate / self.config.per_seconds)
        new_tokens = current_tokens + tokens_to_add
        
        # Cap at burst limit
        return min(float(self.config.effective_burst), new_tokens)
    
    def _calculate_wait_time(self, needed_tokens: float) -> float:
        """
        Calculate how long to wait for sufficient tokens.
        
        Args:
            needed_tokens: Number of additional tokens needed
            
        Returns:
            Wait time in seconds
        """
        if needed_tokens <= 0:
            return 0.0
        
        # Time to accumulate needed tokens at the configured rate
        return needed_tokens * (self.config.per_seconds / self.config.rate)
    
    def _get_reset_time(self, current_tokens: float) -> float:
        """
        Calculate when the bucket will be full again.
        
        Args:
            current_tokens: Current token count
            
        Returns:
            Unix timestamp when bucket will be full
        """
        if current_tokens >= self.config.effective_burst:
            return time.time()  # Already full
        
        tokens_needed = self.config.effective_burst - current_tokens
        time_to_fill = self._calculate_wait_time(tokens_needed)
        return time.time() + time_to_fill
    
    async def check_rate_limit(self, key: str, tokens: int = 1) -> RateLimitResult:
        """
        Check if request is allowed under token bucket rate limit.
        
        This method uses optimistic locking to ensure thread safety while
        maintaining high performance. It fetches current state, calculates
        new state, and atomically updates if possible.
        """
        if tokens <= 0:
            # Edge case: requesting 0 or negative tokens
            current_state = await self.backend.get_state(key)
            current_tokens = current_state.get("tokens", float(self.config.effective_burst))
            
            return RateLimitResult(
                allowed=True,
                remaining=int(current_tokens),
                reset_time=self._get_reset_time(current_tokens),
                strategy_used="token_bucket",
                backend_used=self.config.backend.value
            )
        
        if tokens > self.config.effective_burst:
            # Request exceeds bucket capacity - can never be satisfied
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=time.time() + self.config.per_seconds,
                retry_after=float('inf'),  # Never
                strategy_used="token_bucket", 
                backend_used=self.config.backend.value
            )
        
        # Use atomic update to ensure consistency
        def update_state(current_state: Dict[str, Any]) -> Dict[str, Any]:
            now = time.monotonic()
            current_tokens = current_state.get("tokens", 0.0)
            last_update = current_state.get("last_update", 0.0)
            
            # Calculate current token count
            updated_tokens = self._calculate_tokens(current_tokens, last_update, now)
            
            if updated_tokens >= tokens:
                # Request can be satisfied
                new_tokens = updated_tokens - tokens
                return {
                    "tokens": new_tokens,
                    "last_update": now,
                    "allowed": True,
                    "remaining": int(new_tokens),
                    "reset_time": self._get_reset_time(new_tokens)
                }
            else:
                # Not enough tokens
                needed = tokens - updated_tokens
                wait_time = self._calculate_wait_time(needed)
                
                return {
                    "tokens": updated_tokens,
                    "last_update": now,
                    "allowed": False,
                    "remaining": int(updated_tokens),
                    "reset_time": self._get_reset_time(updated_tokens),
                    "retry_after": wait_time
                }
        
        try:
            # Set TTL to prevent memory leaks
            ttl = self.config.per_seconds * 2  # Keep data for 2 windows
            new_state = await self.backend.atomic_update(key, update_state, ttl)
            
            return RateLimitResult(
                allowed=new_state["allowed"],
                remaining=new_state["remaining"],
                reset_time=new_state["reset_time"],
                retry_after=new_state.get("retry_after"),
                strategy_used="token_bucket",
                backend_used=self.config.backend.value,
                cache_hit=True
            )
            
        except Exception as e:
            if self.config.strict_mode:
                raise
            
            # Graceful degradation - allow request but log error
            import logging
            logging.error(f"Token bucket backend error for key {key}: {e}")
            
            return RateLimitResult(
                allowed=True,
                remaining=self.config.effective_burst,
                reset_time=time.time() + self.config.per_seconds,
                strategy_used="token_bucket",
                backend_used=self.config.backend.value,
                cache_hit=False
            )
    
    async def reset_rate_limit(self, key: str) -> None:
        """Reset the token bucket to full capacity."""
        now = time.monotonic()
        reset_state = {
            "tokens": float(self.config.effective_burst),
            "last_update": now
        }
        
        # Keep state for 2 windows after reset
        ttl = self.config.per_seconds * 2
        await self.backend.set_state(key, reset_state, ttl)
    
    def get_info(self) -> Dict[str, Any]:
        """Get strategy information for debugging and monitoring."""
        return {
            "strategy": "token_bucket",
            "rate": self.config.rate,
            "per_seconds": self.config.per_seconds,
            "burst_capacity": self.config.effective_burst,
            "backend": self.config.backend.value,
            "algorithm": {
                "type": "token_bucket",
                "description": "Tokens added at fixed rate, consumed by requests",
                "properties": {
                    "allows_bursts": True,
                    "self_regulating": True,
                    "predictable": True,
                    "memory_efficient": True
                }
            },
            "configuration": {
                "strict_mode": self.config.strict_mode,
                "cleanup_interval": self.config.cleanup_interval,
                "max_wait_time": self.config.max_wait_time
            }
        }


class SynchronousTokenBucketStrategy:
    """
    Synchronous version of token bucket strategy for thread-based applications.
    
    This provides the same algorithm as TokenBucketStrategy but uses threading
    primitives instead of asyncio. Useful for synchronous web frameworks or
    applications that don't use asyncio.
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._buckets: Dict[str, Dict[str, float]] = {}
        
        # Use threading lock for synchronous operation
        import threading
        self._lock = threading.RLock()
    
    def _calculate_tokens(self, current_tokens: float, last_update: float, now: float) -> float:
        """Calculate current token count (same as async version)."""
        if last_update <= 0:
            return float(self.config.effective_burst)
        
        elapsed = now - last_update
        if elapsed <= 0:
            return current_tokens
        
        tokens_to_add = elapsed * (self.config.rate / self.config.per_seconds)
        new_tokens = current_tokens + tokens_to_add
        
        return min(float(self.config.effective_burst), new_tokens)
    
    def check_rate_limit(self, key: str, tokens: int = 1) -> RateLimitResult:
        """Synchronous rate limit check."""
        if tokens <= 0:
            with self._lock:
                bucket = self._buckets.get(key, {"tokens": float(self.config.effective_burst), "last_update": 0.0})
                return RateLimitResult(
                    allowed=True,
                    remaining=int(bucket["tokens"]),
                    reset_time=time.time() + self.config.per_seconds,
                    strategy_used="token_bucket_sync",
                    backend_used="memory"
                )
        
        if tokens > self.config.effective_burst:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=time.time() + self.config.per_seconds,
                retry_after=float('inf'),
                strategy_used="token_bucket_sync",
                backend_used="memory"
            )
        
        with self._lock:
            now = time.monotonic()
            bucket = self._buckets.get(key, {"tokens": 0.0, "last_update": 0.0})
            
            # Update token count
            current_tokens = self._calculate_tokens(
                bucket["tokens"], 
                bucket["last_update"], 
                now
            )
            
            if current_tokens >= tokens:
                # Allow request
                new_tokens = current_tokens - tokens
                self._buckets[key] = {"tokens": new_tokens, "last_update": now}
                
                reset_time = time.time()
                if new_tokens < self.config.effective_burst:
                    tokens_needed = self.config.effective_burst - new_tokens
                    time_to_fill = tokens_needed * (self.config.per_seconds / self.config.rate)
                    reset_time += time_to_fill
                
                return RateLimitResult(
                    allowed=True,
                    remaining=int(new_tokens),
                    reset_time=reset_time,
                    strategy_used="token_bucket_sync",
                    backend_used="memory"
                )
            else:
                # Deny request
                self._buckets[key] = {"tokens": current_tokens, "last_update": now}
                
                needed = tokens - current_tokens
                wait_time = needed * (self.config.per_seconds / self.config.rate)
                
                return RateLimitResult(
                    allowed=False,
                    remaining=int(current_tokens),
                    reset_time=time.time() + wait_time,
                    retry_after=wait_time,
                    strategy_used="token_bucket_sync",
                    backend_used="memory"
                )
    
    def reset_rate_limit(self, key: str) -> None:
        """Reset bucket to full capacity."""
        with self._lock:
            self._buckets[key] = {
                "tokens": float(self.config.effective_burst),
                "last_update": time.monotonic()
            }
    
    def cleanup(self) -> None:
        """Clean up old buckets to prevent memory leaks."""
        with self._lock:
            now = time.monotonic()
            expired_keys = []
            
            for key, bucket in self._buckets.items():
                # Remove buckets that haven't been used for a while
                if now - bucket["last_update"] > self.config.cleanup_interval:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._buckets[key]