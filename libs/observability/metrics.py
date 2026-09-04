"""
Unified Prometheus metrics registry manager for ML services.

Provides safe metric creation with:
- Separate CollectorRegistry per service for true isolation
- Global cache to prevent duplicate registration
- Existing collector return (not noop) for transparency
- Support for Counter, Gauge, Histogram, Summary

Usage:
    from libs.observability.metrics import get_or_create_metric, get_service_registry
    
    # Get isolated registry for your service
    registry = get_service_registry("inference-service")
    
    # Create metrics with automatic deduplication
    request_counter = get_or_create_metric(
        Counter,
        "inference_requests_total",
        "Total inference requests",
        labelnames=["model_type", "status"],
        registry=registry
    )
"""
import importlib
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, Summary
    from prometheus_client.registry import REGISTRY as DEFAULT_REGISTRY
    
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Noop types for when prometheus_client is not installed
    class MockCounter:
        def __init__(self, *args: Any, **kwargs: Any) -> None: pass
        def inc(self, *args: Any, **kwargs: Any) -> None: pass
        def labels(self, *args: Any, **kwargs: Any) -> "MockCounter": return self
    
    class MockGauge:
        def __init__(self, *args: Any, **kwargs: Any) -> None: pass
        def set(self, *args: Any, **kwargs: Any) -> None: pass
        def inc(self, *args: Any, **kwargs: Any) -> None: pass
        def dec(self, *args: Any, **kwargs: Any) -> None: pass
        def labels(self, *args: Any, **kwargs: Any) -> "MockGauge": return self
    
    class MockHistogram:
        def __init__(self, *args: Any, **kwargs: Any) -> None: pass
        def observe(self, *args: Any, **kwargs: Any) -> None: pass
        def labels(self, *args: Any, **kwargs: Any) -> "MockHistogram": return self
    
    class MockSummary:
        def __init__(self, *args: Any, **kwargs: Any) -> None: pass
        def observe(self, *args: Any, **kwargs: Any) -> None: pass
        def labels(self, *args: Any, **kwargs: Any) -> "MockSummary": return self
    
    class MockCollectorRegistry:
        def __init__(self, *args: Any, **kwargs: Any) -> None: pass
        def register(self, *args: Any, **kwargs: Any) -> None: pass
        def unregister(self, *args: Any, **kwargs: Any) -> None: pass
        _names_to_collectors: Dict[str, Any] = {}
        _collector_to_names: Dict[Any, List[str]] = {}
    
    # Assign mocks to expected names to avoid Pylance "declared type" conflicts
    Counter = MockCounter  # type: ignore
    Gauge = MockGauge  # type: ignore
    Histogram = MockHistogram  # type: ignore
    Summary = MockSummary  # type: ignore
    CollectorRegistry = MockCollectorRegistry  # type: ignore
    
    DEFAULT_REGISTRY = CollectorRegistry()

logger = logging.getLogger(__name__)

# Global cache: {service_name: {metric_name: metric_instance}}
_SERVICE_METRICS_CACHE: Dict[str, Dict[str, Any]] = {}

# Global registry cache: {service_name: CollectorRegistry}
_SERVICE_REGISTRIES: Dict[str, Any] = {}

MetricType = TypeVar('MetricType', bound=Any)


def get_service_registry(service_name: str) -> Any:
    """
    Get or create an isolated CollectorRegistry for a service.
    
    This provides true isolation between services, preventing metric
    conflicts even when services are loaded in the same process (e.g., tests).
    
    Args:
        service_name: Unique service identifier (e.g., "inference-service")
    
    Returns:
        Isolated CollectorRegistry for the service
    """
    if not PROMETHEUS_AVAILABLE:
        return DEFAULT_REGISTRY
    
    if service_name not in _SERVICE_REGISTRIES:
        _SERVICE_REGISTRIES[service_name] = CollectorRegistry()
        logger.debug(f"Created isolated registry for service: {service_name}")
    
    return _SERVICE_REGISTRIES[service_name]


