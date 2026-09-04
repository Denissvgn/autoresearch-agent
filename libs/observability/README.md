# Observability Library

Shared OpenTelemetry observability library for TRAID Platform microservices.

## Overview

This library provides a centralized way to initialize OpenTelemetry tracing across all microservices with consistent configuration and instrumentation.

## Features

- **Idempotent Initialization**: Safe to call multiple times
- **Automatic Instrumentation**: HTTPx and Psycopg2 client instrumentation
- **Flexible Configuration**: Environment variable based configuration
- **Graceful Degradation**: Continues operation when collector is unreachable
- **Multiple Sampling Strategies**: Always-on, always-off, ratio-based, and parent-based sampling

## Usage

### Basic Usage

```python
from observability import initialize_telemetry, shutdown_telemetry

# Initialize tracing (typically in main.py)
initialize_telemetry("my-service")

# Shutdown tracing (typically in shutdown handler)
shutdown_telemetry()
```

### Creating Custom Spans

```python
from observability import get_tracer

tracer = get_tracer(__name__)

with tracer.start_as_current_span("my-operation") as span:
    span.set_attribute("key", "value")
    # Your code here
```

### Check if Tracing is Enabled

```python
from observability import is_tracing_enabled

if is_tracing_enabled():
    # Add custom tracing logic
    pass
```

## Configuration

All configuration is done via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_SDK_DISABLED` | `false` | Set to "true" to disable OpenTelemetry entirely |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4318` | OTLP collector endpoint |
| `OTEL_TRACES_SAMPLER` | `parentbased_always_on` | Sampling strategy |
| `APP_ENV` or `ENVIRONMENT` | `development` | Deployment environment |
| `SERVICE_VERSION` | `unknown` | Service version for telemetry |

### Sampling Strategies

- `always_on`: Sample all traces
- `always_off`: Sample no traces
- `parentbased_always_on`: Sample based on parent span (default)
- `parentbased_always_off`: Don't sample unless parent is sampled
- `traceidratio_X.X`: Sample X.X ratio of traces (e.g., `traceidratio_0.1` for 10%)

## Automatic Instrumentations

The library automatically instruments:

- **HTTPx**: HTTP client requests
- **Psycopg2**: PostgreSQL database queries (if available)

Additional instrumentations can be added by services as needed.

## Error Handling

The library is designed to be resilient:

- Missing dependencies are handled gracefully
- Collector connectivity issues don't crash the service
- Invalid configuration falls back to safe defaults
- All errors are logged but don't propagate

## Development

### Running Tests

```bash
cd libs/observability
poetry install
poetry run pytest
```

### Dependencies

Core dependencies are automatically installed:
- opentelemetry-sdk
- opentelemetry-exporter-otlp
- opentelemetry-instrumentation-httpx
- opentelemetry-instrumentation-psycopg2

## Integration with Services

To use in a FastAPI service:

```python
from fastapi import FastAPI
from observability import initialize_telemetry, shutdown_telemetry
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

app = FastAPI()

# Initialize telemetry
initialize_telemetry("my-service")

# Instrument FastAPI
FastAPIInstrumentor.instrument_app(app)

@app.on_event("shutdown")
async def shutdown_event():
    shutdown_telemetry()
```

For more details, see the implementation tasks in the sprint documentation.
