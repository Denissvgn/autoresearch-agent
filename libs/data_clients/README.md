# Data Clients Library

A comprehensive async client library for indicator and feature service communication in the Traid platform.

## Features

- 🚀 **Async HTTP Client** - High-performance async requests with httpx
- 🔄 **Retry Logic** - Automatic retry with exponential backoff
- 🛡️ **Circuit Breaker** - Fault tolerance and service protection
- 📦 **Response Caching** - Redis-based caching with TTL
- ✅ **Type Safety** - Full Pydantic validation throughout
- 📊 **Performance Monitoring** - Built-in metrics and debug logging
- 🔀 **Service Fallback** - Automatic failover between services

## Quick Start

```python
import asyncio
from data_clients import IndicatorClient, OHLCVData, IndicatorSpec

async def main():
    # Initialize client
    # Note: indicator-service has been archived; use feature-service instead
    client = IndicatorClient(
        base_url="http://feature-service:8000",  # Updated to use feature-service
        feature_service_url="http://feature-service:8000",
        circuit_breaker_enabled=True,
        debug=True
    )
    
    # Prepare data
    ohlcv_data = [
        OHLCVData(
            open=50000.0, high=51000.0, low=49000.0, 
            close=50500.0, volume=1000.0,
            timestamp=datetime.now()
        )
    ]
    
    indicators = [
        IndicatorSpec(indicator_type="SMA", period=20),
        IndicatorSpec(indicator_type="RSI", period=14)
    ]
    
    # Compute indicators
    response = await client.compute_indicators(
        symbol="BTCUSD",
        exchange="binance", 
        ohlcv_data=ohlcv_data,
        indicators=indicators
    )
    
    print(f"SMA values: {response.results[0].values}")
    print(f"RSI values: {response.results[1].values}")

asyncio.run(main())
```

## Configuration

### Basic Client Setup

```python
from data_clients import IndicatorClient
import redis.asyncio as redis

# With Redis caching
cache_client = redis.Redis(host="localhost", port=6379, db=0)

client = IndicatorClient(
    base_url="http://feature-service:8000",  # Updated: indicator-service archived
    feature_service_url="http://feature-service:8000",
    timeout=30.0,
    cache_client=cache_client,
    cache_ttl=300,  # 5 minutes
    circuit_breaker_enabled=True,
    circuit_breaker_threshold=5,
    circuit_breaker_timeout=60,
    prefer_feature_service=False,
    debug=True
)
```

### Circuit Breaker Configuration

```python
# Enable circuit breaker with custom settings
client = IndicatorClient(
    base_url="http://feature-service:8000",  # Updated: use feature-service
    circuit_breaker_enabled=True,
    circuit_breaker_threshold=3,  # Open after 3 failures
    circuit_breaker_timeout=30    # Wait 30s before retry
)
```

## API Reference

### IndicatorClient

#### Core Methods

```python
# Compute multiple indicators
async def compute_indicators(
    symbol: str,
    exchange: str, 
    ohlcv_data: List[OHLCVData],
    indicators: List[IndicatorSpec],
    use_cache: bool = True
) -> IndicatorResponse

# Calculate single indicator
async def calculate_single(
    symbol: str,
    timeframe: str,
    indicators: List[str],
    data: Dict[str, Any]
) -> IndicatorResponse

# Health check
async def health_check() -> Dict[str, Any]
```

#### Utility Functions

```python
from data_clients import compute_indicators, calculate_single

# Utility functions for quick operations
response = await compute_indicators(
    client, symbol, exchange, ohlcv_data, indicators
)

result = await calculate_single(
    client, symbol, timeframe, ["sma"], {"prices": [100, 101, 102]}
)
```

### Data Models

#### OHLCVData
```python
from data_clients import OHLCVData
from datetime import datetime

ohlcv = OHLCVData(
    open=50000.0,
    high=51000.0, 
    low=49000.0,
    close=50500.0,
    volume=1000.0,
    timestamp=datetime.now()
)
```

