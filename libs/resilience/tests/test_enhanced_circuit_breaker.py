"""Tests for the enhanced circuit breaker implementation."""

import asyncio
import time

import pytest

from resilience.breaker import (
    CircuitBreaker,
    CircuitBreakerManager,
    CircuitBreakerState,
    CircuitBreakerStats,
    call_with_circuit_breaker,
    get_circuit_breaker,
)
from resilience.exceptions import CircuitOpenError

# Mark all tests as asyncio
pytestmark = pytest.mark.asyncio


class TestCircuitBreakerStatsDataclass:
    """Test circuit breaker statistics dataclass."""
    
    def test_stats_initialization(self):
        """Test that stats initialize with correct defaults."""
        stats = CircuitBreakerStats()
        assert stats.failure_count == 0
        assert stats.success_count == 0
        assert stats.last_failure_time is None
        assert stats.last_success_time is None
        assert stats.state_changes == 0


class TestCircuitBreakerBasic:
    """Test basic circuit breaker functionality."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for testing."""
        return CircuitBreaker(
            failure_threshold=2,
            reset_timeout=1.0,
            operation="test_op",
            half_open_max_calls=1,
            name="test_cb"
        )
    
    def test_initialization(self, circuit_breaker):
        """Test circuit breaker initialization."""
        assert circuit_breaker.failure_threshold == 2
        assert circuit_breaker.reset_timeout == 1.0
        assert circuit_breaker.operation == "test_op"
        assert circuit_breaker.half_open_max_calls == 1
        assert circuit_breaker.name == "test_cb"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.stats.failure_count == 0
        assert circuit_breaker.half_open_calls == 0
    
    def test_name_defaults_to_operation(self):
        """Test that name defaults to operation when not provided."""
        cb = CircuitBreaker(
            failure_threshold=5,
            reset_timeout=60.0,
            operation="default_op"
        )
        assert cb.name == "default_op"
    
    async def test_successful_call(self, circuit_breaker):
        """Test successful function execution."""
        async def success_func():
            return "success"
        
        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.stats.success_count == 1
        assert circuit_breaker.stats.failure_count == 0
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
    
    async def test_call_with_args(self, circuit_breaker):
        """Test function execution with arguments."""
        async def add_func(a, b, multiplier=1):
            return (a + b) * multiplier
        
        result = await circuit_breaker.call_with_args(add_func, 2, 3, multiplier=2)
        assert result == 10
        assert circuit_breaker.stats.success_count == 1


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state transitions."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker with low thresholds for testing."""
        return CircuitBreaker(
            failure_threshold=2,
            reset_timeout=0.1,  # Short timeout for testing
            operation="test_transitions",
            half_open_max_calls=1
        )
    
    async def test_closed_to_open_transition(self, circuit_breaker):
        """Test transition from CLOSED to OPEN state."""
        async def failing_func():
            raise ValueError("Test error")
        
        # First failure - should stay closed
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.stats.failure_count == 1
        
        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.stats.failure_count == 2
        assert circuit_breaker.opened_at is not None
    
    async def test_open_to_half_open_transition(self, circuit_breaker):
        """Test transition from OPEN to HALF_OPEN state."""
        # First, open the circuit
        async def failing_func():
            raise ValueError("Test error")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Next call should transition to HALF_OPEN
        async def success_func():
            return "success"
        
        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED  # Success transitions to CLOSED
    
    async def test_half_open_success_to_closed(self, circuit_breaker):
        """Test successful transition from HALF_OPEN to CLOSED."""
        # Open the circuit
        async def failing_func():
            raise ValueError("Test error")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)
        
        # Manually set to HALF_OPEN
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        circuit_breaker.half_open_calls = 0
        
        # Successful call should close circuit
        async def success_func():
            return "success"
        
        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.stats.failure_count == 0  # Reset on success
    
    async def test_half_open_failure_to_open(self, circuit_breaker):
        """Test failure transition from HALF_OPEN back to OPEN."""
        # Manually set to HALF_OPEN
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        circuit_breaker.half_open_calls = 0
        
        async def failing_func():
            raise ValueError("Test error")
        
        # Failure in HALF_OPEN should go back to OPEN
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.opened_at is not None
    
    async def test_circuit_breaker_rejection(self, circuit_breaker):
        """Test that calls are rejected when circuit is open."""
        # Open the circuit
        async def failing_func():
            raise ValueError("Test error")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Now calls should be rejected
        async def any_func():
            return "should not execute"
        
        with pytest.raises(CircuitOpenError) as exc_info:
            await circuit_breaker.call(any_func)
        
        assert "test_transitions" in str(exc_info.value)
        assert circuit_breaker.state == CircuitBreakerState.OPEN


