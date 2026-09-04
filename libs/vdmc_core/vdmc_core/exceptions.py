"""
Custom exceptions for VDMC core library.

This module defines specific exception types for different error conditions
that can occur during VDMC calculation.
"""


class VDMCError(Exception):
    """Base exception for VDMC-related errors."""
    pass


class VDMCInputError(VDMCError):
    """Raised when input data is invalid or malformed."""
    pass


class VDMCComputationError(VDMCError):
    """Raised when computation fails due to internal errors."""
    pass


class VDMCConfigurationError(VDMCError):
    """Raised when configuration parameters are invalid."""
    pass 