"""VDMC (Volatility-Driven Momentum Cycle) indicator configuration.

This module provides a standardized configuration for VDMC parameters
that is shared across all ML training services (RL trainer, ensemble trainer).

Per REQ-001-ML ML-3.2:
- VDMC parameters are mandatory for all agents
- Parameters are fixed at training time
- Parameters must be persisted with the model
- Same parameters used in production inference

Design Reference: docs/design/vdmc_parameter_persistence.md
"""

from enum import Enum
from typing import Dict, Any

from pydantic import BaseModel, Field, field_validator, ConfigDict


class SignalType(str, Enum):
    """VDMC signal type enumeration.

    Attributes:
        BUY: Optimize for buy signals
        SELL: Optimize for sell signals
    """

    BUY = "buy"
    SELL = "sell"

    @classmethod
    def from_string(cls, value: str) -> "SignalType":
        """Create SignalType from string (case-insensitive).

        Args:
            value: Signal type string ('buy' or 'sell')

        Returns:
            SignalType enum value

        Raises:
            ValueError: If value is invalid

        Examples:
            >>> SignalType.from_string('BUY')
            <SignalType.BUY: 'buy'>
            >>> SignalType.from_string('sell')
            <SignalType.SELL: 'sell'>
        """
        value_lower = value.lower()
        try:
            return cls(value_lower)
        except ValueError:
            raise ValueError(f"Invalid signal type: {value}. Must be 'buy' or 'sell'")


