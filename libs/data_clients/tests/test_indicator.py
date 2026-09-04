"""
Comprehensive test suite for the Indicator Client.

Tests cover:
- Model validation and serialization
- HTTP client functionality with mocking
- Circuit breaker behavior
- Caching mechanisms
- Error handling and retry logic
- Real-world integration scenarios
"""

import asyncio
from datetime import datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from redis.asyncio import Redis
import respx

from data_clients.indicator import (  # Models; Client; Exceptions; Utilities
    OHLCV,
    CircuitBreaker,
    CircuitBreakerOpenError,
    IndicatorClient,
    IndicatorClientError,
    IndicatorRequest,
    IndicatorResponse,
    IndicatorServiceError,
    IndicatorSpec,
    IndicatorTimeoutError,
    calculate_single,
    compute_indicators,
    create_indicator_client,
)

# =============================================================================
# Test Data and Fixtures
# =============================================================================

@pytest.fixture
def sample_ohlcv():
    """Sample OHLCV data for testing."""
    return OHLCV(
        t=[1640995200, 1640995260, 1640995320, 1640995380, 1640995440],
        o=[50000.0, 50100.0, 50050.0, 50200.0, 50150.0],
        h=[50150.0, 50200.0, 50180.0, 50250.0, 50200.0],
        l=[49950.0, 50050.0, 50000.0, 50150.0, 50100.0],
        c=[50100.0, 50050.0, 50200.0, 50150.0, 50180.0],
        v=[100.5, 95.2, 110.8, 85.3, 102.7]
    )


@pytest.fixture
def sample_indicator_specs():
    """Sample indicator specifications."""
    return [
        IndicatorSpec(type="sma", period=20),
        IndicatorSpec(type="rsi", period=14),
        IndicatorSpec(type="bollinger", period=20, nbdevup=2.0, nbdevdn=2.0)
    ]


@pytest.fixture
def sample_indicator_request(sample_ohlcv, sample_indicator_specs):
    """Sample indicator request."""
    return IndicatorRequest(
        symbol="BTCUSDT",
        timeframe="1h",
        indicators=sample_indicator_specs,
        ohlcv=sample_ohlcv
    )


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock(spec=Redis)

    async def mock_get(key):
        return None

    async def mock_setex(key, ttl, value):
        return True

    redis_mock.get = AsyncMock(side_effect=mock_get)
    redis_mock.setex = AsyncMock(side_effect=mock_setex)
    return redis_mock


@pytest.fixture
def indicator_client(mock_redis):
    """Configured indicator client for testing."""
    return IndicatorClient(
        base_url="http://test-indicator:8000",
        feature_service_url="http://test-feature:8000",
        timeout=10.0,
        cache_client=mock_redis,
        circuit_breaker_enabled=False,  # Disable circuit breaker for most tests
        debug=True
    )


# =============================================================================
# Model Tests
# =============================================================================

class TestOHLCV:
    """Test OHLCV data model."""

    def test_valid_ohlcv_creation(self, sample_ohlcv):
        """Test creating valid OHLCV data."""
        assert len(sample_ohlcv.t) == 5
        assert len(sample_ohlcv.o) == 5
        assert sample_ohlcv.c[-1] == 50180.0

    def test_ohlcv_length_validation(self):
        """Test OHLCV length validation."""
        with pytest.raises(ValueError, match="same length"):
            OHLCV(
                t=[1, 2, 3],
                o=[1.0, 2.0],  # Different length
                h=[1.1, 2.1, 3.1],
                l=[0.9, 1.9, 2.9],
                c=[1.05, 2.05, 3.05],
                v=[100, 200, 300]
            )

    def test_ohlcv_from_dict(self):
        """Test creating OHLCV from dictionary."""
        data = {
            "timestamp": [1640995200, 1640995260],
            "open": [50000.0, 50100.0],
            "high": [50150.0, 50200.0],
            "low": [49950.0, 50050.0],
            "close": [50100.0, 50050.0],
            "volume": [100.5, 95.2]
        }

        ohlcv = OHLCV.from_dict(data)
        assert len(ohlcv.t) == 2
        assert ohlcv.o[0] == 50000.0

    def test_ohlcv_from_dict_flexible_keys(self):
        """Test OHLCV creation with flexible key names."""
        data = {
            "time": [1640995200],
            "opens": [50000.0],
            "highs": [50150.0],
            "lows": [49950.0],
            "closes": [50100.0],
            "volumes": [100.5]
        }

        ohlcv = OHLCV.from_dict(data)
        assert ohlcv.t[0] == 1640995200

    def test_ohlcv_from_dict_missing_key(self):
        """Test OHLCV creation with missing required key."""
        data = {
            "t": [1640995200],
            "o": [50000.0],
            # Missing other required keys
        }

        with pytest.raises(ValueError, match="Required key"):
            OHLCV.from_dict(data)


