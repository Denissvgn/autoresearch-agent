from __future__ import annotations


# Fallback classes that mimic Prometheus client interface
class _NoopMetric:
    """No-op metric class that accepts constructor args and provides chainable methods."""
    
    def __init__(self, *args, **kwargs):
        # Accept any constructor arguments but do nothing
        pass
        
    def labels(self, *args, **kwargs):
        return self
        
    def inc(self, *args, **kwargs):
        return None
        
    def set(self, *args, **kwargs):
        return None

try:
    from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge
    _METRICS = True
except ImportError:  # More specific exception handling
    Counter = _NoopMetric  # type: ignore
    Gauge = _NoopMetric  # type: ignore
    REGISTRY = None  # type: ignore
    _METRICS = False


# Global registry to track created metrics
_CREATED_METRICS = {}


def _get_or_create_metric(metric_class, name, description, labelnames=None):
    """
    Get existing metric or create new one, preventing duplicate registration.
    
    Args:
        metric_class: Counter or Gauge class
        name: Metric name
        description: Metric description  
        labelnames: List of label names
    
    Returns:
        Metric instance
    """
    if not _METRICS:
        return metric_class()
    
    # Return existing metric if already created
    if name in _CREATED_METRICS:
        return _CREATED_METRICS[name]
    
    # Create new metric
    try:
        if labelnames:
            metric = metric_class(name, description, labelnames=labelnames)
        else:
            metric = metric_class(name, description)
        
        _CREATED_METRICS[name] = metric
        return metric
        
    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            # If we get duplicate error, create a no-op metric to prevent crashes
            # This shouldn't happen with our tracking, but just in case
            noop_metric = _NoopMetric()
            _CREATED_METRICS[name] = noop_metric
            return noop_metric
        raise


# Metrics that work with both real and fallback classes
resilience_retry_attempts_total = _get_or_create_metric(
    Counter, "resilience_retry_attempts_total", "Retry attempts total", labelnames=("operation",)
)
resilience_retry_failures_total = _get_or_create_metric(
    Counter, "resilience_retry_failures_total", "Retry failures total", labelnames=("operation",)
)
circuit_breaker_state = _get_or_create_metric(
    Gauge, "circuit_breaker_state", "Circuit breaker state (0=closed,1=open,2=half_open)", labelnames=("operation",)
)
circuit_breaker_state_changes_total = _get_or_create_metric(
    Counter, "circuit_breaker_state_changes_total", "Circuit breaker state changes total", labelnames=("operation", "state")
)
circuit_breaker_failures_total = _get_or_create_metric(
    Counter, "circuit_breaker_failures_total", "Circuit breaker failures total", labelnames=("operation",)
)
circuit_breaker_successes_total = _get_or_create_metric(
    Counter, "circuit_breaker_successes_total", "Circuit breaker successes total", labelnames=("operation",)
)
circuit_breaker_rejections_total = _get_or_create_metric(
    Counter, "circuit_breaker_rejections_total", "Circuit breaker rejections total", labelnames=("operation",)
)

