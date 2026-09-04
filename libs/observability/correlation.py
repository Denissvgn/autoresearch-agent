"""Correlation ID middleware for request tracing."""

import contextvars
import logging
import time
import uuid
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from prometheus_client import Histogram, REGISTRY
    
    _METRIC_NAME = 'correlation_middleware_duration_seconds'

    def _get_or_create_correlation_histogram() -> Histogram:
        """Return shared histogram, tolerating repeated imports in test runs."""
        existing = REGISTRY._names_to_collectors.get(_METRIC_NAME)  # type: ignore[attr-defined]
        if isinstance(existing, Histogram):
            return existing
        try:
            return Histogram(
                _METRIC_NAME,
                'Time spent in correlation middleware',
                buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1)
            )
        except ValueError:
            # Another thread/worker registered concurrently; fetch and re-use
            reused = REGISTRY._names_to_collectors.get(_METRIC_NAME)  # type: ignore[attr-defined]
            if isinstance(reused, Histogram):
                return reused
            raise

    # Middleware latency metric (shared across imports/tests)
    CORRELATION_MIDDLEWARE_DURATION = _get_or_create_correlation_histogram()
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Context variable for correlation ID
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', default=None
)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to handle correlation ID injection and propagation."""
    
    def __init__(self, app, header_name: str = "X-Request-ID", enable_metrics: bool = True):
        """
        Initialize middleware.
        
        Args:
            app: FastAPI application
            header_name: Header name for correlation ID
            enable_metrics: Enable Prometheus latency metrics
        """
        super().__init__(app)
        self.header_name = header_name
        self.enable_metrics = enable_metrics and PROMETHEUS_AVAILABLE
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and inject correlation ID.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with correlation ID header
        """
        start_time = time.perf_counter() if self.enable_metrics else None
        
        # Extract or generate correlation ID
        correlation_id = request.headers.get(self.header_name) or str(uuid.uuid4())
        
        # Set in context for this request
        correlation_id_var.set(correlation_id)
        
        # Process request
        response = await call_next(request)
        
        # Add to response headers
        response.headers[self.header_name] = correlation_id
        
        # Record middleware latency
        if self.enable_metrics and start_time is not None:
            duration = time.perf_counter() - start_time
            CORRELATION_MIDDLEWARE_DURATION.observe(duration)
        
        return response


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID from context.
    
    Returns:
        Correlation ID string or None if not set
    """
    return correlation_id_var.get()


class CorrelationLogFilter(logging.Filter):
    """Log filter to inject correlation ID into log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add correlation ID to log record.
        
        Args:
            record: Log record to enhance
            
        Returns:
            True (always allow record)
        """
        record.correlation_id = get_correlation_id() or "-"
        return True