class TestIndicatorSpec:
    """Test indicator specification model."""

    def test_basic_indicator_spec(self):
        """Test basic indicator specification."""
        spec = IndicatorSpec(type="sma", period=20)
        assert spec.type == "sma"
        assert spec.period == 20

    def test_indicator_defaults(self):
        """Test that defaults are set based on indicator type."""
        spec = IndicatorSpec(type="bollinger")
        assert spec.period == 20
        assert spec.nbdevup == 2.0
        assert spec.nbdevdn == 2.0

    def test_macd_defaults(self):
        """Test MACD specific defaults."""
        spec = IndicatorSpec(type="macd")
        assert spec.fastperiod == 12
        assert spec.slowperiod == 26
        assert spec.signalperiod == 9

    def test_invalid_period(self):
        """Test invalid period validation."""
        with pytest.raises(ValueError):
            IndicatorSpec(type="sma", period=0)

        with pytest.raises(ValueError):
            IndicatorSpec(type="sma", period=300)  # Too large


class TestIndicatorRequest:
    """Test indicator request model."""

    def test_valid_request(self, sample_indicator_request):
        """Test valid indicator request."""
        assert sample_indicator_request.symbol == "BTCUSDT"
        assert sample_indicator_request.timeframe == "1h"
        assert len(sample_indicator_request.indicators) == 3
        assert sample_indicator_request.use_cache is True

    def test_empty_indicators_list(self, sample_ohlcv):
        """Test request with empty indicators list."""
        with pytest.raises(ValueError):
            IndicatorRequest(
                symbol="BTCUSDT",
                timeframe="1h",
                indicators=[],  # Empty list
                ohlcv=sample_ohlcv
            )


class TestIndicatorResponse:
    """Test indicator response model."""

    def test_basic_response(self):
        """Test basic response creation."""
        response = IndicatorResponse(
            symbol="BTCUSDT",
            timeframe="1h",
            results={"sma_20": [50100.0, 50125.0]},
            calculation_time=0.15
        )

        assert response.symbol == "BTCUSDT"
        assert response.cache_hit is False
        assert isinstance(response.timestamp, datetime)

    def test_response_serialization(self):
        """Test response serialization."""
        response = IndicatorResponse(
            symbol="BTCUSDT",
            timeframe="1h",
            results={"sma_20": [50100.0]},
        )

        data = response.model_dump(mode="json")
        assert "symbol" in data
        assert "results" in data
        assert "timestamp" in data


# =============================================================================
# Circuit Breaker Tests
# =============================================================================

