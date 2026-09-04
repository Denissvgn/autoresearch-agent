"""
OpenTelemetry SDK initialization and configuration for TRAID Platform.

This module provides a centralized way to initialize OpenTelemetry tracing
across all microservices with consistent configuration and instrumentation.
"""

import logging
import os
from contextlib import nullcontext
from typing import Any

logger = logging.getLogger(__name__)

# Global state to ensure idempotent initialization
_initialized = False
_tracer_provider: Any | None = None
_otel_missing_warned = False

_TRUE_VALUES = {"1", "true", "yes", "y", "on"}


class _NoopSpan:
    """Minimal span shim used when OpenTelemetry is unavailable."""

    def set_attribute(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def set_status(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def record_exception(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def end(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def is_recording(self) -> bool:
        return False


class _NoopTracer:
    """Minimal tracer shim used when OpenTelemetry is unavailable."""

    def start_span(self, *_args: Any, **_kwargs: Any) -> _NoopSpan:
        return _NoopSpan()

    def start_as_current_span(self, *_args: Any, **_kwargs: Any):
        return nullcontext(_NoopSpan())


def _load_otel_deps() -> dict[str, Any] | None:
    """Load OpenTelemetry dependencies lazily.

    Many services import ``libs.observability`` only for headers, correlation IDs,
    or Prometheus helpers. Tracing dependencies are optional unless a service
    explicitly enables OpenTelemetry at runtime.
    """

    global _otel_missing_warned
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import (
            ALWAYS_OFF,
            ALWAYS_ON,
            ParentBased,
            TraceIdRatioBased,
        )
    except ImportError as exc:
        if is_observability_enabled() and not _otel_missing_warned:
            logger.warning("OpenTelemetry dependencies unavailable; tracing disabled: %s", exc)
            _otel_missing_warned = True
        return None

    return {
        "trace": trace,
        "OTLPSpanExporter": OTLPSpanExporter,
        "DEPLOYMENT_ENVIRONMENT": DEPLOYMENT_ENVIRONMENT,
        "SERVICE_NAME": SERVICE_NAME,
        "Resource": Resource,
        "TracerProvider": TracerProvider,
        "BatchSpanProcessor": BatchSpanProcessor,
        "ALWAYS_OFF": ALWAYS_OFF,
        "ALWAYS_ON": ALWAYS_ON,
        "ParentBased": ParentBased,
        "TraceIdRatioBased": TraceIdRatioBased,
    }


def _get_sampler(deps: dict[str, Any]):
    """Get the configured sampler based on environment variables."""
    sampler_name = os.getenv("OTEL_TRACES_SAMPLER", "parentbased_always_on").lower()
    
    if sampler_name == "always_on":
        return deps["ALWAYS_ON"]
    elif sampler_name == "always_off":
        return deps["ALWAYS_OFF"]
    elif sampler_name.startswith("traceidratio"):
        # Format: traceidratio_0.1 for 10% sampling
        try:
            ratio = float(sampler_name.split("_")[1])
            return deps["TraceIdRatioBased"](ratio)
        except (IndexError, ValueError):
            logger.warning(f"Invalid traceidratio format: {sampler_name}, using always_on")
            return deps["ALWAYS_ON"]
    elif sampler_name == "parentbased_always_off":
        return deps["ParentBased"](deps["ALWAYS_OFF"])
    else:  # parentbased_always_on (default)
        return deps["ParentBased"](deps["ALWAYS_ON"])


def _get_trace_endpoint() -> str:
    """Resolve the OTLP trace endpoint using platform-compatible env vars."""

    traces_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    if traces_endpoint:
        return traces_endpoint

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/v1/traces"):
        return endpoint
    return f"{endpoint}/v1/traces"


def is_observability_enabled(env_var: str = "OBSERVABILITY_ENABLED") -> bool:
    """Return whether service-level observability should initialize."""

    return os.getenv(env_var, "false").lower() in _TRUE_VALUES


def _setup_client_instrumentations() -> None:
    """Set up automatic instrumentation for HTTP clients and database drivers."""
    # Always instrument httpx for HTTP client tracing
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        if not HTTPXClientInstrumentor().is_instrumented_by_opentelemetry:
            HTTPXClientInstrumentor().instrument()
            logger.debug("HTTPx client instrumentation enabled")
    except ImportError:
        logger.debug("HTTPx not available, skipping instrumentation")
    except Exception as e:
        logger.warning(f"Failed to instrument HTTPx: {e}")

    # Conditionally instrument psycopg2 for PostgreSQL tracing
    try:
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
        if not Psycopg2Instrumentor().is_instrumented_by_opentelemetry:
            Psycopg2Instrumentor().instrument()
            logger.debug("Psycopg2 instrumentation enabled")
    except ImportError:
        logger.debug("Psycopg2 not available, skipping instrumentation")
    except Exception as e:
        logger.warning(f"Failed to instrument Psycopg2: {e}")

    # Conditionally instrument SQLAlchemy for database tracing (works with asyncpg)
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        if not SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry:
            SQLAlchemyInstrumentor().instrument()
            logger.debug("SQLAlchemy instrumentation enabled")
    except ImportError:
        logger.debug("SQLAlchemy not available, skipping instrumentation")
    except Exception as e:
        logger.warning(f"Failed to instrument SQLAlchemy: {e}")


def initialize_telemetry(service_name: str) -> None:
    """
    Initialize OpenTelemetry tracing for a service.
    
    This function is idempotent - calling it multiple times will not
    create duplicate exporters or processors.
    
    Args:
        service_name: The name of the service (e.g., "autotrade-service")
        
    Environment Variables:
        OTEL_SDK_DISABLED: Set to "true" to disable OpenTelemetry entirely
        OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint (default: http://otel-collector:4318)
        OTEL_TRACES_SAMPLER: Sampling strategy (default: parentbased_always_on)
        APP_ENV or ENVIRONMENT: Deployment environment (default: development)
    """
    global _initialized, _tracer_provider
    
    # Check if telemetry is disabled
    if os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true":
        logger.debug("OpenTelemetry SDK disabled via OTEL_SDK_DISABLED")
        return

    deps = _load_otel_deps()
    if deps is None:
        return
    
    # Prevent duplicate initialization
    if _initialized:
        logger.debug("OpenTelemetry already initialized, skipping")
        return
    
    try:
        # Get configuration from environment
        endpoint = _get_trace_endpoint()
        environment = (
            os.getenv("APP_ENV") or 
            os.getenv("ENVIRONMENT") or 
            "development"
        )
        
        # Create resource with service metadata
        resource = deps["Resource"].create({
            deps["SERVICE_NAME"]: service_name,
            deps["DEPLOYMENT_ENVIRONMENT"]: environment,
            "service.version": os.getenv("SERVICE_VERSION", "unknown"),
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.language": "python",
        })
        
        # Create tracer provider with sampler
        sampler = _get_sampler(deps)
        _tracer_provider = deps["TracerProvider"](
            resource=resource,
            sampler=sampler
        )
        
        # Create OTLP exporter
        try:
            exporter = deps["OTLPSpanExporter"](
                endpoint=endpoint,
                timeout=10,  # 10 second timeout
            )
            
            # Create span processor
            processor = deps["BatchSpanProcessor"](
                span_exporter=exporter,
                max_queue_size=2048,
                max_export_batch_size=512,
                export_timeout_millis=30000,  # 30 seconds
                schedule_delay_millis=1000,   # 1 second
            )
            
            _tracer_provider.add_span_processor(processor)
            logger.debug(f"OTLP exporter configured for endpoint: {endpoint}")
            
        except Exception as e:
            logger.warning(f"Failed to configure OTLP exporter: {e}")
            # Continue without exporter - spans will be generated but not exported
        
        # Set the global tracer provider
        deps["trace"].set_tracer_provider(_tracer_provider)
        
        # Set up automatic instrumentations
        _setup_client_instrumentations()
        
        _initialized = True
        logger.info(f"OpenTelemetry initialized for service: {service_name} (env: {environment})")
        
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        # Don't raise - allow the service to continue without tracing


def initialize_telemetry_from_env(
    service_name: str,
    *,
    enabled_env: str = "OBSERVABILITY_ENABLED",
) -> bool:
    """Initialize OpenTelemetry only when the service observability flag is enabled."""

    if not is_observability_enabled(enabled_env):
        logger.debug("OpenTelemetry not initialized because %s is not enabled", enabled_env)
        return False
    initialize_telemetry(service_name)
    return is_tracing_enabled()


def shutdown_telemetry() -> None:
    """
    Shutdown OpenTelemetry and flush any pending spans.
    
    This should be called during application shutdown to ensure
    all spans are exported before the process exits.
    """
    global _initialized, _tracer_provider
    
    if not _initialized or _tracer_provider is None:
        return
    
    try:
        # Shutdown the tracer provider to flush pending spans
        _tracer_provider.shutdown()
        logger.debug("OpenTelemetry tracer provider shutdown completed")
    except Exception as e:
        logger.warning(f"Error during OpenTelemetry shutdown: {e}")
    finally:
        _initialized = False
        _tracer_provider = None


def get_tracer(name: str) -> Any:
    """
    Get a tracer instance for creating custom spans.
    
    Args:
        name: The name of the tracer (typically __name__ of the calling module)
        
    Returns:
        A tracer instance for creating spans
    """
    deps = _load_otel_deps()
    if deps is None:
        return _NoopTracer()
    return deps["trace"].get_tracer(name)


def is_tracing_enabled() -> bool:
    """
    Check if tracing is currently enabled and initialized.
    
    Returns:
        True if tracing is enabled and initialized, False otherwise
    """
    return _initialized and _tracer_provider is not None