#### IndicatorSpec
```python
from data_clients import IndicatorSpec

# Simple moving average
sma = IndicatorSpec(indicator_type="SMA", period=20)

# Bollinger bands with custom parameters  
bb = IndicatorSpec(
    indicator_type="BOLLINGER",
    period=20,
    nbdevup=2.0,
    nbdevdn=2.0
)

# MACD with periods
macd = IndicatorSpec(
    indicator_type="MACD",
    fastperiod=12,
    slowperiod=26, 
    signalperiod=9
)
```

## Error Handling

The client provides structured error handling:

```python
from data_clients import (
    IndicatorClientError,
    IndicatorServiceError, 
    IndicatorTimeoutError,
    CircuitBreakerOpenError
)

try:
    response = await client.compute_indicators(...)
except IndicatorServiceError as e:
    print(f"Service error: {e.status_code} - {e.message}")
except IndicatorTimeoutError as e:
    print(f"Request timeout: {e}")
except CircuitBreakerOpenError as e:
    print(f"Circuit breaker open: {e}")
except IndicatorClientError as e:
    print(f"Client error: {e}")
```

## Caching

The client supports Redis-based caching:

```python
# Cache configuration
client = IndicatorClient(
    base_url="http://feature-service:8000",  # Updated: use feature-service
    cache_client=redis_client,
    cache_ttl=300,  # 5 minutes
    enable_cache=True
)

# Cache operations
await client.compute_indicators(..., use_cache=True)  # Use cache
await client.compute_indicators(..., use_cache=False)  # Skip cache
```

## Performance Monitoring

```python
# Get client performance metrics
metrics = client.get_performance_metrics()
print(f"Total requests: {metrics['total_requests']}")
print(f"Success rate: {metrics['success_rate']}")
print(f"Average response time: {metrics['avg_response_time']}")
print(f"Circuit breaker state: {metrics['circuit_breaker_state']}")
```

## Logging

Configure structured logging:

```python
import structlog

# Enable debug logging
client = IndicatorClient(
    base_url="http://feature-service:8000",  # Updated: use feature-service
    debug=True
)

# The client logs:
# - Request details (method, URL, data)
# - Response status and timing
# - Cache hits/misses
# - Circuit breaker state changes
# - Error details
```

## Testing

```python
import pytest
from unittest.mock import AsyncMock
from data_clients import IndicatorClient

@pytest.fixture
async def client():
    mock_redis = AsyncMock()
    return IndicatorClient(
        base_url="http://test:8000",
        cache_client=mock_redis,
        circuit_breaker_enabled=False
    )

@pytest.mark.asyncio
async def test_compute_indicators(client):
    # Test implementation
    pass
```

## Installation

```bash
# Install from local directory
pip install -e libs/data_clients

# With dependencies
pip install -e "libs/data_clients[dev]"
```

## Development

```bash
# Run tests
cd libs/data_clients
pytest tests/ -v

# Type checking
mypy data_clients/

# Code formatting
black data_clients/
ruff data_clients/
```

## Examples

### Basic Usage
```python
from data_clients import IndicatorClient, OHLCVData, IndicatorSpec

client = IndicatorClient(base_url="http://localhost:8000")

# Compute SMA
response = await client.compute_indicators(
    symbol="BTCUSD",
    exchange="binance",
    ohlcv_data=[...],
    indicators=[IndicatorSpec(indicator_type="SMA", period=20)]
)
```

### Batch Processing
```python
symbols = ["BTCUSD", "ETHUSD", "ADAUSD"]
results = []

for symbol in symbols:
    response = await client.compute_indicators(
        symbol=symbol,
        exchange="binance", 
        ohlcv_data=ohlcv_data,
        indicators=indicators
    )
    results.append(response)
```

### Error Recovery
```python
from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3))
async def compute_with_retry(client, symbol, ohlcv_data, indicators):
    return await client.compute_indicators(
        symbol=symbol,
        exchange="binance",
        ohlcv_data=ohlcv_data, 
        indicators=indicators
    )
```

## License

MIT License - see LICENSE file for details.