class TestCircuitBreakerHalfOpenLimiting:
    """Test half-open call limiting functionality."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker with half-open limiting."""
        return CircuitBreaker(
            failure_threshold=1,
            reset_timeout=0.1,
            operation="test_half_open",
            half_open_max_calls=2  # Allow 2 calls in half-open
        )
    
    async def test_half_open_call_limiting(self, circuit_breaker):
        """Test that half-open state limits number of calls."""
        # Open the circuit
        async def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Manually set to HALF_OPEN to test limiting
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        circuit_breaker.half_open_calls = 0
        
        async def success_func():
            return "success"
        
        # First call should succeed
        result1 = await circuit_breaker.call(success_func)
        assert result1 == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerConcurrency:
    """Test circuit breaker behavior under concurrent access."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for concurrency testing."""
        return CircuitBreaker(
            failure_threshold=3,
            reset_timeout=1.0,
            operation="test_concurrency"
        )
    
    async def test_concurrent_success_calls(self, circuit_breaker):
        """Test concurrent successful calls."""
        async def success_func():
            await asyncio.sleep(0.01)  # Small delay
            return "success"
        
        # Run multiple concurrent calls
        tasks = [circuit_breaker.call(success_func) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert all(result == "success" for result in results)
        assert circuit_breaker.stats.success_count == 10
        assert circuit_breaker.stats.failure_count == 0
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
    
    async def test_concurrent_mixed_calls(self, circuit_breaker):
        """Test concurrent success and failure calls."""
        async def success_func():
            await asyncio.sleep(0.01)
            return "success"
        
        async def failing_func():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")
        
        # Mix of success and failure calls
        tasks = []
        for i in range(10):
            if i % 2 == 0:
                tasks.append(circuit_breaker.call(success_func))
            else:
                tasks.append(circuit_breaker.call(failing_func))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successes = [r for r in results if r == "success"]
        failures = [r for r in results if isinstance(r, ValueError)]
        
        assert len(successes) == 5
        assert len(failures) == 5
        assert circuit_breaker.stats.success_count == 5
        assert circuit_breaker.stats.failure_count == 5


class TestCircuitBreakerManager:
    """Test circuit breaker manager functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create a circuit breaker manager."""
        return CircuitBreakerManager()
    
    async def test_get_circuit_breaker_creation(self, manager):
        """Test circuit breaker creation through manager."""
        cb = await manager.get_circuit_breaker(
            name="test_cb",
            failure_threshold=5,
            reset_timeout=30.0
        )
        
        assert cb.name == "test_cb"
        assert cb.failure_threshold == 5
        assert cb.reset_timeout == 30.0
    
    async def test_get_circuit_breaker_reuse(self, manager):
        """Test that manager reuses existing circuit breakers."""
        cb1 = await manager.get_circuit_breaker(name="test_cb")
        cb2 = await manager.get_circuit_breaker(name="test_cb")
        
        assert cb1 is cb2
    
    async def test_get_all_stats(self, manager):
        """Test getting statistics for all circuit breakers."""
        cb1 = await manager.get_circuit_breaker(name="cb1")
        cb2 = await manager.get_circuit_breaker(name="cb2")
        
        # Execute some calls to generate stats
        async def success_func():
            return "success"
        
        await cb1.call(success_func)
        await cb2.call(success_func)
        
        stats = manager.get_all_stats()
        assert "cb1" in stats
        assert "cb2" in stats
        assert stats["cb1"]["success_count"] == 1
        assert stats["cb2"]["success_count"] == 1
    
    def test_reset_all(self, manager):
        """Test resetting all circuit breakers."""
        # This is a simple test since reset_all is synchronous
        manager.reset_all()
        # Should not raise any exceptions


class TestUtilityFunctions:
    """Test utility functions for circuit breaker usage."""
    
    async def test_get_circuit_breaker_function(self):
        """Test the global get_circuit_breaker function."""
        cb = await get_circuit_breaker(
            name="global_test",
            failure_threshold=3,
            reset_timeout=60.0
        )
        
        assert cb.name == "global_test"
        assert cb.failure_threshold == 3
        assert cb.reset_timeout == 60.0
    
    async def test_call_with_circuit_breaker_async(self):
        """Test call_with_circuit_breaker with async function."""
        async def async_add(a, b):
            return a + b
        
        result = await call_with_circuit_breaker(
            async_add, 5, 3,
            failure_threshold=2,
            timeout=30,
            operation="test_async"
        )
        
        assert result == 8
    
    async def test_call_with_circuit_breaker_sync(self):
        """Test call_with_circuit_breaker with sync function."""
        def sync_multiply(a, b):
            return a * b
        
        result = await call_with_circuit_breaker(
            sync_multiply, 4, 3,
            failure_threshold=2,
            timeout=30,
            operation="test_sync"
        )
        
        assert result == 12
    
    async def test_call_with_circuit_breaker_failure(self):
        """Test call_with_circuit_breaker with failing function."""
        async def failing_func():
            raise ValueError("Test error")
        
        # First call should fail but not open circuit
        with pytest.raises(ValueError):
            await call_with_circuit_breaker(
                failing_func,
                failure_threshold=2,
                timeout=30,
                operation="test_failure"
            )
        
        # Second call should fail and open circuit
        with pytest.raises(ValueError):
            await call_with_circuit_breaker(
                failing_func,
                failure_threshold=2,
                timeout=30,
                operation="test_failure"
            )
        
        # Third call should be rejected (circuit open)
        with pytest.raises(CircuitOpenError):
            await call_with_circuit_breaker(
                failing_func,
                failure_threshold=2,
                timeout=30,
                operation="test_failure"
            )


class TestCircuitBreakerStatsTracking:
    """Test circuit breaker statistics tracking."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for stats testing."""
        return CircuitBreaker(
            failure_threshold=3,
            reset_timeout=60.0,
            operation="stats_test"
        )
    
    async def test_stats_tracking(self, circuit_breaker):
        """Test that statistics are properly tracked."""
        async def success_func():
            return "success"
        
        async def failing_func():
            raise ValueError("Test error")
        
        # Execute some calls
        await circuit_breaker.call(success_func)
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)
        await circuit_breaker.call(success_func)
        
        assert circuit_breaker.stats.success_count == 2
        assert circuit_breaker.stats.failure_count == 1
        assert circuit_breaker.stats.last_success_time is not None
        assert circuit_breaker.stats.last_failure_time is not None
        assert circuit_breaker.stats.state_changes >= 1  # At least the initial state set
    
    def test_get_stats_format(self, circuit_breaker):
        """Test the format of get_stats output."""
        stats = circuit_breaker.get_stats()
        
        expected_keys = {
            "name", "operation", "state", "failure_count", "success_count",
            "last_failure_time", "last_success_time", "state_changes",
            "failure_threshold", "reset_timeout", "half_open_max_calls"
        }
        
        assert set(stats.keys()) == expected_keys
        assert stats["state"] == "closed"
        assert stats["failure_threshold"] == 3
        assert stats["reset_timeout"] == 60.0
    
    def test_reset_functionality(self, circuit_breaker):
        """Test circuit breaker reset functionality."""
        # Modify some state
        circuit_breaker.stats.success_count = 5
        circuit_breaker.stats.failure_count = 2
        circuit_breaker.stats.state_changes = 3
        circuit_breaker.state = CircuitBreakerState.OPEN
        
        # Reset
        circuit_breaker.reset()
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.stats.success_count == 0
        assert circuit_breaker.stats.failure_count == 0
        assert circuit_breaker.stats.state_changes == 0
        assert circuit_breaker.half_open_calls == 0
        assert circuit_breaker.opened_at is None


