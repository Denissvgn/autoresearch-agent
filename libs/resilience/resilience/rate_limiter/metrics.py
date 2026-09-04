"""
Prometheus Metrics Integration for Rate Limiting

This module provides comprehensive metrics collection for rate limiting operations
using Prometheus client library. It tracks various aspects of rate limiting
performance, usage patterns, and backend health.

Key Metrics:
- Request counts by outcome (allowed/denied)
- Response times for rate limit checks
- Rate limit remaining capacity
- Backend operation performance
- Error rates and types
- Wait times for blocked requests

Design Principles:
- Low overhead metrics collection
- Configurable label sets to control cardinality
- Graceful degradation if metrics collection fails
- Compatible with existing Prometheus infrastructure
- Support for custom metric collectors
"""
from enum import Enum
from typing import Any, Dict, Optional, Set, cast

try:
    from prometheus_client import Counter, Gauge, Histogram, Info
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from .core import MetricsCollector


class MetricLabels(str, Enum):
    """Standard metric labels for rate limiting."""
    SERVICE = "service"
    EXCHANGE = "exchange"
    ENDPOINT_TYPE = "endpoint_type"
    STRATEGY = "strategy"
    BACKEND = "backend"
    STATUS = "status"
    ERROR_TYPE = "error_type"
    KEY_PREFIX = "key_prefix"


class RateLimitStatus(str, Enum):
    """Rate limit request outcomes."""
    ALLOWED = "allowed"
    DENIED = "denied"
    ERROR = "error"
    THROTTLED = "throttled"


class BackendOperation(str, Enum):
    """Backend operation types."""
    GET = "get"
    SET = "set"
    UPDATE = "update"
    SCRIPT = "script"
    CLEANUP = "cleanup"
    HEALTH_CHECK = "health_check"


