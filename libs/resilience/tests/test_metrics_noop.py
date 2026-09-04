import sys


def test_metrics_noop_importable(monkeypatch):
    # Simulate prometheus_client missing so metrics module falls back to no-op
    sys_modules_backup = dict(sys.modules)
    try:
        if 'prometheus_client' in sys.modules:
            del sys.modules['prometheus_client']
        import resilience.metrics as m

        # Access attributes to ensure they exist
        _ = m.resilience_retry_attempts_total
        _ = m.resilience_retry_failures_total
        _ = m.circuit_breaker_state
    finally:
        sys.modules.clear()
        sys.modules.update(sys_modules_backup)

