"""
VDMC Core Library - Volatility-Driven Momentum Cycle Indicator

This library provides the core mathematical logic for the VDMC indicator,
a proprietary trading signal used in the Traid platform.

Main API:
    - vdmc(): Calculate VDMC indicator
    - VDMCConfig: Configuration model
    - VDMCOutput: Output model
"""

from .algorithm import vdmc
from .exceptions import VDMCComputationError, VDMCError, VDMCInputError
from .factored import (
    VDMCIntermediates,
    apply_sigmoid,
    compute_intermediates,
    derive_vdmc_features,
)
from .models import SignalType, VDMCConfig, VDMCOutput

__version__ = "0.1.0"
__author__ = "Traid Platform Team"

__all__ = [
    "vdmc",
    "VDMCConfig",
    "VDMCOutput",
    "SignalType",
    "VDMCError",
    "VDMCInputError",
    "VDMCComputationError",
    # Factored API (HPO)
    "VDMCIntermediates",
    "compute_intermediates",
    "apply_sigmoid",
    "derive_vdmc_features",
] 