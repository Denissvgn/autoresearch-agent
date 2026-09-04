class RetryError(Exception):
    """Raised when retry attempts are exhausted without success."""


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and execution is blocked."""

