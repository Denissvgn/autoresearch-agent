"""Feature specification package."""

from .generator import generate_feature_spec
from .hasher import compute_feature_spec_hash

__all__ = ["generate_feature_spec", "compute_feature_spec_hash"]