class PrometheusMetricsCollector:
    """
    Prometheus metrics collector for rate limiting operations.
    
    This collector provides comprehensive metrics for monitoring rate limiting
    performance, usage patterns, and system health.
    """
    
    def __init__(
        self, 
        service_name: str = "unknown",
        enable_high_cardinality: bool = False,
        custom_labels: Optional[Dict[str, str]] = None
    ):
        """
        Initialize Prometheus metrics collector.
        
        Args:
            service_name: Name of the service using rate limiting
            enable_high_cardinality: Whether to include high-cardinality labels
            custom_labels: Additional labels to include in all metrics
        """
        if not PROMETHEUS_AVAILABLE:
            raise RuntimeError(
                "prometheus_client package required for Prometheus metrics. "
                "Install with: pip install prometheus-client"
            )
        
        self.service_name = service_name
        self.enable_high_cardinality = enable_high_cardinality
        self.custom_labels = custom_labels or {}
        
        # Track which exchanges/keys we've seen to control cardinality
        self._known_exchanges: Set[str] = set()
        self._known_keys: Set[str] = set()
        self._max_exchanges = 50
        self._max_keys = 1000
        
        # Initialize metrics
        self._init_metrics()
    
    def _get_base_labels(self) -> list[str]:
        """Get base labels for all metrics."""
        labels = [MetricLabels.SERVICE.value]
        
        if self.enable_high_cardinality:
            labels.extend([
                MetricLabels.EXCHANGE.value,
                MetricLabels.ENDPOINT_TYPE.value,
                MetricLabels.STRATEGY.value,
                MetricLabels.BACKEND.value
            ])
        else:
            labels.extend([
                MetricLabels.STRATEGY.value,
                MetricLabels.BACKEND.value
            ])
        
        # Add custom labels (converting keys to strings)
        labels.extend(list(self.custom_labels.keys()))
        
        return labels
    
    def _init_metrics(self) -> None:
        """Initialize all Prometheus metrics."""
        base_labels = self._get_base_labels()
        
        # Request counting metrics
        self.requests_total = Counter(
            'rate_limit_requests_total',
            'Total number of rate limit requests',
            labelnames=base_labels + [MetricLabels.STATUS]
        )
        
        self.requests_denied_total = Counter(
            'rate_limit_requests_denied_total', 
            'Total number of denied rate limit requests',
            labelnames=base_labels
        )
        
        # Response time metrics
        self.request_duration = Histogram(
            'rate_limit_request_duration_seconds',
            'Time spent processing rate limit requests',
            labelnames=base_labels,
            buckets=(.0001, .0005, .001, .005, .01, .025, .05, .1, .25, .5, 1.0, 2.5, 5.0, 10.0, float('inf'))
        )
        
        # Capacity metrics
        self.tokens_remaining = Gauge(
            'rate_limit_tokens_remaining',
            'Remaining rate limit capacity',
            labelnames=base_labels
        )
        
        # Wait time metrics
        self.wait_time_seconds = Histogram(
            'rate_limit_wait_time_seconds',
            'Time spent waiting due to rate limiting',
            labelnames=base_labels,
            buckets=(.01, .05, .1, .25, .5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float('inf'))
        )
        
        # Backend operation metrics
        backend_labels = [MetricLabels.SERVICE, MetricLabels.BACKEND, "operation"]
        
        self.backend_operations_total = Counter(
            'rate_limit_backend_operations_total',
            'Total number of backend operations',
            labelnames=backend_labels + [MetricLabels.STATUS]
        )
        
        self.backend_operation_duration = Histogram(
            'rate_limit_backend_operation_duration_seconds',
            'Time spent on backend operations',
            labelnames=backend_labels,
            buckets=(.0001, .0005, .001, .005, .01, .025, .05, .1, .25, .5, 1.0, 2.5, 5.0, float('inf'))
        )
        
        # Error metrics
        self.errors_total = Counter(
            'rate_limit_errors_total',
            'Total number of rate limiting errors',
            labelnames=[MetricLabels.SERVICE, MetricLabels.BACKEND, MetricLabels.ERROR_TYPE]
        )
        
        # Rate limiter configuration info
        self.rate_limiter_info = Info(
            'rate_limit_config',
            'Rate limiter configuration information',
            labelnames=[MetricLabels.SERVICE]
        )
        
        # Circuit breaker metrics (for Redis backend)
        self.circuit_breaker_state = Gauge(
            'rate_limit_circuit_breaker_open',
            'Whether the circuit breaker is open (1) or closed (0)',
            labelnames=[MetricLabels.SERVICE, MetricLabels.BACKEND]
        )
        
        # Memory usage metrics (for memory backend) 
        self.memory_usage_bytes = Gauge(
            'rate_limit_memory_usage_bytes',
            'Memory usage of rate limiter backend',
            labelnames=[MetricLabels.SERVICE, MetricLabels.BACKEND]
        )
    
    def _should_track_exchange(self, exchange: str) -> bool:
        """Check if we should track metrics for this exchange (cardinality control)."""
        if not self.enable_high_cardinality:
            return False
        
        if exchange in self._known_exchanges:
            return True
        
        if len(self._known_exchanges) < self._max_exchanges:
            self._known_exchanges.add(exchange)
            return True
        
        return False
    
    def _should_track_key(self, key: str) -> bool:
        """Check if we should track metrics for this key (cardinality control).""" 
        if not self.enable_high_cardinality:
            return False
        
        if key in self._known_keys:
            return True
        
        if len(self._known_keys) < self._max_keys:
            self._known_keys.add(key)
            return True
        
        return False
    
    def _get_labels(
        self, 
        strategy: str = "unknown",
        backend: str = "unknown", 
        exchange: str = "unknown",
        endpoint_type: str = "unknown",
        **extra_labels
    ) -> Dict[str, str]:
        """Build label dictionary for metrics."""
        labels = {
            MetricLabels.SERVICE.value: self.service_name,
            MetricLabels.STRATEGY.value: strategy,
            MetricLabels.BACKEND.value: backend
        }
        
        if self.enable_high_cardinality:
            if self._should_track_exchange(exchange):
                labels[MetricLabels.EXCHANGE.value] = exchange
            else:
                labels[MetricLabels.EXCHANGE.value] = "other"
            
            labels[MetricLabels.ENDPOINT_TYPE.value] = endpoint_type
        
        # Add custom labels (converting enum keys to string values)
        for key, value in self.custom_labels.items():
            labels[key] = value
        
        # Add any extra labels provided (convert to strings)
        for key, value in extra_labels.items():
            labels[str(key)] = str(value)
        
        return labels
    
    def record_request(
        self, 
        key: str, 
        allowed: bool, 
        remaining: int, 
        wait_time: float = 0.0,
        duration: float = 0.0,
        **labels
    ) -> None:
        """
        Record a rate limit request.
        
        Args:
            key: Rate limit key
            allowed: Whether request was allowed
            remaining: Remaining capacity
            wait_time: Time spent waiting
            duration: Time spent processing request
            **labels: Additional labels (strategy, backend, exchange, etc.)
        """
        try:
            # Extract exchange and endpoint from key if possible
            key_parts = key.split(":")
            exchange = labels.get("exchange", key_parts[0] if len(key_parts) > 1 else "unknown")
            endpoint_type = labels.get("endpoint_type", key_parts[1] if len(key_parts) > 2 else "requests")
            
            metric_labels = self._get_labels(
                exchange=exchange,
                endpoint_type=endpoint_type,
                **labels
            )
            
            # Record request outcome
            status = RateLimitStatus.ALLOWED if allowed else RateLimitStatus.DENIED
            self.requests_total.labels(**metric_labels, status=status.value).inc()
            
            if not allowed:
                self.requests_denied_total.labels(**metric_labels).inc()
            
            # Record capacity
            if remaining >= 0:
                self.tokens_remaining.labels(**metric_labels).set(remaining)
            
            # Record wait time if applicable
            if wait_time > 0:
                self.wait_time_seconds.labels(**metric_labels).observe(wait_time)
            
            # Record processing duration
            if duration > 0:
                self.request_duration.labels(**metric_labels).observe(duration)
            
        except Exception:
            # Never fail due to metrics collection
            pass
    
    def record_backend_operation(
        self, 
        backend: str, 
        operation: str, 
        duration: float, 
        success: bool
    ) -> None:
        """
        Record backend operation metrics.
        
        Args:
            backend: Backend type (memory, redis)
            operation: Operation type (get, set, update, etc.)
            duration: Operation duration in seconds
            success: Whether operation succeeded
        """
        try:
            labels = {
                MetricLabels.SERVICE: self.service_name,
                MetricLabels.BACKEND: backend,
                "operation": operation
            }
            
            status = RateLimitStatus.ALLOWED if success else RateLimitStatus.ERROR
            self.backend_operations_total.labels(**labels, status=status.value).inc()
            
            if duration > 0:
                self.backend_operation_duration.labels(**labels).observe(duration)
            
        except Exception:
            pass
    
    def record_error(self, backend: str, error_type: str, error_message: str = "") -> None:
        """
        Record rate limiting errors.
        
        Args:
            backend: Backend where error occurred
            error_type: Type of error (connection, timeout, etc.)
            error_message: Detailed error message
        """
        try:
            self.errors_total.labels(
                service=self.service_name,
                backend=backend,
                error_type=error_type
            ).inc()
        except Exception:
            pass
    
    def update_circuit_breaker_state(self, backend: str, is_open: bool) -> None:
        """Update circuit breaker state metric."""
        try:
            self.circuit_breaker_state.labels(
                service=self.service_name,
                backend=backend
            ).set(1 if is_open else 0)
        except Exception:
            pass
    
    def update_memory_usage(self, backend: str, bytes_used: int) -> None:
        """Update memory usage metric."""
        try:
            self.memory_usage_bytes.labels(
                service=self.service_name,
                backend=backend
            ).set(bytes_used)
        except Exception:
            pass
    
    def update_config_info(self, config_info: Dict[str, Any]) -> None:
        """Update rate limiter configuration information."""
        try:
            # Convert config to string representation for info metric
            info_dict = {}
            for key, value in config_info.items():
                info_dict[key] = str(value)
            
            self.rate_limiter_info.labels(service=self.service_name).info(info_dict)
        except Exception:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get metrics collector statistics."""
        return {
            "collector_type": "prometheus",
            "service_name": self.service_name,
            "high_cardinality_enabled": self.enable_high_cardinality,
            "known_exchanges": len(self._known_exchanges),
            "known_keys": len(self._known_keys),
            "max_exchanges": self._max_exchanges,
            "max_keys": self._max_keys,
            "custom_labels": self.custom_labels
        }


class NoOpMetricsCollector:
    """
    No-operation metrics collector for when Prometheus is not available.
    
    This provides the same interface as PrometheusMetricsCollector but
    does nothing, allowing the rate limiter to work without metrics.
    """
    
    def __init__(self, *args, **kwargs):
        pass
    
    def record_request(self, *args, **kwargs) -> None:
        pass
    
    def record_backend_operation(self, *args, **kwargs) -> None:
        pass
    
    def record_error(self, *args, **kwargs) -> None:
        pass
    
    def update_circuit_breaker_state(self, *args, **kwargs) -> None:
        pass
    
    def update_memory_usage(self, *args, **kwargs) -> None:
        pass
    
    def update_config_info(self, *args, **kwargs) -> None:
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        return {"collector_type": "noop"}


class MetricsManager:
    """
    Manager for rate limiting metrics that handles collector lifecycle.
    
    This provides a convenient way to manage metrics collectors and
    ensures proper initialization and cleanup.
    """
    
    def __init__(self):
        self._collectors: Dict[str, MetricsCollector] = {}
        self._default_collector: Optional[MetricsCollector] = None
    
    def register_collector(self, name: str, collector: MetricsCollector) -> None:
        """Register a metrics collector."""
        self._collectors[name] = collector
    
    def get_collector(self, name: str) -> Optional[MetricsCollector]:
        """Get a registered metrics collector."""
        return self._collectors.get(name)
    
    def set_default_collector(self, collector: MetricsCollector) -> None:
        """Set the default metrics collector."""
        self._default_collector = collector
    
    def get_default_collector(self) -> MetricsCollector:
        """Get the default metrics collector."""
        if self._default_collector is None:
            # Create appropriate default collector
            if PROMETHEUS_AVAILABLE:
                self._default_collector = PrometheusMetricsCollector()
            else:
                self._default_collector = NoOpMetricsCollector()
        
        return self._default_collector
    
    def create_prometheus_collector(
        self, 
        service_name: str,
        **kwargs
    ) -> MetricsCollector:
        """
        Create and register a Prometheus metrics collector.
        
        Args:
            service_name: Name of the service
            **kwargs: Additional arguments for PrometheusMetricsCollector
            
        Returns:
            Created metrics collector
        """
        if not PROMETHEUS_AVAILABLE:
            return NoOpMetricsCollector()
        
        collector = PrometheusMetricsCollector(service_name=service_name, **kwargs)
        self.register_collector(service_name, collector)
        
        if self._default_collector is None:
            self.set_default_collector(collector)
        
        return collector
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics from all registered collectors."""
        stats = {}
        
        for name, collector in self._collectors.items():
            try:
                if hasattr(collector, 'get_stats'):
                    # Use cast to handle the type checker issue
                    stats[name] = cast(Any, collector).get_stats()
            except Exception:
                stats[name] = {"error": "Failed to get stats"}
        
        if self._default_collector and hasattr(self._default_collector, 'get_stats'):
            try:
                # Use cast to handle the type checker issue
                stats["default"] = cast(Any, self._default_collector).get_stats()
            except Exception:
                stats["default"] = {"error": "Failed to get stats"}
        
        return stats


# Global metrics manager instance
metrics_manager = MetricsManager()


def get_metrics_collector(service_name: Optional[str] = None) -> MetricsCollector:
    """
    Get a metrics collector for the specified service.
    
    Args:
        service_name: Name of the service (uses default if None)
        
    Returns:
        Metrics collector instance
    """
    if service_name:
        collector = metrics_manager.get_collector(service_name)
        if collector:
            return collector
    
    return metrics_manager.get_default_collector()


def create_metrics_collector(
    service_name: str,
    enable_high_cardinality: bool = False,
    custom_labels: Optional[Dict[str, str]] = None
) -> MetricsCollector:
    """
    Create a new metrics collector for a service.
    
    Args:
        service_name: Name of the service
        enable_high_cardinality: Whether to include high-cardinality labels
        custom_labels: Additional labels for all metrics
        
    Returns:
        Created metrics collector
    """
    return metrics_manager.create_prometheus_collector(
        service_name=service_name,
        enable_high_cardinality=enable_high_cardinality,
        custom_labels=custom_labels
    )