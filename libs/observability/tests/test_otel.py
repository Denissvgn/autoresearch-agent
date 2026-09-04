"""Tests for the observability library."""

import os
from unittest.mock import MagicMock, patch

from observability.otel import (
    _get_sampler,
    get_tracer,
    initialize_telemetry,
    initialize_telemetry_from_env,
    is_observability_enabled,
    is_tracing_enabled,
    shutdown_telemetry,
)


class TestObservabilityLibrary:
    """Test suite for the observability library."""

    def setup_method(self):
        """Reset global state before each test."""
        # Reset the global state
        import observability.otel as otel_module
        otel_module._initialized = False
        otel_module._tracer_provider = None
        
        # Clear environment variables
        env_vars = [
            "OTEL_SDK_DISABLED",
            "OTEL_EXPORTER_OTLP_ENDPOINT", 
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            "OTEL_TRACES_SAMPLER",
            "OBSERVABILITY_ENABLED",
            "APP_ENV",
            "ENVIRONMENT",
            "SERVICE_VERSION"
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

    def test_sdk_disabled(self):
        """Test that initialization is skipped when SDK is disabled."""
        os.environ["OTEL_SDK_DISABLED"] = "true"
        
        initialize_telemetry("test-service")
        
        assert not is_tracing_enabled()

    def test_basic_initialization(self):
        """Test basic telemetry initialization."""
        with patch("observability.otel.trace.set_tracer_provider") as mock_set_provider:
            with patch("observability.otel.OTLPSpanExporter"):
                with patch(
                    "observability.otel._setup_client_instrumentations"
                ) as mock_instrumentation:
                    
                    initialize_telemetry("test-service")
                    
                    assert is_tracing_enabled()
                    mock_set_provider.assert_called_once()
                    mock_instrumentation.assert_called_once()

    def test_idempotent_initialization(self):
        """Test that multiple calls to initialize don't create duplicates."""
        with patch("observability.otel.trace.set_tracer_provider") as mock_set_provider:
            with patch("observability.otel._setup_client_instrumentations") as mock_instrumentation:
                
                # First call
                initialize_telemetry("test-service")
                
                # Second call - should be no-op
                initialize_telemetry("test-service")
                
                # Should only be called once
                assert mock_set_provider.call_count == 1
                assert mock_instrumentation.call_count == 1

    def test_custom_environment_variables(self):
        """Test configuration with custom environment variables."""
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://custom-collector:4318"
        os.environ["APP_ENV"] = "production"
        os.environ["SERVICE_VERSION"] = "1.2.3"
        
        with patch("observability.otel.OTLPSpanExporter") as mock_exporter:
            with patch("observability.otel.trace.set_tracer_provider"):
                with patch("observability.otel._setup_client_instrumentations"):
                    
                    initialize_telemetry("test-service")
                    
                    # Check that custom endpoint is used
                    mock_exporter.assert_called_once()
                    call_args = mock_exporter.call_args
                    assert "http://custom-collector:4318/v1/traces" in str(call_args)

    def test_custom_trace_endpoint_variable(self):
        """Test explicit traces endpoint is used without appending a suffix."""
        os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = "http://collector:4318/custom/traces"

        with patch("observability.otel.OTLPSpanExporter") as mock_exporter:
            with patch("observability.otel.trace.set_tracer_provider"):
                with patch("observability.otel._setup_client_instrumentations"):
                    initialize_telemetry("test-service")

                    mock_exporter.assert_called_once()
                    call_args = mock_exporter.call_args
                    assert "http://collector:4318/custom/traces" in str(call_args)

    def test_initialize_telemetry_from_env_is_gated(self):
        """Test service-level observability flag gates initialization."""
        with patch("observability.otel.initialize_telemetry") as mock_initialize:
            assert not is_observability_enabled()
            assert initialize_telemetry_from_env("test-service") is False
            mock_initialize.assert_not_called()

            os.environ["OBSERVABILITY_ENABLED"] = "true"
            assert is_observability_enabled()
            initialize_telemetry_from_env("test-service")
            mock_initialize.assert_called_once_with("test-service")

    def test_sampler_configuration(self):
        """Test different sampler configurations.""" 
        # Test always_on
        os.environ["OTEL_TRACES_SAMPLER"] = "always_on"
        sampler = _get_sampler()
        assert "StaticSampler" in str(sampler)
        
        # Test always_off
        os.environ["OTEL_TRACES_SAMPLER"] = "always_off"
        sampler = _get_sampler()
        assert "StaticSampler" in str(sampler)
        
        # Test ratio-based
        os.environ["OTEL_TRACES_SAMPLER"] = "traceidratio_0.5"
        sampler = _get_sampler()
        assert "TraceIdRatioBased" in str(sampler)

    def test_exporter_failure_handling(self):
        """Test graceful handling when OTLP exporter fails."""
        with patch("observability.otel.OTLPSpanExporter") as mock_exporter:
            with patch("observability.otel.trace.set_tracer_provider"):
                with patch("observability.otel._setup_client_instrumentations"):
                    
                    # Make exporter initialization fail
                    mock_exporter.side_effect = Exception("Connection failed")
                    
                    # Should not raise exception
                    initialize_telemetry("test-service")
                    
                    # Tracing should still be enabled (just no export)
                    assert is_tracing_enabled()

    def test_client_instrumentation_setup(self):
        """Test client instrumentation setup with missing dependencies.""" 
        with patch("observability.otel._setup_client_instrumentations") as mock_instrumentation:
            with patch("observability.otel.trace.set_tracer_provider"):
                
                initialize_telemetry("test-service")
                
                # Check that instrumentation setup was called
                mock_instrumentation.assert_called_once()

    def test_shutdown_telemetry(self):
        """Test telemetry shutdown."""
        with patch("observability.otel.trace.set_tracer_provider"):
            with patch("observability.otel._setup_client_instrumentations"):
                
                initialize_telemetry("test-service")
                assert is_tracing_enabled()
                
                # Mock tracer provider
                import observability.otel as otel_module
                mock_provider = MagicMock()
                otel_module._tracer_provider = mock_provider
                
                shutdown_telemetry()
                
                mock_provider.shutdown.assert_called_once()
                assert not is_tracing_enabled()

    def test_get_tracer(self):
        """Test tracer retrieval."""
        with patch("observability.otel.trace.get_tracer") as mock_get_tracer:
            get_tracer("test-module")
            mock_get_tracer.assert_called_once_with("test-module")

    def test_initialization_failure_handling(self):
        """Test that initialization failures don't crash the application."""
        with patch("observability.otel.Resource.create") as mock_resource:
            # Make resource creation fail
            mock_resource.side_effect = Exception("Resource creation failed")
            
            # Should not raise exception
            initialize_telemetry("test-service")
            
            # Tracing should not be enabled
            assert not is_tracing_enabled()

    def test_environment_defaults(self):
        """Test default environment values."""
        with patch("observability.otel.OTLPSpanExporter") as mock_exporter:
            with patch("observability.otel.trace.set_tracer_provider"):
                with patch("observability.otel._setup_client_instrumentations"):
                    
                    initialize_telemetry("test-service")
                    
                    # Check default endpoint is used
                    mock_exporter.assert_called_once()
                    call_args = mock_exporter.call_args
                    assert "http://otel-collector:4318/v1/traces" in str(call_args)
