"""
Testing utilities for Prometheus metrics in ML services.

Provides pytest fixtures for proper test isolation when using
service-specific CollectorRegistry instances.
"""
import pytest
from typing import Optional

try:
    from .metrics import (
        clear_service_registry,
        clear_all_service_registries,
        get_service_registry,
        PROMETHEUS_AVAILABLE
    )
except ImportError:
    # Fallback if running outside package context
    from libs.observability.metrics import (
        clear_service_registry,
        clear_all_service_registries,
        get_service_registry,
        PROMETHEUS_AVAILABLE
    )


@pytest.fixture(scope="function")
def clear_prometheus_registry():
    """
    Clear all Prometheus registries before and after each test.
    
    Use this fixture in tests that create metrics to ensure clean state.
    Scope is "function" to handle module re-imports within a session.
    
    Usage:
        def test_my_metric(clear_prometheus_registry):
            # Test code here - registry is clean
            counter = create_counter(...)
    """
    if PROMETHEUS_AVAILABLE:
        clear_all_service_registries()
    
    yield
    
    # Clean up after test
    if PROMETHEUS_AVAILABLE:
        clear_all_service_registries()


@pytest.fixture(scope="function")
def clear_service_metrics():
    """
    Factory fixture for clearing specific service metrics.
    
    Returns a callable that clears metrics for a specific service.
    Useful when testing multiple services in the same test suite.
    
    Usage:
        def test_inference_metrics(clear_service_metrics):
            clear_service_metrics("inference-service")
            # Test code here
    """
    def _clear(service_name: str):
        if PROMETHEUS_AVAILABLE:
            clear_service_registry(service_name)
    
    yield _clear


@pytest.fixture(scope="function")
def inference_service_registry(clear_service_metrics):
    """
    Provides clean inference-service registry for tests.
    
    Automatically clears registry before test and returns it.
    
    Usage:
        def test_inference(inference_service_registry):
            counter = create_counter(
                "test_metric",
                "Test metric",
                registry=inference_service_registry
            )
    """
    clear_service_metrics("inference-service")
    return get_service_registry("inference-service")


@pytest.fixture(scope="function")
def ensemble_trainer_registry(clear_service_metrics):
    """Provides clean ensemble-trainer registry for tests."""
    clear_service_metrics("ensemble-trainer")
    return get_service_registry("ensemble-trainer")


@pytest.fixture(scope="function")
def vdmc_indicator_registry(clear_service_metrics):
    """Provides clean vdmc-indicator registry for tests."""
    clear_service_metrics("vdmc-indicator")
    return get_service_registry("vdmc-indicator")


@pytest.fixture(scope="function")
def rl_trainer_registry(clear_service_metrics):
    """Provides clean rl-trainer registry for tests."""
    clear_service_metrics("rl-trainer")
    return get_service_registry("rl-trainer")


@pytest.fixture(scope="module")
def ml_service_registry():
    """
    Factory fixture for getting service registries.
    
    Module-scoped to share registries across tests in same module.
    Each service still gets isolated registry.
    
    Usage:
        def test_service(ml_service_registry):
            registry = ml_service_registry("my-service")
            # Use registry
    """
    def _get_registry(service_name: str):
        return get_service_registry(service_name)
    
    return _get_registry