def clear_service_registry(service_name: str) -> None:
    """
    Clear all metrics for a specific service.
    
    Useful for test isolation - clears both the registry and cache
    for a specific service without affecting other services.
    
    Args:
        service_name: Service identifier to clear
    """
    if not PROMETHEUS_AVAILABLE:
        return
    
    # Clear cache
    if service_name in _SERVICE_METRICS_CACHE:
        _SERVICE_METRICS_CACHE[service_name].clear()
        logger.debug(f"Cleared metrics cache for service: {service_name}")
    
    # Clear registry
    if service_name in _SERVICE_REGISTRIES:
        registry = _SERVICE_REGISTRIES[service_name]
        collectors = list(registry._collector_to_names.keys())
        for collector in collectors:
            try:
                registry.unregister(collector)
            except Exception as e:
                logger.debug(f"Failed to unregister collector: {e}")
        logger.debug(f"Cleared registry for service: {service_name}")


def clear_all_service_registries() -> None:
    """
    Clear all service registries and caches.
    
    Nuclear option for test isolation - clears everything.
    Use sparingly; prefer clear_service_registry() for targeted clearing.
    """
    if not PROMETHEUS_AVAILABLE:
        return
    
    for service_name in list(_SERVICE_REGISTRIES.keys()):
        clear_service_registry(service_name)
    
    _SERVICE_REGISTRIES.clear()
    logger.debug("Cleared all service registries")


def get_or_create_metric(
    metric_class: Type[MetricType],
    name: str,
    documentation: str,
    labelnames: Optional[List[str]] = None,
    registry: Optional[Any] = None,
    service_name: Optional[str] = None,
    **kwargs: Any
) -> MetricType:
    """
    Safely get or create a Prometheus metric.
    
    Returns existing collector if already registered, preventing
    "Duplicated timeseries in CollectorRegistry" errors.
    
    Args:
        metric_class: Counter, Gauge, Histogram, or Summary
        name: Metric name (must be unique within registry)
        documentation: Help text for the metric
        labelnames: Optional list of label names
        registry: CollectorRegistry to use (required if service_name not provided)
        service_name: Service identifier for registry lookup (alternative to registry param)
        **kwargs: Additional arguments passed to metric constructor
    
    Returns:
        Existing or newly created metric instance
    
    Raises:
        ValueError: If neither registry nor service_name provided
    
    Example:
        >>> registry = get_service_registry("inference-service")
        >>> counter = get_or_create_metric(
        ...     Counter,
        ...     "requests_total",
        ...     "Total requests",
        ...     labelnames=["status"],
        ...     registry=registry
        ... )
    """
    if not PROMETHEUS_AVAILABLE:
        # Return noop instance
        return metric_class()  # type: ignore
    
    # Determine registry and service name
    if registry is None and service_name is None:
        raise ValueError("Either 'registry' or 'service_name' must be provided")
    
    if service_name and registry is None:
        registry = get_service_registry(service_name)
    
    # For cache lookup, we need a service identifier
    cache_key = service_name if service_name else id(registry)
    if cache_key not in _SERVICE_METRICS_CACHE:
        _SERVICE_METRICS_CACHE[cache_key] = {}  # type: ignore
    
    cache = _SERVICE_METRICS_CACHE[cache_key]  # type: ignore
    
    # Check cache first
    if name in cache:
        existing = cache[name]
        if isinstance(existing, metric_class):
            logger.debug(f"Returning cached metric: {name}")
            return existing
        else:
            logger.warning(
                f"Metric {name} exists but is wrong type: "
                f"expected {metric_class.__name__}, got {type(existing).__name__}"
            )
    
    # Check if metric already registered in this registry
    if registry and hasattr(registry, '_names_to_collectors'):
        existing_collector = registry._names_to_collectors.get(name)
        if existing_collector is not None:
            if isinstance(existing_collector, metric_class):
                logger.debug(f"Found existing metric in registry: {name}")
                cache[name] = existing_collector
                return existing_collector
            else:
                logger.warning(
                    f"Metric {name} registered with wrong type: "
                    f"expected {metric_class.__name__}, got {type(existing_collector).__name__}"
                )
    
    # Create new metric
    try:
        if labelnames:
            metric = metric_class(name, documentation, labelnames=labelnames, registry=registry, **kwargs)
        else:
            metric = metric_class(name, documentation, registry=registry, **kwargs)
        
        cache[name] = metric
        logger.debug(f"Created new metric: {name}")
        return metric
    
    except ValueError as e:
        if "Duplicated timeseries" in str(e) or "already registered" in str(e):
            # Race condition: another thread registered between our checks
            # Try to find it one more time
            if registry and hasattr(registry, '_collector_to_names'):
                for collector in registry._collector_to_names.keys():
                    if hasattr(collector, '_name') and getattr(collector, '_name') == name:
                        if isinstance(collector, metric_class):
                            logger.debug(f"Found metric after race condition: {name}")
                            cache[name] = collector
                            return collector
            
            logger.error(f"Failed to create or find metric {name}: {e}")
            raise
        else:
            raise


