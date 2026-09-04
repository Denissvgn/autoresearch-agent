#!/usr/bin/env python3
"""
Demo script showing the observability library in action.

This script demonstrates:
1. Library initialization
2. Custom span creation 
3. Graceful shutdown
4. Error handling
"""

import asyncio
import os
from pathlib import Path
import sys

# Add the observability library to the path
sys.path.append(str(Path(__file__).parent / "observability"))

from observability import get_tracer, initialize_telemetry, shutdown_telemetry


async def demo_observability():
    """Demonstrate observability library functionality."""
    
    # 1. Initialize telemetry
    os.environ["OTEL_SDK_DISABLED"] = "false"
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"  # Will fail but that's OK
    os.environ["APP_ENV"] = "demo"
    
    initialize_telemetry("demo-service")
    
    # 2. Create custom spans
    tracer = get_tracer(__name__)
    
    with tracer.start_as_current_span("demo_operation") as span:
        span.set_attribute("demo.version", "1.0.0")
        span.set_attribute("demo.environment", "test")
        
        # Nested span
        with tracer.start_as_current_span("nested_operation") as nested_span:
            nested_span.set_attribute("operation.type", "nested")
            nested_span.add_event("Processing started")
            
            # Simulate work
            await asyncio.sleep(0.1)
            
            nested_span.add_event("Processing completed")
            
        span.add_event("All nested operations completed")
    
    # 3. Test error handling
    try:
        with tracer.start_as_current_span("error_test") as span:
            span.set_attribute("test.type", "error_handling")
            raise ValueError("Demo error for testing")
    except ValueError:
        pass
    
    # 4. Test idempotent initialization
    initialize_telemetry("demo-service")  # Should be no-op
    
    # 5. Shutdown
    shutdown_telemetry()
    


if __name__ == "__main__":
    asyncio.run(demo_observability())
