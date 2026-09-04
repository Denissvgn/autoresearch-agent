# Circuit Breaker Migration Guide

## Migration from Inference Service Circuit Breaker

This guide helps migrate from the custom circuit breaker in `services/ml/inference-service/src/utils/circuit_breaker.py` to the shared enhanced circuit breaker in `libs/resilience/resilience/breaker.py`.

## Key Changes

### 1. Import Changes

**Old:**
```python
from utils.circuit_breaker import CircuitBreaker, get_circuit_breaker, circuit_breaker_manager
```

**New:**
```python
from libs.resilience import CircuitBreaker, get_circuit_breaker
# or
from resilience.breaker import CircuitBreaker, get_circuit_breaker
```

### 2. Manager Usage

**Old:**
```python
cb = get_circuit_breaker("my_service", failure_threshold=5)
```

**New:**
```python
cb = await get_circuit_breaker("my_service", failure_threshold=5)
```

### 3. Function Calls with Arguments

**Old:**
```python
result = await cb.call(my_func, arg1, arg2, keyword=value)
```

**New:**
```python
result = await cb.call_with_args(my_func, arg1, arg2, keyword=value)
```

### 4. State Checking

**Old:**
```python
if cb.state == "open":
    # handle open state
```

**New:**
```python
from resilience.breaker import CircuitBreakerState

if cb.state == CircuitBreakerState.OPEN:
    # handle open state
```

### 5. Exception Handling

**Old:**
```python
from utils.circuit_breaker import CircuitBreakerOpenError
```

**New:**
```python
from resilience.exceptions import CircuitOpenError
```

## Step-by-Step Migration

### Step 1: Update Imports

Replace all circuit breaker imports:

```python
# Remove this
from utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    get_circuit_breaker,
    circuit_breaker_manager
)

# Add this
from resilience.breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    get_circuit_breaker,
    call_with_circuit_breaker
)
from resilience.exceptions import CircuitOpenError
```

### Step 2: Update Circuit Breaker Creation

**Old pattern:**
```python
def get_my_circuit_breaker():
    return get_circuit_breaker(
        "inference_service",
        failure_threshold=5,
        timeout=60,
        half_open_max_calls=3
    )
```

**New pattern:**
```python
async def get_my_circuit_breaker():
    return await get_circuit_breaker(
        name="inference_service",
        failure_threshold=5,
        reset_timeout=60.0,
        half_open_max_calls=3
    )
```

### Step 3: Update Call Sites

**Old pattern:**
```python
async def predict_with_circuit_breaker(data):
    cb = get_circuit_breaker("prediction")
    return await cb.call(prediction_service.predict, data)
```

**New pattern:**
```python
async def predict_with_circuit_breaker(data):
    cb = await get_circuit_breaker("prediction")
    return await cb.call_with_args(prediction_service.predict, data)
```

### Step 4: Update Exception Handling

**Old pattern:**
```python
try:
    result = await cb.call(operation)
except CircuitBreakerOpenError:
    return get_fallback_result()
```

**New pattern:**
```python
try:
    result = await cb.call(operation)
except CircuitOpenError:
    return get_fallback_result()
```

### Step 5: Update State Checks

**Old pattern:**
```python
if circuit_breaker.state == "open":
    log.warning("Circuit breaker is open")
```

**New pattern:**
```python
if circuit_breaker.state == CircuitBreakerState.OPEN:
    log.warning("Circuit breaker is open")
```

## Complete Example

### Before Migration

```python
from utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, get_circuit_breaker

class InferenceService:
    def __init__(self):
        self.circuit_breaker = get_circuit_breaker(
            "inference",
            failure_threshold=5,
            timeout=60
        )
    
    async def predict(self, input_data):
        try:
            return await self.circuit_breaker.call(
                self._internal_predict, 
                input_data
            )
        except CircuitBreakerOpenError:
            return {"error": "Service temporarily unavailable"}
    
    def get_status(self):
        return {
            "circuit_state": self.circuit_breaker.state,
            "stats": self.circuit_breaker.get_stats()
        }
```

