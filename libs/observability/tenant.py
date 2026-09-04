"""Tenant ID middleware for multi-tenancy support."""

import contextvars
import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from prometheus_client import Histogram, REGISTRY
    
    _METRIC_NAME = 'tenant_middleware_duration_seconds'

    def _get_or_create_tenant_histogram() -> Histogram:
        """Return shared histogram, tolerating repeated imports in tests."""
        existing = REGISTRY._names_to_collectors.get(_METRIC_NAME)  # type: ignore[attr-defined]
        if isinstance(existing, Histogram):
            return existing
        try:
            return Histogram(
                _METRIC_NAME,
                'Time spent in tenant middleware',
                buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1)
            )
        except ValueError:
            reused = REGISTRY._names_to_collectors.get(_METRIC_NAME)  # type: ignore[attr-defined]
            if isinstance(reused, Histogram):
                return reused
            raise

    # Middleware latency metric (shared across imports/tests)
    TENANT_MIDDLEWARE_DURATION = _get_or_create_tenant_histogram()
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Context variable for tenant ID
tenant_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'tenant_id', default=None
)


class TenantIdMiddleware(BaseHTTPMiddleware):
    """Middleware to handle X-Tenant-Id propagation."""
    
    def __init__(self, app, header_name: str = "X-Tenant-Id", enable_metrics: bool = True):
        """
        Initialize middleware.
        
        Args:
            app: FastAPI application
            header_name: Header name for tenant ID
            enable_metrics: Enable Prometheus latency metrics
        """
        super().__init__(app)
        self.header_name = header_name
        self.enable_metrics = enable_metrics and PROMETHEUS_AVAILABLE
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and propagate tenant ID.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with tenant ID header echoed if provided
        """
        start_time = time.perf_counter() if self.enable_metrics else None
        
        # Extract tenant ID from header (no generation - must be provided)
        tenant_id = request.headers.get(self.header_name)
        
        # Set in context if present
        if tenant_id:
            tenant_id_var.set(tenant_id)
        
        # Process request
        response = await call_next(request)
        
        # Echo back in response if was provided
        if tenant_id:
            response.headers[self.header_name] = tenant_id
        
        # Record middleware latency
        if self.enable_metrics and start_time is not None:
            duration = time.perf_counter() - start_time
            TENANT_MIDDLEWARE_DURATION.observe(duration)
        
        return response


def get_tenant_id() -> Optional[str]:
    """
    Get the current tenant ID from context.
    
    Returns:
        Tenant ID string or None if not set
    """
    return tenant_id_var.get()


class TenantLogFilter(logging.Filter):
    """Log filter to inject tenant_id into log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add tenant ID to log record.
        
        Args:
            record: Log record to enhance
            
        Returns:
            True (always allow record)
        """
        record.tenant_id = get_tenant_id() or "-"
        return True
