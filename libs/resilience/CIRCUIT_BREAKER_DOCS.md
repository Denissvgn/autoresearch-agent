# Enhanced Circuit Breaker Library

This library provides an enhanced circuit breaker implementation for the TRAID platform, designed to prevent cascade failures by monitoring service call success/failure rates and temporarily blocking calls when failure thresholds are exceeded.

## Features

- **Three States**: CLOSED (normal operation), OPEN (failing, calls blocked), HALF_OPEN (testing recovery)
- **Async Support**: Full async/await support with proper concurrency handling
- **Thread Safety**: Uses asyncio.Lock for safe concurrent access
- **Comprehensive Statistics**: Tracks success/failure counts, timing, and state changes
- **Metrics Integration**: Prometheus metrics emission with fallback support
- **Half-Open Limiting**: Configurable number of trial calls in half-open state
- **Manager Pattern**: Global manager for multiple circuit breakers
- **Flexible API**: Both object-oriented and functional interfaces

## Quick Start

### Basic Usage

```python
from resilience.breaker import CircuitBreaker, call_with_circuit_breaker

# Object-oriented approach
circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    reset_timeout=60.0,
    operation="my_service",
    half_open_max_calls=1
)

async def risky_operation():
    # Your potentially failing operation
    return await some_external_service_call()

# Use the circuit breaker
try:
    result = await circuit_breaker.call(risky_operation)
    print(f"Success: {result}")
except CircuitOpenError:
    print("Circuit breaker is open - calls are being blocked")
except Exception as e:
    print(f"Operation failed: {e}")
```

### Functional Approach

```python
from resilience.breaker import call_with_circuit_breaker

async def my_service_call(param1, param2):
    # Your service call logic
    return f"Result for {param1}, {param2}"

# Use functional interface
result = await call_with_circuit_breaker(
    my_service_call,
    "value1", "value2",  # function arguments
    failure_threshold=3,
    timeout=30,
    operation="my_service"
)
```

## Configuration Parameters

### CircuitBreaker Parameters

- **failure_threshold** (int): Number of consecutive failures before opening circuit (default: 5)
- **reset_timeout** (float): Seconds to wait before attempting recovery (default: 60.0)
- **operation** (str): Operation name for metrics and logging (default: "default")
- **half_open_max_calls** (int): Maximum calls allowed in half-open state (default: 1)
- **name** (str, optional): Circuit breaker identifier (defaults to operation)

### call_with_circuit_breaker Parameters

- **func** (Callable): Function to execute (can be sync or async)
- ***args**: Function arguments
- **failure_threshold** (int): Number of failures before opening circuit (default: 5)
- **timeout** (int): Seconds to wait before attempting recovery (default: 60)
- **half_open_requests** (int): Max calls allowed in half-open state (default: 1)
- **operation** (str): Operation name for metrics and logging (default: "default")
- ****kwargs**: Function keyword arguments

## State Transitions

```
CLOSED ──failure_threshold──> OPEN
  ↑                              │
  │                              │ reset_timeout
  │                              ↓
  └──── success ←─────── HALF_OPEN
```

### State Descriptions

1. **CLOSED**: Normal operation, all calls are allowed
2. **OPEN**: Circuit is open, all calls are rejected immediately
3. **HALF_OPEN**: Testing phase, limited number of calls allowed to test recovery

## Statistics and Monitoring

### Get Circuit Breaker Statistics

```python
stats = circuit_breaker.get_stats()
print(f"State: {stats['state']}")
print(f"Failures: {stats['failure_count']}")
print(f"Successes: {stats['success_count']}")
print(f"State changes: {stats['state_changes']}")
```

### Statistics Fields

- **name**: Circuit breaker identifier
- **operation**: Operation name
- **state**: Current state (closed/open/half_open)
- **failure_count**: Number of failures
- **success_count**: Number of successes
- **last_failure_time**: Timestamp of last failure
- **last_success_time**: Timestamp of last success
- **state_changes**: Number of state transitions
- **failure_threshold**: Configured failure threshold
- **reset_timeout**: Configured reset timeout
- **half_open_max_calls**: Configured half-open call limit

## Metrics Integration