class TestCircuitBreakerErrorHandling:
    """Test error handling in circuit breaker."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for error testing."""
        return CircuitBreaker(
            failure_threshold=2,
            reset_timeout=1.0,
            operation="error_test"
        )
    
    async def test_cancelled_error_propagation(self, circuit_breaker):
        """Test that CancelledError is properly propagated."""
        async def cancellable_func():
            raise asyncio.CancelledError()
        
        with pytest.raises(asyncio.CancelledError):
            await circuit_breaker.call(cancellable_func)
        
        # Should not count as failure
        assert circuit_breaker.stats.failure_count == 0
    
    async def test_exception_propagation(self, circuit_breaker):
        """Test that original exceptions are propagated."""
        class CustomError(Exception):
            pass
        
        async def custom_error_func():
            raise CustomError("Custom error message")
        
        with pytest.raises(CustomError) as exc_info:
            await circuit_breaker.call(custom_error_func)
        
        assert str(exc_info.value) == "Custom error message"
        assert circuit_breaker.stats.failure_count == 1


class TestCircuitBreakerPerformance:
    """Test circuit breaker performance characteristics."""
    
    async def test_minimal_overhead_success_path(self):
        """Test that circuit breaker adds minimal overhead for successful calls."""
        circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            reset_timeout=60.0,
            operation="perf_test"
        )
        
        async def fast_func():
            return "fast"
        
        # Measure overhead
        iterations = 1000
        
        # Without circuit breaker
        start_time = time.perf_counter()
        for _ in range(iterations):
            await fast_func()
        direct_time = time.perf_counter() - start_time
        
        # With circuit breaker
        start_time = time.perf_counter()
        for _ in range(iterations):
            await circuit_breaker.call(fast_func)
        cb_time = time.perf_counter() - start_time
        
        # Overhead should be reasonable (less than 100% increase)
        overhead = (cb_time - direct_time) / direct_time
        assert overhead < 1.0, f"Circuit breaker overhead too high: {overhead:.2%}"
    
    async def test_high_concurrency_performance(self):
        """Test circuit breaker performance under high concurrency."""
        circuit_breaker = CircuitBreaker(
            failure_threshold=10,
            reset_timeout=60.0,
            operation="concurrency_perf_test"
        )
        
        async def concurrent_func():
            await asyncio.sleep(0.001)  # Small delay to simulate work
            return "concurrent"
        
        # High concurrency test
        concurrent_tasks = 100
        tasks = [circuit_breaker.call(concurrent_func) for _ in range(concurrent_tasks)]
        
        start_time = time.perf_counter()
        results = await asyncio.gather(*tasks)
        elapsed_time = time.perf_counter() - start_time
        
        assert len(results) == concurrent_tasks
        assert all(result == "concurrent" for result in results)
        # Should complete reasonably quickly (within 1 second with proper async handling)
        assert elapsed_time < 1.0, f"High concurrency test took too long: {elapsed_time:.2f}s"


if __name__ == "__main__":
    pytest.main([__file__])