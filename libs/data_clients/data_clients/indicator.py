"""
Indicator Service Client

Type-safe async client for indicator/feature service communication with:
- Unified API for both compute and calculate endpoints
- Automatic retry logic with exponential backoff
- Circuit breaker pattern for fault tolerance
- Response caching with TTL
- Comprehensive error handling and validation
- Debug logging and performance metrics
"""

from contextlib import asynccontextmanager
from datetime import datetime
import hashlib
import json
import logging
import time
from typing import Any, Literal
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field, model_validator
from redis.asyncio import Redis
import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Setup logging
logger = structlog.get_logger(__name__)

# Type aliases
IndicatorType = Literal["sma", "ema", "rsi", "atr", "vwap", "bollinger", "macd", "stoch", "williams", "bbands", "ad", "obv", "adx", "cci", "dx"]
TimeFrame = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]


# =============================================================================
# Exception Classes
# =============================================================================

class IndicatorClientError(Exception):
    """Base exception for indicator client errors."""
    def __init__(self, message: str, status_code: int | None = None, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class IndicatorServiceError(IndicatorClientError):
    """Raised when indicator service returns an error response."""
    pass


class IndicatorTimeoutError(IndicatorClientError):
    """Raised when indicator service request times out."""
    pass


class IndicatorValidationError(IndicatorClientError):
    """Raised when request validation fails."""
    pass


class CircuitBreakerOpenError(IndicatorClientError):
    """Raised when circuit breaker is open."""
    pass


# =============================================================================
# Data Models
# =============================================================================

class OHLCV(BaseModel):
    """OHLCV data structure matching indicator service format."""
    t: list[int] = Field(..., description="Timestamps (Unix seconds)", min_length=1)
    o: list[float] = Field(..., description="Open prices", min_length=1)
    h: list[float] = Field(..., description="High prices", min_length=1)
    l: list[float] = Field(..., description="Low prices", min_length=1)
    c: list[float] = Field(..., description="Close prices", min_length=1)
    v: list[float] = Field(..., description="Volume", min_length=1)

    @model_validator(mode="after")
    def validate_lengths(self) -> "OHLCV":
        """Ensure all arrays have same length."""
        lengths = [len(self.t), len(self.o), len(self.h), len(self.l), len(self.c), len(self.v)]
        if not all(length == lengths[0] for length in lengths):
            raise ValueError("All OHLCV arrays must have the same length")
        return self

    @classmethod
    def from_dict(cls, data: dict[str, list[int | float]]) -> "OHLCV":
        """Create OHLCV from dictionary with flexible key names."""
        key_mappings = {
            't': ['t', 'time', 'timestamp', 'timestamps'],
            'o': ['o', 'open', 'opens'],
            'h': ['h', 'high', 'highs'],
            'l': ['l', 'low', 'lows'],
            'c': ['c', 'close', 'closes'],
            'v': ['v', 'volume', 'volumes']
        }

        mapped_data = {}
        for target_key, possible_keys in key_mappings.items():
            for key in possible_keys:
                if key in data:
                    mapped_data[target_key] = data[key]
                    break
            else:
                raise ValueError(f"Required key '{target_key}' not found in data. Expected one of: {possible_keys}")

        return cls(**mapped_data)


class IndicatorSpec(BaseModel):
    """Specification for a single indicator calculation."""
    type: IndicatorType = Field(..., description="Indicator type")
    period: int = Field(default=14, gt=0, le=200, description="Period for the indicator")

    # Additional parameters for specific indicators
    nbdevup: float | None = Field(default=None, description="Upper deviation for Bollinger Bands")
    nbdevdn: float | None = Field(default=None, description="Lower deviation for Bollinger Bands")
    fastperiod: int | None = Field(default=None, description="Fast period for MACD")
    slowperiod: int | None = Field(default=None, description="Slow period for MACD")
    signalperiod: int | None = Field(default=None, description="Signal period for MACD")

    @model_validator(mode="after")
    def set_defaults_by_type(self) -> "IndicatorSpec":
        """Set default parameters based on indicator type."""
        defaults = {
            "sma": {"period": 20},
            "ema": {"period": 12},
            "rsi": {"period": 14},
            "atr": {"period": 14},
            "vwap": {"period": 1},  # VWAP typically doesn't use period
            "bollinger": {"period": 20, "nbdevup": 2.0, "nbdevdn": 2.0},
            "bbands": {"period": 20, "nbdevup": 2.0, "nbdevdn": 2.0},
            "macd": {"fastperiod": 12, "slowperiod": 26, "signalperiod": 9},
            "stoch": {"period": 14},
            "williams": {"period": 14},
            "ad": {"period": 1},
            "obv": {"period": 1},
            "adx": {"period": 14},
            "cci": {"period": 14},
            "dx": {"period": 14},
        }

        if self.type in defaults:
            for key, value in defaults[self.type].items():
                # Only set if current value is default or None for non-period fields
                if key == "period" and self.period == 14:  # Default period
                    setattr(self, key, value)
                elif hasattr(self, key) and getattr(self, key, None) is None:
                    setattr(self, key, value)

        return self


class IndicatorRequest(BaseModel):
    """Request model for indicator computation."""
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    timeframe: TimeFrame = Field(..., description="Timeframe for the data")
    indicators: list[IndicatorSpec] = Field(..., description="List of indicators to compute", min_length=1)
    ohlcv: OHLCV = Field(..., description="OHLCV data for computation")

    # Optional parameters
    use_cache: bool = Field(default=True, description="Whether to use cached results")
    cache_ttl: int | None = Field(default=None, description="Cache TTL in seconds")


class CalculateRequest(BaseModel):
    """Request model for single indicator calculation."""
    symbol: str = Field(..., description="Trading symbol")
    timeframe: TimeFrame = Field(..., description="Timeframe")
    indicators: list[str] = Field(..., description="List of indicator names", min_length=1)
    data: Any = Field(..., description="OHLCV data in any format")


class IndicatorResponse(BaseModel):
    """Response model for indicator computation."""
    symbol: str
    timeframe: str
    results: dict[str, Any] = Field(..., description="Computed indicator values")
    calculation_time: float | None = Field(default=None, description="Calculation time in seconds")
    cache_hit: bool = Field(default=False, description="Whether result came from cache")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    # Additional metadata
    request_id: str | None = Field(default=None, description="Unique request identifier")
    service_endpoint: str | None = Field(default=None, description="Service endpoint used")


# =============================================================================
# Circuit Breaker Implementation
# =============================================================================

class CircuitBreaker:
    """Simple circuit breaker implementation for service protection."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: tuple = (Exception,)
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "closed"  # closed, open, half-open

    async def async_call(self, func, *args, **kwargs):
        """Execute async function with circuit breaker protection."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (
            self.last_failure_time is not None and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )

    def _on_success(self):
        """Reset circuit breaker on successful call."""
        self.failure_count = 0
        self.state = "closed"

    def _on_failure(self):
        """Handle failure and potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"


# =============================================================================
# Main Client Implementation
# =============================================================================

class IndicatorClient:
    """
    Async client for indicator/feature service communication.

    Features:
    - Unified API for both compute and calculate endpoints
    - Automatic retry logic with exponential backoff
    - Circuit breaker pattern for fault tolerance
    - Response caching with configurable TTL
    - Request/response validation
    - Comprehensive error handling
    - Performance metrics and debug logging
    """

    def __init__(
        self,
        base_url: str = "http://feature-service:8000",  # Updated Task 14: consolidated service
        feature_service_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        cache_client: Redis | None = None,
        cache_ttl: int = 300,
        circuit_breaker_enabled: bool = True,
        prefer_feature_service: bool = False,
        debug: bool = False
    ):
        """
        Initialize the indicator client.

        Args:
            base_url: Base URL for indicator service
            feature_service_url: Base URL for feature service (fallback)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            cache_client: Redis client for caching (optional)
            cache_ttl: Default cache TTL in seconds
            circuit_breaker_enabled: Enable circuit breaker protection
            prefer_feature_service: Prefer feature service over indicator service
            debug: Enable debug logging
        """
        self.base_url = base_url.rstrip("/")
        self.feature_service_url = feature_service_url.rstrip("/") if feature_service_url else None
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_client = cache_client
        self.cache_ttl = cache_ttl
        self.prefer_feature_service = prefer_feature_service
        self.debug = debug

        # Circuit breaker setup
        if circuit_breaker_enabled:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60,
                expected_exception=(httpx.HTTPError, IndicatorServiceError)
            )
        else:
            self.circuit_breaker = None

        # HTTP client configuration
        self.client_config = {
            "timeout": httpx.Timeout(timeout),
            "limits": httpx.Limits(max_keepalive_connections=10, max_connections=20),
            "headers": {
                "User-Agent": "traid-platform-indicator-client/0.1.0",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        }

        # Performance tracking
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "retries": 0,
            "circuit_breaker_opens": 0
        }

    @asynccontextmanager
    async def _http_client(self):
        """Create async HTTP client with configuration."""
        async with httpx.AsyncClient(**self.client_config) as client:
            yield client

    def _build_cache_key(self, request: IndicatorRequest) -> str:
        """Build cache key for request."""
        # Create deterministic key from request
        key_data = {
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "indicators": sorted([
                f"{ind.type}_{ind.period}_{getattr(ind, 'nbdevup', '')}_{getattr(ind, 'nbdevdn', '')}"
                for ind in request.indicators
            ]),
            "ohlcv_hash": hashlib.md5(
                json.dumps([request.ohlcv.t, request.ohlcv.c], sort_keys=True).encode()
            ).hexdigest()[:8]
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return f"indicator:{hashlib.md5(key_str.encode()).hexdigest()}"

    async def _get_cached_response(self, cache_key: str) -> IndicatorResponse | None:
        """Get cached response if available."""
        if not self.cache_client:
            return None

        try:
            cached_data = await self.cache_client.get(cache_key)
            if cached_data:
                self.stats["cache_hits"] += 1
                data = json.loads(cached_data)
                # Handle datetime serialization
                if "timestamp" in data:
                    data["timestamp"] = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
                return IndicatorResponse(**data)
        except Exception as e:
            logger.warning("Cache retrieval failed", error=str(e))

        self.stats["cache_misses"] += 1
        return None

    async def _cache_response(self, cache_key: str, response: IndicatorResponse, ttl: int | None = None) -> None:
        """Cache response with TTL."""
        if not self.cache_client:
            return

        try:
            ttl = ttl or self.cache_ttl
            data = response.model_dump(mode="json")
            # Ensure datetime is serializable
            if "timestamp" in data:
                data["timestamp"] = response.timestamp.isoformat()
            await self.cache_client.setex(cache_key, ttl, json.dumps(data))
        except Exception as e:
            logger.warning("Cache storage failed", error=str(e))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, IndicatorServiceError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        use_feature_service: bool = False
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic."""
        base_url = self.feature_service_url if use_feature_service else self.base_url
        if not base_url:
            raise IndicatorClientError("No service URL configured")

        url = urljoin(base_url, endpoint)

        try:
            async with self._http_client() as client:
                if self.debug:
                    logger.debug("Making request", method=method, url=url, data=data)

                if method.upper() == "GET":
                    response = await client.get(url)
                else:
                    response = await client.post(url, json=data)

                response.raise_for_status()
                result = response.json()

                if self.debug:
                    logger.debug("Request successful", status_code=response.status_code)

                return result

        except httpx.TimeoutException as e:
            raise IndicatorTimeoutError(f"Request timeout: {e}")
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_detail = e.response.json().get("detail", str(e))
            except:
                error_detail = str(e)

            raise IndicatorServiceError(
                f"HTTP {e.response.status_code}: {error_detail}",
                status_code=e.response.status_code
            )
        except Exception as e:
            raise IndicatorClientError(f"Request failed: {e}")

    async def compute_indicators(
        self,
        request: IndicatorRequest,
        use_cache: bool | None = None,
        prefer_feature_service: bool | None = None
    ) -> IndicatorResponse:
        """
        Compute indicators using the /compute endpoint.

        Args:
            request: Indicator computation request
            use_cache: Override cache usage setting
            prefer_feature_service: Override service preference

        Returns:
            IndicatorResponse with computed indicators
        """
        self.stats["total_requests"] += 1
        start_time = time.time()

        # Determine cache usage
        use_cache = use_cache if use_cache is not None else request.use_cache
        cache_key = self._build_cache_key(request) if use_cache else None

        # Check cache first
        if cache_key:
            cached_response = await self._get_cached_response(cache_key)
            if cached_response:
                cached_response.cache_hit = True
                return cached_response

        # Prepare request data
        request_data = {
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "indicators": [spec.model_dump() for spec in request.indicators],
            "ohlcv": request.ohlcv.model_dump()
        }

        # Determine which service to use
        use_feature_service = prefer_feature_service if prefer_feature_service is not None else self.prefer_feature_service
        endpoint = "/api/v1/indicators/compute"

        try:
            # Execute with circuit breaker if enabled
            if self.circuit_breaker:
                result = await self.circuit_breaker.async_call(
                    self._make_request,
                    "POST",
                    endpoint,
                    request_data,
                    use_feature_service
                )
            else:
                result = await self._make_request("POST", endpoint, request_data, use_feature_service)

            # Build response
            calculation_time = time.time() - start_time
            response = IndicatorResponse(
                symbol=request.symbol,
                timeframe=request.timeframe,
                results=result.get("results", {}),
                calculation_time=calculation_time,
                cache_hit=False,
                service_endpoint=endpoint
            )

            # Cache the response
            if cache_key:
                await self._cache_response(cache_key, response, request.cache_ttl)

            return response

        except CircuitBreakerOpenError:
            self.stats["circuit_breaker_opens"] += 1
            raise
        except Exception as e:
            self.stats["errors"] += 1
            logger.error("Compute request failed", error=str(e), symbol=request.symbol)
            raise

    async def calculate_single(
        self,
        symbol: str,
        timeframe: TimeFrame,
        indicators: list[str],
        data: Any,
        use_feature_service: bool | None = None
    ) -> IndicatorResponse:
        """
        Calculate indicators using the /calculate endpoint.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            indicators: List of indicator names
            data: OHLCV data in any format
            use_feature_service: Override service preference

        Returns:
            IndicatorResponse with calculated indicators
        """
        self.stats["total_requests"] += 1
        start_time = time.time()

        # Prepare request data
        request_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicators": indicators,
            "data": data
        }

        # Determine which service to use
        use_feature_service = use_feature_service if use_feature_service is not None else self.prefer_feature_service
        endpoint = "/api/v1/indicators/calculate"

        try:
            # Execute request
            if self.circuit_breaker:
                result = await self.circuit_breaker.async_call(
                    self._make_request,
                    "POST",
                    endpoint,
                    request_data,
                    use_feature_service
                )
            else:
                result = await self._make_request("POST", endpoint, request_data, use_feature_service)

            # Build response
            calculation_time = time.time() - start_time
            response = IndicatorResponse(
                symbol=result.get("symbol", symbol),
                timeframe=result.get("timeframe", timeframe),
                results=result.get("results", {}),
                calculation_time=result.get("calculation_time", calculation_time),
                cache_hit=False,
                service_endpoint=endpoint
            )

            return response

        except CircuitBreakerOpenError:
            self.stats["circuit_breaker_opens"] += 1
            raise
        except Exception as e:
            self.stats["errors"] += 1
            logger.error("Calculate request failed", error=str(e), symbol=symbol)
            raise

    async def health_check(self, use_feature_service: bool | None = None) -> dict[str, Any]:
        """
        Check service health.

        Args:
            use_feature_service: Check feature service instead of indicator service

        Returns:
            Health status information
        """
        use_feature_service = use_feature_service if use_feature_service is not None else self.prefer_feature_service
        endpoint = "/health"

        try:
            result = await self._make_request("GET", endpoint, use_feature_service=use_feature_service)
            return result
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            raise

    def get_stats(self) -> dict[str, Any]:
        """Get client performance statistics."""
        return {
            **self.stats,
            "cache_hit_rate": (
                self.stats["cache_hits"] / (self.stats["cache_hits"] + self.stats["cache_misses"])
                if (self.stats["cache_hits"] + self.stats["cache_misses"]) > 0
                else 0.0
            ),
            "error_rate": (
                self.stats["errors"] / self.stats["total_requests"]
                if self.stats["total_requests"] > 0
                else 0.0
            ),
            "circuit_breaker_state": self.circuit_breaker.state if self.circuit_breaker else "disabled"
        }

    def reset_stats(self) -> None:
        """Reset performance statistics."""
        self.stats = {key: 0 for key in self.stats}


