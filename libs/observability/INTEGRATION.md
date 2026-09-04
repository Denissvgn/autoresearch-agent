# Integration Example: FastAPI Service

This document shows how to integrate the observability library with a FastAPI service.

## Quick Start

### 1. Add the dependency to your service

In your service's `pyproject.toml`:

```toml
[tool.poetry.dependencies]
# ... other dependencies
observability = { path = "../../libs/observability", develop = true }

# Add FastAPI instrumentation dependency
opentelemetry-instrumentation-fastapi = "^0.55b1"
```

### 2. Initialize telemetry in your main.py

```python
# services/your-service/src/main.py
import os
from fastapi import FastAPI
from observability import initialize_telemetry, shutdown_telemetry

# Initialize telemetry BEFORE creating FastAPI app
initialize_telemetry("your-service")

# Create FastAPI app
app = FastAPI(title="Your Service", version="1.0.0")

# Add instrumentation for FastAPI
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)
except ImportError:
    pass  # FastAPI instrumentation not available

@app.on_event("startup")
async def startup_event():
    """Application startup."""
    pass

@app.on_event("shutdown") 
async def shutdown_event():
    """Application shutdown."""
    shutdown_telemetry()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/v1/example")
async def example_endpoint():
    """Example endpoint with automatic tracing."""
    return {"message": "Hello World"}
```

### 3. Adding custom spans

```python
from observability import get_tracer

tracer = get_tracer(__name__)

@app.post("/api/v1/process")
async def process_data(data: dict):
    with tracer.start_as_current_span("process_data") as span:
        span.set_attribute("data.size", len(data))
        span.set_attribute("operation", "process")
        
        # Your business logic here
        result = await some_processing_function(data)
        
        span.set_attribute("result.status", "success")
        return result

async def some_processing_function(data: dict):
    """Function with custom tracing."""
    with tracer.start_as_current_span("processing_step") as span:
        span.add_event("Processing started")
        
        # Simulate processing
        await asyncio.sleep(0.1)
        
        span.add_event("Processing completed")
        return {"processed": True}
```

### 4. Environment Configuration

Create a `.env` file or set environment variables:

```bash
# OpenTelemetry Configuration
OTEL_SDK_DISABLED=false
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_TRACES_SAMPLER=parentbased_always_on
APP_ENV=development
SERVICE_VERSION=1.0.0

# Service specific config
SERVICE_NAME=your-service
```

### 5. Docker Compose Integration

In your `docker-compose.yml`:

```yaml
services:
  your-service:
    build: ./services/your-service
    environment:
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
      - APP_ENV=production
      - SERVICE_VERSION=${SERVICE_VERSION:-latest}
    depends_on:
      - otel-collector
    networks:
      - traid-network

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./docker/otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC receiver
      - "4318:4318"   # OTLP HTTP receiver
      - "8889:8889"   # Prometheus metrics
    networks:
      - traid-network
```

## Advanced Usage

### Custom Span Attributes

```python
from observability import get_tracer
from opentelemetry.trace import Status, StatusCode

tracer = get_tracer(__name__)

@app.post("/api/v1/trade")
async def execute_trade(trade_request: TradeRequest):
    with tracer.start_as_current_span("execute_trade") as span:
        # Add business context
        span.set_attribute("trade.symbol", trade_request.symbol)
        span.set_attribute("trade.amount", trade_request.amount)
        span.set_attribute("trade.side", trade_request.side)
        span.set_attribute("user.id", trade_request.user_id)
        
        try:
            result = await trading_service.execute(trade_request)
            
            # Mark success
            span.set_status(Status(StatusCode.OK))
            span.set_attribute("trade.order_id", result.order_id)
            
            return result
            
        except Exception as e:
            # Mark error
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
```

### Distributed Tracing with HTTP Calls

```python
import httpx
from observability import get_tracer

tracer = get_tracer(__name__)

async def call_external_service(user_id: str):
    """Example of distributed tracing across services."""
    with tracer.start_as_current_span("call_user_service") as span:
        span.set_attribute("http.url", "http://identity-service/api/v1/users")  # Updated Task 14: consolidated service
        span.set_attribute("user.id", user_id)
        
        async with httpx.AsyncClient() as client:
            # HTTPx is automatically instrumented
            response = await client.get(
                f"http://identity-service/api/v1/users/{user_id}"  # Updated Task 14: consolidated service
            )
            
            span.set_attribute("http.status_code", response.status_code)
            return response.json()
```

### Database Query Tracing

```python
import asyncpg
from observability import get_tracer

tracer = get_tracer(__name__)

async def get_user_trades(user_id: str):
    """Database queries are automatically traced via psycopg2 instrumentation."""
    with tracer.start_as_current_span("get_user_trades") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("db.operation", "select")
        
        # Database call (automatically instrumented)
        async with database.transaction():
            trades = await database.fetch_all(
                "SELECT * FROM trades WHERE user_id = $1 ORDER BY created_at DESC",
                user_id
            )
            
        span.set_attribute("db.rows_returned", len(trades))
        return trades
```

## Monitoring and Alerting

### Health Check with Tracing Status

```python
from observability import is_tracing_enabled

@app.get("/health/detailed")
async def detailed_health_check():
    return {
        "status": "healthy",
        "tracing_enabled": is_tracing_enabled(),
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Metrics Integration

```python
from observability import get_tracer
from prometheus_client import Counter, Histogram

tracer = get_tracer(__name__)

# Custom metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')

@app.middleware("http")
async def add_metrics_and_tracing(request: Request, call_next):
    start_time = time.time()
    
    with tracer.start_as_current_span("http_request") as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", str(request.url))
        
        response = await call_next(request)
        
        # Record metrics
        request_count.labels(
            method=request.method,
            endpoint=request.url.path
        ).inc()
        
        duration = time.time() - start_time
        request_duration.observe(duration)
        
        # Add response attributes
        span.set_attribute("http.status_code", response.status_code)
        span.set_attribute("http.response_size", len(response.body) if hasattr(response, 'body') else 0)
        
    return response
```

## Best Practices

1. **Initialize Early**: Call `initialize_telemetry()` before creating the FastAPI app
2. **Use Context**: Always use spans to provide business context, not just technical details
3. **Error Handling**: Always record exceptions and set error status on spans
4. **Resource Cleanup**: Call `shutdown_telemetry()` during application shutdown
5. **Environment Specific**: Use different sampling rates for different environments
6. **Security**: Never trace sensitive data like passwords or API keys

## Troubleshooting

### Common Issues

1. **No traces appearing**: Check that `OTEL_SDK_DISABLED` is not set to `true`
2. **Collector unreachable**: Verify the `OTEL_EXPORTER_OTLP_ENDPOINT` is correct
3. **Missing spans**: Ensure the collector and backend are running and accessible
4. **Performance impact**: Adjust sampling rate in production environments

### Debug Mode

```python
import logging

# Enable OpenTelemetry debug logging
logging.getLogger("opentelemetry").setLevel(logging.DEBUG)
```