class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        breaker = CircuitBreaker(failure_threshold=3)

        # Successful calls should work
        result = breaker.call(lambda x: x * 2, 5)
        assert result == 10
        assert breaker.state == "closed"

    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after failures."""
        breaker = CircuitBreaker(failure_threshold=2)

        # Cause failures
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call(lambda: (_ for _ in ()).throw(ValueError("test error")))

        assert breaker.state == "open"

    def test_circuit_breaker_open_state_blocks_calls(self):
        """Test circuit breaker blocks calls when open."""
        breaker = CircuitBreaker(failure_threshold=1)

        # Cause failure to open circuit
        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("test error")))

        # Next call should be blocked
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(lambda: "success")

    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        import time

        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1)

        # Open the circuit
        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("test error")))

        assert breaker.state == "open"

        # Wait for recovery timeout
        time.sleep(1.1)

        # Successful call should reset circuit
        result = breaker.call(lambda: "success")
        assert result == "success"
        assert breaker.state == "closed"


# =============================================================================
# Client Tests
# =============================================================================

class TestIndicatorClient:
    """Test indicator client functionality."""

    def test_client_initialization(self, mock_redis):
        """Test client initialization."""
        client = IndicatorClient(
            base_url="http://test:8000",
            cache_client=mock_redis,
            timeout=20.0
        )

        assert client.base_url == "http://test:8000"
        assert client.timeout == 20.0
        assert client.cache_client == mock_redis

    def test_cache_key_generation(self, indicator_client, sample_indicator_request):
        """Test cache key generation."""
        key1 = indicator_client._build_cache_key(sample_indicator_request)
        key2 = indicator_client._build_cache_key(sample_indicator_request)

        # Same request should generate same key
        assert key1 == key2
        assert key1.startswith("indicator:")
        assert len(key1) > 20

    @pytest.mark.asyncio
    async def test_cache_operations(self, indicator_client, mock_redis):
        """Test cache operations."""
        response = IndicatorResponse(
            symbol="BTCUSDT",
            timeframe="1h",
            results={"sma_20": [50100.0]}
        )

        # Test caching
        await indicator_client._cache_response("test_key", response, 300)
        mock_redis.setex.assert_called_once()

        # Test cache retrieval - no cache hit
        mock_redis.get.return_value = None
        cached = await indicator_client._get_cached_response("test_key")
        assert cached is None

        # Test cache retrieval - cache hit
        mock_redis.get.return_value = json.dumps(response.model_dump(mode="json"))
        cached = await indicator_client._get_cached_response("test_key")
        assert cached is not None
        assert cached.symbol == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_successful_compute_request(self, indicator_client, sample_indicator_request):
        """Test successful compute request."""
        with respx.mock:
            # Mock successful response
            respx.post("http://test-indicator:8000/api/v1/indicators/compute").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "results": {
                            "sma_20": [50100.0, 50125.0, 50150.0],
                            "rsi_14": [45.5, 52.3, 48.7]
                        },
                        "cache_hit": False
                    }
                )
            )

            response = await indicator_client.compute_indicators(sample_indicator_request)

            assert response.symbol == "BTCUSDT"
            assert response.timeframe == "1h"
            assert "sma_20" in response.results
            assert "rsi_14" in response.results
            assert response.cache_hit is False

    @pytest.mark.asyncio
    async def test_calculate_single_request(self, indicator_client):
        """Test single calculation request."""
        with respx.mock:
            respx.post("http://test-indicator:8000/api/v1/indicators/calculate").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "symbol": "ETHUSD",
                        "timeframe": "1h",
                        "results": {"rsi_14": [55.2]},
                        "calculation_time": 0.05
                    }
                )
            )

            response = await indicator_client.calculate_single(
                symbol="ETHUSD",
                timeframe="1h",
                indicators=["rsi"],
                data={"prices": [3000, 3100, 3050]}
            )

            assert response.symbol == "ETHUSD"
            assert "rsi_14" in response.results

    @pytest.mark.asyncio

    async def test_feature_service_fallback(self, indicator_client, sample_indicator_request):
        """Test fallback to feature service."""
        with respx.mock:
            # Configure client to prefer feature service
            indicator_client.prefer_feature_service = True

            respx.post("http://test-feature:8000/api/v1/indicators/compute").mock(
                return_value=httpx.Response(
                    200,
                    json={"results": {"sma_20": [50100.0]}, "cache_hit": False}
                )
            )

            response = await indicator_client.compute_indicators(sample_indicator_request)
            assert response.results["sma_20"] == [50100.0]

    @pytest.mark.asyncio

    async def test_http_error_handling(self, indicator_client, sample_indicator_request):
        """Test HTTP error handling."""
        respx.post("http://test-indicator:8000/api/v1/indicators/compute").mock(
            return_value=httpx.Response(
                400,
                json={"detail": "Invalid indicator type"}
            )
        )

        with pytest.raises(IndicatorServiceError) as exc_info:
            await indicator_client.compute_indicators(sample_indicator_request)

        assert exc_info.value.status_code == 400
        assert "Invalid indicator type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_handling(self, indicator_client, sample_indicator_request):
        """Test timeout handling."""
        with respx.mock:
            respx.post("http://test-indicator:8000/api/v1/indicators/compute").mock(
                side_effect=httpx.TimeoutException("Request timeout")
            )

            with pytest.raises(IndicatorTimeoutError):
                await indicator_client.compute_indicators(sample_indicator_request)

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, mock_redis):
        """Test circuit breaker integration."""
        with respx.mock:
            client = IndicatorClient(
                base_url="http://test:8000",
                cache_client=mock_redis,
                circuit_breaker_enabled=True
            )

            # Mock failures to trigger circuit breaker
            respx.post("http://test:8000/api/v1/indicators/compute").mock(
                return_value=httpx.Response(500, json={"detail": "Internal error"})
            )

            request = IndicatorRequest(
                symbol="BTCUSDT",
                timeframe="1h",
                indicators=[IndicatorSpec(type="sma", period=20)],
                ohlcv=OHLCV(
                    t=[1640995200],
                    o=[50000.0],
                    h=[50100.0],
                    l=[49900.0],
                    c=[50050.0],
                    v=[100.0]
                )
            )

            # Trigger multiple failures
            for _ in range(5):
                with pytest.raises(IndicatorServiceError):
                    await client.compute_indicators(request)

            # Circuit should be open now
            assert client.circuit_breaker is not None
            assert client.circuit_breaker.state == "open"

            # Next request should fail immediately
            with pytest.raises(CircuitBreakerOpenError):
                await client.compute_indicators(request)

    @pytest.mark.asyncio

    async def test_health_check(self, indicator_client):
        """Test health check functionality."""
        respx.get("http://test-indicator:8000/health").mock(
            return_value=httpx.Response(
                200,
                json={"status": "healthy", "service": "feature-service"}  # Updated Task 14: consolidated service
            )
        )

        health = await indicator_client.health_check()
        assert health["status"] == "healthy"

    def test_stats_tracking(self, indicator_client):
        """Test performance statistics tracking."""
        # Initial stats
        stats = indicator_client.get_stats()
        assert stats["total_requests"] == 0
        assert stats["cache_hit_rate"] == 0.0

        # Simulate some activity
        indicator_client.stats["total_requests"] = 10
        indicator_client.stats["cache_hits"] = 3
        indicator_client.stats["cache_misses"] = 7
        indicator_client.stats["errors"] = 1

        stats = indicator_client.get_stats()
        assert stats["total_requests"] == 10
        assert stats["cache_hit_rate"] == 0.3
        assert stats["error_rate"] == 0.1

        # Reset stats
        indicator_client.reset_stats()
        stats = indicator_client.get_stats()
        assert stats["total_requests"] == 0


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestUtilityFunctions:
    """Test utility functions."""

    @pytest.mark.asyncio

    async def test_compute_indicators_utility(self, sample_ohlcv):
        """Test compute_indicators utility function."""
        respx.post("http://feature-service:8000/api/v1/indicators/compute").mock(  # Updated Task 14: consolidated service
            return_value=httpx.Response(
                200,
                json={"results": {"sma_20": [50100.0]}, "cache_hit": False}
            )
        )

        indicators = [IndicatorSpec(type="sma", period=20)]

        response = await compute_indicators(
            symbol="BTCUSDT",
            timeframe="1h",
            indicators=indicators,
            ohlcv=sample_ohlcv
        )

        assert response.symbol == "BTCUSDT"
        assert "sma_20" in response.results

    @pytest.mark.asyncio

    async def test_calculate_single_utility(self):
        """Test calculate_single utility function."""
        respx.post("http://feature-service:8000/api/v1/indicators/calculate").mock(  # Updated Task 14: consolidated service
            return_value=httpx.Response(
                200,
                json={
                    "symbol": "ETHUSD",
                    "timeframe": "1h",
                    "results": {"rsi_14": [55.2]},
                    "calculation_time": 0.05
                }
            )
        )

        response = await calculate_single(
            symbol="ETHUSD",
            timeframe="1h",
            indicators=["rsi"],
            data={"prices": [3000, 3100, 3050]}
        )

        assert response.symbol == "ETHUSD"
        assert "rsi_14" in response.results

    def test_create_indicator_client_factory(self):
        """Test indicator client factory function."""
        with patch('redis.asyncio.Redis.from_url') as mock_redis:
            mock_redis.return_value = MagicMock()

            client = create_indicator_client(
                base_url="http://custom:8000",
                timeout=15.0
            )

            assert client.base_url == "http://custom:8000"
            assert client.timeout == 15.0

    def test_create_indicator_client_no_redis(self):
        """Test client creation without Redis."""
        with patch('redis.asyncio.Redis.from_url', side_effect=ImportError):
            client = create_indicator_client(cache_enabled=True)
            assert client.cache_client is None


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    @pytest.mark.asyncio

    async def test_full_workflow_with_caching(self, mock_redis):
        """Test complete workflow with caching."""
        client = IndicatorClient(
            base_url="http://test:8000",
            cache_client=mock_redis
        )

        # Mock successful API response
        api_response = {
            "results": {
                "sma_20": [50100.0, 50125.0],
                "rsi_14": [45.5, 52.3]
            },
            "cache_hit": False
        }

        respx.post("http://test:8000/api/v1/indicators/compute").mock(
            return_value=httpx.Response(200, json=api_response)
        )

        # First request - should hit API and cache result
        request = IndicatorRequest(
            symbol="BTCUSDT",
            timeframe="1h",
            indicators=[
                IndicatorSpec(type="sma", period=20),
                IndicatorSpec(type="rsi", period=14)
            ],
            ohlcv=OHLCV(
                t=[1640995200, 1640995260],
                o=[50000.0, 50100.0],
                h=[50150.0, 50200.0],
                l=[49950.0, 50050.0],
                c=[50100.0, 50050.0],
                v=[100.5, 95.2]
            )
        )

        response = await client.compute_indicators(request)

        # Verify response
        assert response.symbol == "BTCUSDT"
        assert "sma_20" in response.results
        assert response.cache_hit is False

        # Verify caching was attempted
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio

    async def test_multi_service_fallback(self, mock_redis):
        """Test fallback between services."""
        client = IndicatorClient(
            base_url="http://indicator:8000",
            feature_service_url="http://feature:8000",
            cache_client=mock_redis
        )

        # Mock indicator service failure
        respx.post("http://indicator:8000/api/v1/indicators/compute").mock(
            return_value=httpx.Response(503, json={"detail": "Service unavailable"})
        )

        # Mock feature service success
        respx.post("http://feature:8000/api/v1/indicators/compute").mock(
            return_value=httpx.Response(
                200,
                json={"results": {"sma_20": [50100.0]}, "cache_hit": False}
            )
        )

        request = IndicatorRequest(
            symbol="BTCUSDT",
            timeframe="1h",
            indicators=[IndicatorSpec(type="sma", period=20)],
            ohlcv=OHLCV(
                t=[1640995200],
                o=[50000.0],
                h=[50100.0],
                l=[49900.0],
                c=[50050.0],
                v=[100.0]
            )
        )

        # First attempt should fail on indicator service
        with pytest.raises(IndicatorServiceError):
            await client.compute_indicators(request)

        # Manual fallback to feature service should work
        response = await client.compute_indicators(request, prefer_feature_service=True)
        assert response.results["sma_20"] == [50100.0]

    @pytest.mark.asyncio

    async def test_batch_processing_simulation(self):
        """Test batch processing multiple symbols."""
        client = IndicatorClient(base_url="http://test:8000")

        symbols = ["BTCUSDT", "ETHUSD", "ADABTC"]

        # Mock responses for each symbol
        for i, symbol in enumerate(symbols):
            respx.post("http://test:8000/api/v1/indicators/compute").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "results": {"sma_20": [50000.0 + i * 1000]},
                        "cache_hit": False
                    }
                )
            )

        # Process batch
        tasks = []
        for symbol in symbols:
            request = IndicatorRequest(
                symbol=symbol,
                timeframe="1h",
                indicators=[IndicatorSpec(type="sma", period=20)],
                ohlcv=OHLCV(
                    t=[1640995200],
                    o=[50000.0],
                    h=[50100.0],
                    l=[49900.0],
                    c=[50050.0],
                    v=[100.0]
                )
            )
            tasks.append(client.compute_indicators(request))

        responses = await asyncio.gather(*tasks)

        assert len(responses) == 3
        for i, response in enumerate(responses):
            assert response.symbol == symbols[i]
            assert "sma_20" in response.results

    @pytest.mark.asyncio
    async def test_error_resilience(self, mock_redis):
        """Test client resilience to various errors."""
        client = IndicatorClient(
            base_url="http://unreachable:8000",
            cache_client=mock_redis,
            max_retries=2
        )

        request = IndicatorRequest(
            symbol="BTCUSDT",
            timeframe="1h",
            indicators=[IndicatorSpec(type="sma", period=20)],
            ohlcv=OHLCV(
                t=[1640995200],
                o=[50000.0],
                h=[50100.0],
                l=[49900.0],
                c=[50050.0],
                v=[100.0]
            )
        )

        # Should handle connection errors gracefully
        with pytest.raises(IndicatorClientError):
            await client.compute_indicators(request)

        # Check stats were updated
        stats = client.get_stats()
        assert stats["errors"] > 0
