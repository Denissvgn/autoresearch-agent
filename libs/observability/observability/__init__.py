"""
Observability library for TRAID Platform.

This package provides shared utilities for OpenTelemetry tracing,
health checking, and observability across all microservices.
"""

from .health import (
    DependencyCheck,
    DependencyResult,
    DependencyType,
    HealthChecker,
    HealthStatus,
    StandardHealthResponse,
    create_custom_dependency,
    create_database_dependency,
    create_http_dependency,
    create_redis_dependency,
)

__version__ = "0.1.0"


def initialize_telemetry(*args, **kwargs):
    from .otel import initialize_telemetry as _initialize_telemetry

    return _initialize_telemetry(*args, **kwargs)


def initialize_telemetry_from_env(*args, **kwargs):
    from .otel import initialize_telemetry_from_env as _initialize_telemetry_from_env

    return _initialize_telemetry_from_env(*args, **kwargs)


def shutdown_telemetry(*args, **kwargs):
    from .otel import shutdown_telemetry as _shutdown_telemetry

    return _shutdown_telemetry(*args, **kwargs)


def get_tracer(*args, **kwargs):
    from .otel import get_tracer as _get_tracer

    return _get_tracer(*args, **kwargs)


def is_tracing_enabled(*args, **kwargs):
    from .otel import is_tracing_enabled as _is_tracing_enabled

    return _is_tracing_enabled(*args, **kwargs)


def is_observability_enabled(*args, **kwargs):
    from .otel import is_observability_enabled as _is_observability_enabled

    return _is_observability_enabled(*args, **kwargs)


__all__ = [
    # OpenTelemetry
    "initialize_telemetry",
    "initialize_telemetry_from_env",
    "shutdown_telemetry",
    "get_tracer",
    "is_tracing_enabled",
    "is_observability_enabled",
    
    # Health Checking
    "HealthChecker",
    "HealthStatus",
    "DependencyType", 
    "DependencyCheck",
    "DependencyResult",
    "StandardHealthResponse",
    "create_http_dependency",
    "create_redis_dependency", 
    "create_database_dependency",
    "create_custom_dependency",
]