The circuit breaker automatically emits Prometheus metrics:

### Metrics Emitted

- **circuit_breaker_state**: Current state as gauge (0=closed, 1=open, 2=half_open)
- **circuit_breaker_state_changes_total**: Total state changes counter
- **circuit_breaker_failures_total**: Total failures counter
- **circuit_breaker_successes_total**: Total successes counter
- **circuit_breaker_rejections_total**: Total rejections counter

All metrics include the `operation` label for filtering and aggregation.

### Grafana Dashboard Queries

```promql
# Circuit breaker state over time
circuit_breaker_state{operation="my_service"}

# Failure rate
rate(circuit_breaker_failures_total{operation="my_service"}[5m])

# Success rate
rate(circuit_breaker_successes_total{operation="my_service"}[5m])

# Rejection rate (when circuit is open)
rate(circuit_breaker_rejections_total{operation="my_service"}[5m])
```

## Advanced Usage

### Using Circuit Breaker Manager

```python
from resilience.breaker import get_circuit_breaker

# Get or create a circuit breaker
cb = await get_circuit_breaker(
    name="external_api",
    failure_threshold=3,
    reset_timeout=30.0
)

# Use the circuit breaker
result = await cb.call(my_external_api_call)
```

### Error Handling

```python
from resilience.exceptions import CircuitOpenError

try:
    result = await circuit_breaker.call(risky_operation)
except CircuitOpenError:
    # Circuit is open, handle gracefully
    result = get_cached_result()
except ValueError as e:
    # Original function error
    log.error(f"Operation failed: {e}")
    raise
except Exception as e:
    # Unexpected error
    log.error(f"Unexpected error: {e}")
    raise
```

### Resetting Circuit Breakers

```python
# Reset single circuit breaker
circuit_breaker.reset()

# Reset all circuit breakers via manager
from resilience.breaker import _circuit_breaker_manager
_circuit_breaker_manager.reset_all()
```

## Integration Examples

### HTTP Client Integration

```python
import httpx
from resilience.breaker import CircuitBreaker

class ResilientHttpClient:
    def __init__(self, base_url: str):
        self.client = httpx.AsyncClient(base_url=base_url)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            reset_timeout=60.0,
            operation=f"http_client_{base_url}"
        )
    
    async def get(self, path: str) -> httpx.Response:
        async def http_call():
            response = await self.client.get(path)
            response.raise_for_status()
            return response
        
        return await self.circuit_breaker.call(http_call)
```

### Database Connection Integration

```python
from resilience.breaker import call_with_circuit_breaker

async def get_user_by_id(user_id: int):
    async def db_query():
        async with database.connection() as conn:
            return await conn.fetch_one(
                "SELECT * FROM users WHERE id = $1", user_id
            )
    
    return await call_with_circuit_breaker(
        db_query,
        failure_threshold=3,
        timeout=30,
        operation="database_user_query"
    )
```

### Microservice Call Integration

```python
from resilience.breaker import get_circuit_breaker

class UserService:
    def __init__(self):
        self.circuit_breaker = None
    
    async def _get_circuit_breaker(self):
        if not self.circuit_breaker:
            self.circuit_breaker = await get_circuit_breaker(
                name="user_service",
                failure_threshold=5,
                reset_timeout=120.0,
                half_open_max_calls=2
            )
        return self.circuit_breaker
    
    async def get_user_profile(self, user_id: str):
        cb = await self._get_circuit_breaker()
        
        async def fetch_profile():
            async with httpx.AsyncClient() as client:
                response = await client.get(f"/users/{user_id}")
                response.raise_for_status()
                return response.json()
        
        return await cb.call(fetch_profile)
```

## Best Practices

### 1. Choose Appropriate Thresholds

- **Failure Threshold**: Start with 5-10 failures for most services
- **Reset Timeout**: 30-120 seconds depending on service recovery time
- **Half-Open Calls**: 1-3 calls for most cases

### 2. Operation Naming

Use descriptive operation names that help with monitoring:

```python
# Good
operation="external_payment_api"
operation="database_user_queries"
operation="inference_model_predictions"

# Avoid
operation="api"
operation="db"
operation="service"
```