# =============================================================================
# Utility Functions
# =============================================================================

async def compute_indicators(
    symbol: str,
    timeframe: TimeFrame,
    indicators: list[IndicatorSpec],
    ohlcv: OHLCV,
    client: IndicatorClient | None = None,
    **kwargs
) -> IndicatorResponse:
    """
    Convenience function to compute indicators.

    Args:
        symbol: Trading symbol
        timeframe: Data timeframe
        indicators: List of indicator specifications
        ohlcv: OHLCV data
        client: Optional existing client instance
        **kwargs: Additional arguments for client

    Returns:
        IndicatorResponse with computed indicators
    """
    if client is None:
        client = IndicatorClient(**kwargs)

    request = IndicatorRequest(
        symbol=symbol,
        timeframe=timeframe,
        indicators=indicators,
        ohlcv=ohlcv
    )

    return await client.compute_indicators(request)


async def calculate_single(
    symbol: str,
    timeframe: TimeFrame,
    indicators: list[str],
    data: Any,
    client: IndicatorClient | None = None,
    **kwargs
) -> IndicatorResponse:
    """
    Convenience function to calculate single indicators.

    Args:
        symbol: Trading symbol
        timeframe: Data timeframe
        indicators: List of indicator names
        data: OHLCV data in any format
        client: Optional existing client instance
        **kwargs: Additional arguments for client

    Returns:
        IndicatorResponse with calculated indicators
    """
    if client is None:
        client = IndicatorClient(**kwargs)

    return await client.calculate_single(symbol, timeframe, indicators, data)


def create_indicator_client(
    base_url: str = "http://feature-service:8000",  # Updated Task 14: consolidated service
    cache_enabled: bool = True,
    **kwargs
) -> IndicatorClient:
    """
    Factory function to create configured indicator client.

    Args:
        base_url: Base URL for indicator service
        cache_enabled: Enable Redis caching
        **kwargs: Additional client configuration

    Returns:
        Configured IndicatorClient instance
    """
    # Setup Redis client if caching is enabled
    cache_client = None
    if cache_enabled:
        try:
            import redis.asyncio as redis
            cache_client = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)
        except ImportError:
            logger.warning("Redis not available, caching disabled")

    return IndicatorClient(
        base_url=base_url,
        cache_client=cache_client,
        **kwargs
    )