def create_counter(
    name: str,
    documentation: str,
    labelnames: Optional[List[str]] = None,
    registry: Optional[Any] = None,
    service_name: Optional[str] = None
) -> Any:
    """Convenience wrapper for creating Counter metrics."""
    return get_or_create_metric(Counter, name, documentation, labelnames, registry, service_name)


def create_gauge(
    name: str,
    documentation: str,
    labelnames: Optional[List[str]] = None,
    registry: Optional[Any] = None,
    service_name: Optional[str] = None
) -> Any:
    """Convenience wrapper for creating Gauge metrics."""
    return get_or_create_metric(Gauge, name, documentation, labelnames, registry, service_name)


def create_histogram(
    name: str,
    documentation: str,
    labelnames: Optional[List[str]] = None,
    buckets: Optional[tuple] = None,
    registry: Optional[Any] = None,
    service_name: Optional[str] = None
) -> Any:
    """Convenience wrapper for creating Histogram metrics."""
    kwargs = {}
    if buckets:
        kwargs['buckets'] = buckets
    return get_or_create_metric(Histogram, name, documentation, labelnames, registry, service_name, **kwargs)


def create_summary(
    name: str,
    documentation: str,
    labelnames: Optional[List[str]] = None,
    registry: Optional[Any] = None,
    service_name: Optional[str] = None
) -> Any:
    """Convenience wrapper for creating Summary metrics."""
    return get_or_create_metric(Summary, name, documentation, labelnames, registry, service_name)


InstrumentatorType: Type[Any]

try:
    instrumentator_module = importlib.import_module("prometheus_fastapi_instrumentator")
    InstrumentatorType = getattr(instrumentator_module, "Instrumentator")
    FASTAPI_INSTRUMENTATOR_AVAILABLE = True
except (ImportError, AttributeError):
    FASTAPI_INSTRUMENTATOR_AVAILABLE = False

    class InstrumentatorFallback:
        """No-op fallback when prometheus_fastapi_instrumentator is unavailable."""
        def instrument(self, app: Any) -> "InstrumentatorFallback":
            return self

        def expose(self, app: Any) -> None:
            return

    InstrumentatorType = InstrumentatorFallback

def setup_metrics(app: Any) -> None:
    """
    Setup Prometheus metrics for a FastAPI application.
    
    Exposes /metrics endpoint on the application.
    
    Args:
        app: FastAPI application instance
    """
    if not FASTAPI_INSTRUMENTATOR_AVAILABLE:
        logger.warning("prometheus-fastapi-instrumentator not installed, skipping metrics setup")
        return

    InstrumentatorType().instrument(app).expose(app)