### 3. Error Handling Strategy

```python
try:
    result = await circuit_breaker.call(operation)
    return result
except CircuitOpenError:
    # Circuit is open - use fallback
    return get_fallback_result()
except SpecificServiceError:
    # Handle known service errors
    log.warning("Service returned expected error")
    raise
except Exception:
    # Unexpected errors will be counted as failures
    log.error("Unexpected error in operation")
    raise
```

### 4. Monitoring and Alerting

Set up alerts for:
- Circuit breaker state changes
- High failure rates
- Sustained open states
- Rapid state oscillations

### 5. Testing Circuit Breaker Behavior

```python
import pytest
from resilience.breaker import CircuitBreaker
from resilience.exceptions import CircuitOpenError

@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_failures():
    cb = CircuitBreaker(failure_threshold=2, reset_timeout=1.0)
    
    async def failing_operation():
        raise ValueError("Test failure")
    
    # First failure
    with pytest.raises(ValueError):
        await cb.call(failing_operation)
    assert cb.state == CircuitBreakerState.CLOSED
    
    # Second failure - should open circuit
    with pytest.raises(ValueError):
        await cb.call(failing_operation)
    assert cb.state == CircuitBreakerState.OPEN
    
    # Third call should be rejected
    with pytest.raises(CircuitOpenError):
        await cb.call(failing_operation)
```

## Performance Considerations

- Circuit breaker adds minimal overhead (~1-5ms) to successful calls
- Uses asyncio.Lock which is efficient for async operations
- Metrics emission is non-blocking with exception handling
- Memory usage scales with number of circuit breakers (not calls)

## Troubleshooting

### Common Issues

1. **Circuit opens too frequently**
   - Increase failure_threshold
   - Check if errors are expected (don't count as failures)
   - Verify service stability

2. **Circuit doesn't open when it should**
   - Check failure_threshold setting
   - Verify exceptions are being raised (not returning error values)
   - Check if CancelledError is being raised (doesn't count as failure)

3. **Circuit stays open too long**
   - Decrease reset_timeout
   - Increase half_open_max_calls for faster recovery testing

4. **Metrics not appearing**
   - Verify Prometheus client is installed
   - Check metric export configuration
   - Look for metric emission errors in logs

### Debug Logging

Enable debug logging to see circuit breaker state changes:

```python
import logging
logging.getLogger("resilience.breaker").setLevel(logging.DEBUG)
```

## Migration from Inference Service Circuit Breaker

If migrating from the inference service's custom circuit breaker:

### Old Code
```python
from utils.circuit_breaker import CircuitBreaker, get_circuit_breaker

cb = get_circuit_breaker("my_service", failure_threshold=5)
result = await cb.call(my_function, arg1, arg2)
```

### New Code
```python
from resilience.breaker import get_circuit_breaker

cb = await get_circuit_breaker("my_service", failure_threshold=5)
result = await cb.call_with_args(my_function, arg1, arg2)
```

### Key Differences

1. **Async Manager**: `get_circuit_breaker()` is now async
2. **Method Names**: Use `call_with_args()` for functions with arguments
3. **Enum States**: States are now enum values, not strings
4. **Enhanced Metrics**: More comprehensive metrics are available
5. **Better Concurrency**: Improved async safety with proper locking

## API Reference

### Classes

#### CircuitBreaker
```python
@dataclass
class CircuitBreaker:
    failure_threshold: int
    reset_timeout: float
    operation: str = "default"
    half_open_max_calls: int = 1
    name: Optional[str] = None
```

#### CircuitBreakerManager
```python
class CircuitBreakerManager:
    async def get_circuit_breaker(self, name: str, **kwargs) -> CircuitBreaker
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]
    def reset_all(self) -> None
```

### Functions

#### call_with_circuit_breaker
```python
async def call_with_circuit_breaker(
    func: Callable,
    *args,
    failure_threshold: int = 5,
    timeout: int = 60,
    half_open_requests: int = 1,
    operation: str = "default",
    **kwargs
) -> Any
```

#### get_circuit_breaker
```python
async def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker
```

### Exceptions

#### CircuitOpenError
```python
class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and execution is blocked."""
```