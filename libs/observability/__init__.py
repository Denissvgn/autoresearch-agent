"""Observability utilities for monitoring and tracing."""

from .correlation import (
    CorrelationIdMiddleware,
    CorrelationLogFilter,
    correlation_id_var,
    get_correlation_id,
)
from .headers import (
    API_KEY_HEADER,
    CORRELATION_ID_HEADER,
    PLATFORM_HEADER_SPECS,
    TENANT_ID_HEADER,
    PlatformHeaders,
    bind_platform_headers,
    document_platform_headers,
    ensure_app_platform_headers,
    ensure_platform_headers,
    ensure_router_platform_headers,
    get_bound_platform_headers,
    get_platform_headers,
)
from .metrics import (
    clear_all_service_registries,
    clear_service_registry,
    create_counter,
    create_gauge,
    create_histogram,
    create_summary,
    get_or_create_metric,
    get_service_registry,
)
from .tenant import (
    TenantIdMiddleware,
    TenantLogFilter,
    get_tenant_id,
    tenant_id_var,
)


def initialize_telemetry(*args, **kwargs):
    from .observability.otel import initialize_telemetry as _initialize_telemetry

    return _initialize_telemetry(*args, **kwargs)


def initialize_telemetry_from_env(*args, **kwargs):
    from .observability.otel import initialize_telemetry_from_env as _initialize_telemetry_from_env

    return _initialize_telemetry_from_env(*args, **kwargs)


def shutdown_telemetry(*args, **kwargs):
    from .observability.otel import shutdown_telemetry as _shutdown_telemetry

    return _shutdown_telemetry(*args, **kwargs)


def get_tracer(*args, **kwargs):
    from .observability.otel import get_tracer as _get_tracer

    return _get_tracer(*args, **kwargs)


def is_tracing_enabled(*args, **kwargs):
    from .observability.otel import is_tracing_enabled as _is_tracing_enabled

    return _is_tracing_enabled(*args, **kwargs)


def is_observability_enabled(*args, **kwargs):
    from .observability.otel import is_observability_enabled as _is_observability_enabled

    return _is_observability_enabled(*args, **kwargs)


__all__ = [
    "CorrelationIdMiddleware",
    "CorrelationLogFilter",
    "get_correlation_id",
    "correlation_id_var",
    "API_KEY_HEADER",
    "PlatformHeaders",
    "CORRELATION_ID_HEADER",
    "TENANT_ID_HEADER",
    "PLATFORM_HEADER_SPECS",
    "document_platform_headers",
    "get_platform_headers",
    "get_bound_platform_headers",
    "bind_platform_headers",
    "ensure_platform_headers",
    "ensure_app_platform_headers",
    "ensure_router_platform_headers",
    "TenantIdMiddleware",
    "TenantLogFilter",
    "get_tenant_id",
    "tenant_id_var",
    "get_service_registry",
    "get_or_create_metric",
    "create_counter",
    "create_gauge",
    "create_histogram",
    "create_summary",
    "clear_service_registry",
    "clear_all_service_registries",
    "initialize_telemetry",
    "initialize_telemetry_from_env",
    "shutdown_telemetry",
    "get_tracer",
    "is_tracing_enabled",
    "is_observability_enabled",
]