class VDMCConfig(BaseModel):
    """Configuration for VDMC indicator parameters.

    This configuration is frozen (immutable) to ensure parameters cannot
    be modified after training begins, per REQ-001-ML ML-3.2.

    All parameters have sensible defaults but can be overridden for
    specific trading strategies or market conditions.

    Attributes:
        lookback_period: Number of bars for kernel smoothing (120-720)
        signal_type: Type of signal to optimize for (BUY or SELL)
        alpha: Trend coefficient in logistic function (0.1-5.0)
        beta: Wave amplitude coefficient (0.1-5.0)
        kernel_sigma: Gaussian filter sigma parameter (3-21, odd numbers preferred)
        amplitude_scaling: Scaling factor for wave amplitude (0.1-5.0)
        smoothing_factor: Smoothing factor for calculations (0.0-1.0)

    Examples:
        >>> config = VDMCConfig()  # Use defaults
        >>> config.lookback_period
        120

        >>> config = VDMCConfig(
        ...     lookback_period=240,
        ...     signal_type=SignalType.SELL,
        ...     alpha=1.5
        ... )
        >>> config.alpha
        1.5
    """

    model_config = ConfigDict(
        frozen=True,  # Immutable per REQ-001-ML ML-3.2
        use_enum_values=False,  # Keep enum objects
    )

    # ========================================================================
    # Core VDMC Parameters (Mandatory)
    # ========================================================================

    lookback_period: int = Field(
        default=120,
        ge=120,
        le=720,
        description="Number of bars for kernel smoothing. Typical: 120 (default), 240 (medium-term), 360-720 (long-term)",
    )

    signal_type: SignalType = Field(default=SignalType.BUY, description="Type of signal to optimize for: BUY or SELL")

    alpha: float = Field(
        default=1.2,
        gt=0.0,
        le=5.0,
        description="Trend coefficient in logistic function. Higher values = stronger trend sensitivity. Range: (0, 5.0], typical: 0.8-2.0",
    )

    beta: float = Field(
        default=0.8,
        gt=0.0,
        le=5.0,
        description="Wave amplitude coefficient. Controls momentum signal strength. Range: (0, 5.0], typical: 0.5-1.5",
    )

    kernel_sigma: int = Field(
        default=5,
        ge=3,
        le=21,
        description="Gaussian filter sigma parameter. Odd numbers preferred. Range: [3, 21], typical: 5, 7, 9",
    )

    # ========================================================================
    # Extended Parameters (Optional)
    # ========================================================================

    amplitude_scaling: float = Field(
        default=1.0,
        gt=0.0,
        le=5.0,
        description="Scaling factor for wave amplitude. Amplifies or dampens signals. Range: (0, 5.0], typical: 0.8-1.5",
    )

    smoothing_factor: float = Field(
        default=0.3,
        gt=0.0,
        le=1.0,
        description="Smoothing factor for calculations. Higher = more smoothing. Range: (0, 1.0], typical: 0.2-0.5",
    )

    # ========================================================================
    # Validators
    # ========================================================================

    @field_validator("kernel_sigma")
    @classmethod
    def validate_kernel_sigma_odd(cls, v: int) -> int:
        """Validate kernel_sigma is odd (preferred for symmetric kernel).

        Warning only - even values are technically valid but not recommended.
        """
        if v % 2 == 0:
            import warnings

            warnings.warn(
                f"kernel_sigma={v} is even. Odd values (3, 5, 7, 9...) are " "preferred for symmetric Gaussian kernel.",
                UserWarning,
            )
        return v

    @field_validator("signal_type", mode="before")
    @classmethod
    def validate_signal_type(cls, v: Any) -> SignalType:
        """Convert string to SignalType enum if needed."""
        if isinstance(v, str):
            return SignalType.from_string(v)
        elif isinstance(v, SignalType):
            return v
        else:
            raise ValueError(f"Invalid signal_type: {v}. Must be 'buy', 'sell', or SignalType enum")

    # ========================================================================
    # Serialization Methods
    # ========================================================================

    def to_mlflow_params(self) -> Dict[str, Any]:
        """Convert to MLflow parameters dictionary.

        Adds 'vdmc_' prefix to all parameters for namespacing.

        Returns:
            Dictionary of MLflow parameters

        Examples:
            >>> config = VDMCConfig(lookback_period=240)
            >>> params = config.to_mlflow_params()
            >>> params['vdmc_lookback_period']
            240
        """
        return {
            "vdmc_lookback_period": self.lookback_period,
            "vdmc_signal_type": self.signal_type.value,
            "vdmc_alpha": self.alpha,
            "vdmc_beta": self.beta,
            "vdmc_kernel_sigma": self.kernel_sigma,
            "vdmc_amplitude_scaling": self.amplitude_scaling,
            "vdmc_smoothing_factor": self.smoothing_factor,
        }

    def to_mlflow_tags(self) -> Dict[str, str]:
        """Convert to MLflow tags dictionary.

        Tags are string-valued for searchability in MLflow UI.

        Returns:
            Dictionary of MLflow tags

        Examples:
            >>> config = VDMCConfig()
            >>> tags = config.to_mlflow_tags()
            >>> tags['vdmc_signal_type']
            'buy'
        """
        return {
            "vdmc_signal_type": self.signal_type.value,
            "vdmc_lookback_period": str(self.lookback_period),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to plain dictionary.

        Returns:
            Dictionary with all parameters

        Examples:
            >>> config = VDMCConfig()
            >>> d = config.to_dict()
            >>> d['lookback_period']
            120
        """
        return {
            "lookback_period": self.lookback_period,
            "signal_type": self.signal_type.value,
            "alpha": self.alpha,
            "beta": self.beta,
            "kernel_sigma": self.kernel_sigma,
            "amplitude_scaling": self.amplitude_scaling,
            "smoothing_factor": self.smoothing_factor,
        }

    def to_api_request(self) -> Dict[str, Any]:
        """Convert to VDMC API request format.

        Compatible with vdmc-indicator service API.

        Returns:
            Dictionary formatted for VDMC API requests

        Examples:
            >>> config = VDMCConfig()
            >>> request = config.to_api_request()
            >>> request['signal_type']
            'buy'
        """
        return {
            "lookback_period": self.lookback_period,
            "signal_type": self.signal_type.value,
            "alpha": self.alpha,
            "beta": self.beta,
            "kernel_sigma": self.kernel_sigma,
            "amplitude_scaling": self.amplitude_scaling,
            "smoothing_factor": self.smoothing_factor,
        }

    @classmethod
    def from_mlflow_params(cls, params: Dict[str, Any]) -> "VDMCConfig":
        """Create VDMCConfig from MLflow parameters.

        Handles both prefixed ('vdmc_*') and unprefixed parameter names.

        Args:
            params: Dictionary of MLflow parameters

        Returns:
            VDMCConfig instance

        Examples:
            >>> params = {'vdmc_lookback_period': 240, 'vdmc_signal_type': 'sell'}
            >>> config = VDMCConfig.from_mlflow_params(params)
            >>> config.lookback_period
            240
        """

        # Handle both prefixed and unprefixed keys
        def get_param(name: str, default: Any = None) -> Any:
            """Get parameter with or without vdmc_ prefix."""
            prefixed = f"vdmc_{name}"
            if prefixed in params:
                return params[prefixed]
            elif name in params:
                return params[name]
            return default

        return cls(
            lookback_period=get_param("lookback_period", 120),
            signal_type=get_param("signal_type", "buy"),
            alpha=get_param("alpha", 1.2),
            beta=get_param("beta", 0.8),
            kernel_sigma=get_param("kernel_sigma", 5),
            amplitude_scaling=get_param("amplitude_scaling", 1.0),
            smoothing_factor=get_param("smoothing_factor", 0.3),
        )

    @classmethod
    def get_recommended_for_strategy(cls, strategy: str) -> "VDMCConfig":
        """Get recommended VDMC parameters for an agent strategy.

        Args:
            strategy: Agent strategy code ('AGGR', 'CONS', 'BALA', 'SCAL')

        Returns:
            VDMCConfig tuned for the strategy

        Examples:
            >>> config = VDMCConfig.get_recommended_for_strategy('AGGR')
            >>> config.lookback_period  # Aggressive uses shorter lookback
            120
        """
        recommendations = {
            "AGGR": {
                "lookback_period": 120,
                "alpha": 1.5,
                "beta": 1.2,
                "kernel_sigma": 3,
                "amplitude_scaling": 1.3,
            },
            "CONS": {
                "lookback_period": 360,
                "alpha": 0.8,
                "beta": 0.6,
                "kernel_sigma": 9,
                "amplitude_scaling": 0.8,
            },
            "BALA": {
                "lookback_period": 240,
                "alpha": 1.2,
                "beta": 0.8,
                "kernel_sigma": 5,
                "amplitude_scaling": 1.0,
            },
            "SCAL": {
                "lookback_period": 120,
                "alpha": 1.8,
                "beta": 1.5,
                "kernel_sigma": 3,
                "amplitude_scaling": 1.5,
            },
        }

        strategy_upper = strategy.upper()
        if strategy_upper not in recommendations:
            # Return balanced defaults for unknown strategies
            return cls()

        return cls(**recommendations[strategy_upper])

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"VDMCConfig(lookback={self.lookback_period}, "
            f"signal={self.signal_type.value}, alpha={self.alpha}, "
            f"beta={self.beta}, sigma={self.kernel_sigma})"
        )

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"VDMCConfig(lookback_period={self.lookback_period}, "
            f"signal_type={self.signal_type!r}, alpha={self.alpha}, "
            f"beta={self.beta}, kernel_sigma={self.kernel_sigma}, "
            f"amplitude_scaling={self.amplitude_scaling}, "
            f"smoothing_factor={self.smoothing_factor})"
        )
