"""
TRAID Platform Data Clients Library

Shared client libraries for communication with data services including:
- Indicator Service: Technical indicator computation
- Feature Service: Enhanced feature computation
- Market Data Services: Real-time and historical data
- Batched Data Ingest: Cursor-paginated OHLCV access (ARC-016)

This library provides type-safe, async clients with built-in retry logic,
circuit breaker patterns, caching, and comprehensive error handling.
"""

from .indicator import (  # Core client; Exceptions; Models; Utilities
    OHLCV,
    IndicatorClient,
    IndicatorClientError,
    IndicatorRequest,
    IndicatorResponse,
    IndicatorServiceError,
    IndicatorSpec,
    IndicatorTimeoutError,
    IndicatorValidationError,
    calculate_single,
    compute_indicators,
    create_indicator_client,
)

from .batched_ingest_client import (  # ARC-016: Batched data ingest
    BatchedDataIngestClient,
    BatchedIngestConnectionError,
    BatchedIngestCursorExpiredError,
    BatchedIngestDataNotFoundError,
    BatchedIngestError,
)

__version__ = "0.2.0"

__all__ = [
    # Indicator client
    "IndicatorClient",

    # Indicator models
    "IndicatorRequest",
    "IndicatorResponse",
    "IndicatorSpec",
    "OHLCV",

    # Indicator exceptions
    "IndicatorClientError",
    "IndicatorServiceError",
    "IndicatorTimeoutError",
    "IndicatorValidationError",

    # Indicator utilities
    "compute_indicators",
    "calculate_single",
    "create_indicator_client",

    # ARC-016: Batched data ingest client
    "BatchedDataIngestClient",
    "BatchedIngestError",
    "BatchedIngestConnectionError",
    "BatchedIngestDataNotFoundError",
    "BatchedIngestCursorExpiredError",
]