### After Migration

```python
from resilience.breaker import CircuitBreaker, CircuitBreakerState, get_circuit_breaker
from resilience.exceptions import CircuitOpenError

class InferenceService:
    def __init__(self):
        self.circuit_breaker = None
    
    async def _get_circuit_breaker(self):
        if not self.circuit_breaker:
            self.circuit_breaker = await get_circuit_breaker(
                name="inference",
                failure_threshold=5,
                reset_timeout=60.0
            )
        return self.circuit_breaker
    
    async def predict(self, input_data):
        cb = await self._get_circuit_breaker()
        try:
            return await cb.call_with_args(
                self._internal_predict, 
                input_data
            )
        except CircuitOpenError:
            return {"error": "Service temporarily unavailable"}
    
    async def get_status(self):
        cb = await self._get_circuit_breaker()
        return {
            "circuit_state": cb.state.value,  # Convert enum to string
            "stats": cb.get_stats()
        }
```

## Testing Migration

### Unit Test Updates

**Old test:**
```python
def test_circuit_breaker_opens():
    cb = get_circuit_breaker("test")
    # ... test logic
    assert cb.state == "open"
```

**New test:**
```python
@pytest.mark.asyncio
async def test_circuit_breaker_opens():
    cb = await get_circuit_breaker("test")
    # ... test logic
    assert cb.state == CircuitBreakerState.OPEN
```

### Integration Test Updates

Make sure to:
1. Add `@pytest.mark.asyncio` to async tests
2. Use `await get_circuit_breaker()` instead of direct call
3. Update state comparisons to use enum values
4. Update exception class names

## Rollback Plan

If you need to rollback:

1. Keep the old circuit breaker code in place
2. Use feature flags to switch between implementations:

```python
import os
from typing import Union

if os.getenv("USE_ENHANCED_CIRCUIT_BREAKER", "false").lower() == "true":
    from resilience.breaker import get_circuit_breaker as _get_cb
    
    async def get_circuit_breaker(name, **kwargs):
        return await _get_cb(name, **kwargs)
else:
    from utils.circuit_breaker import get_circuit_breaker

# Use get_circuit_breaker() as normal
```

## Benefits of Migration

1. **Enhanced Metrics**: More comprehensive Prometheus metrics
2. **Better Async Safety**: Proper locking for concurrent access
3. **Improved Testing**: Better test coverage and reliability
4. **Standardization**: Consistent interface across all services
5. **Performance**: Optimized for high-concurrency scenarios
6. **Maintainability**: Centralized maintenance and updates

## Common Issues and Solutions

### Issue: "AttributeError: 'coroutine' object has no attribute 'call'"

**Cause:** Forgot to await `get_circuit_breaker()`

**Solution:**
```python
# Wrong
cb = get_circuit_breaker("test")

# Correct
cb = await get_circuit_breaker("test")
```

### Issue: "TypeError: 'CircuitBreakerState' object is not subscriptable"

**Cause:** Trying to compare state with string

**Solution:**
```python
# Wrong
if cb.state == "open":

# Correct
if cb.state == CircuitBreakerState.OPEN:
```

### Issue: "AttributeError: 'CircuitBreaker' object has no attribute 'call'"

**Cause:** Using old call pattern with arguments

**Solution:**
```python
# Wrong
await cb.call(func, arg1, arg2)

# Correct
await cb.call_with_args(func, arg1, arg2)
```

## Verification Steps

After migration, verify:

1. All tests pass
2. Metrics are being emitted correctly
3. Circuit breaker state transitions work as expected
4. Performance is maintained or improved
5. Error handling works correctly

## Support

For questions or issues during migration:
- Check the comprehensive documentation in `CIRCUIT_BREAKER_DOCS.md`
- Review test examples in `tests/test_enhanced_circuit_breaker.py`
- Consult the implementation in `resilience/breaker.py`