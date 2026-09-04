"""Compatibility alias for top-level ``observability.otel`` imports."""

import sys

from .observability import otel as _otel

sys.modules[__name__] = _otel
