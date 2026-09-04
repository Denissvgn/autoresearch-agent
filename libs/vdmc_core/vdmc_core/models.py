"""
Pydantic models for VDMC calculation configuration and outputs.

This module defines the input and output data structures for the VDMC
(Volatility-Driven Momentum Cycle) indicator calculation.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SignalType(str, Enum):
    """Enumeration for signal types."""

    BUY = "buy"
    SELL = "sell"


class VDMCConfig(BaseModel):
    """Configuration for VDMC calculation with validation.

    This model contains all parameters needed for VDMC calculation,
    with proper validation ranges as specified in the technical specification.
    """

    lookback_period: int = Field(default=120, ge=120, le=720, description="Number of bars for kernel smoothing")
    signal_type: SignalType = Field(default=SignalType.BUY, description="Type of signal sought")
    alpha: float = Field(default=1.2, description="Trend coefficient in logistic function")
    beta: float = Field(default=0.8, description="Wave amplitude coefficient")
    kernel_sigma: int = Field(default=5, ge=3, le=21, description="gaussian_filter1d parameter")
    amplitude_scaling: float = Field(
        default=1.0, gt=0.0, le=5.0, description="Scaling factor applied to wave amplitude"
    )
    smoothing_factor: float = Field(
        default=0.3, gt=0.0, le=1.0, description="Smoothing factor for wave and momentum calculations"
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class VDMCOutput(BaseModel):
    """Output structure for VDMC calculation.

    Contains the calculated probabilities, intermediate values,
    and optional warning codes for edge cases.
    """

    p_buy: float = Field(ge=0.0, le=1.0, description="Buy probability")
    p_sell: float = Field(ge=0.0, le=1.0, description="Sell probability")
    wave_amplitude: float = Field(description="Calculated wave amplitude")
    momentum: float = Field(description="Current momentum value")
    warning_code: Optional[int] = Field(
        default=None, description="Warning code for edge cases (1001: Invalid input, 1002: Short history)"
    )

    class Config:
        """Pydantic configuration."""

        # Allow numpy types
        arbitrary_types_allowed = True


class VDMCProbabilities(BaseModel):
    """Helper model for probability calculations."""

    p_buy: float
    p_sell: float
