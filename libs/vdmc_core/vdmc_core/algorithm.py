"""
Core VDMC (Volatility-Driven Momentum Cycle) algorithm implementation.

This module implements the main VDMC calculation function following the
technical specification exactly, with proper error handling and fallback strategies.
"""

import logging

import numpy as np
from scipy.ndimage import gaussian_filter1d

from .exceptions import VDMCComputationError
from .models import VDMCConfig, VDMCOutput
from .utils import (
    calculate_amplitude,
    calculate_probabilities,
    exponential_smoothing,
    find_local_extrema,
    validate_input_data,
)

try:
    # Try importing from prometheus_client to create fallback metric
    from prometheus_client import Counter
    VDMC_FALLBACK_TOTAL = Counter(
        "vdmc_fallback_total",
        "Total number of times VDMC calculation used fallback logic",
        ["reason"]
    )
    _METRICS_AVAILABLE = True
except ImportError:
    # Create a no-op metric if prometheus is not available
    class _NoopCounter:
        def labels(self, **kwargs):
            return self
        def inc(self, *args, **kwargs):
            pass
    
    VDMC_FALLBACK_TOTAL = _NoopCounter()
    _METRICS_AVAILABLE = False

logger = logging.getLogger(__name__)


def _increment_fallback_metric(reason: str) -> None:
    """Safely increment fallback metric if available."""
    try:
        VDMC_FALLBACK_TOTAL.labels(reason=reason).inc()
    except Exception:
        pass  # Fail silently if metrics unavailable


def vdmc(close_prices: np.ndarray, config: VDMCConfig) -> VDMCOutput:
    """
    Calculate VDMC (Volatility-Driven Momentum Cycle) indicator.
    
    Implementation follows RORO pattern and early error handling as specified
    in the technical specification.
    
    Args:
        close_prices: Array of closing prices
        config: VDMC configuration parameters
        
    Returns:
        VDMCOutput containing probabilities, amplitude, momentum, and warning codes
        
    Raises:
        VDMCComputationError: If computation fails due to internal errors
    """
    logger.debug(f"Starting VDMC calculation with {len(close_prices)} price points")
    
    # Early validation and error handling
    if not validate_input_data(close_prices):
        logger.warning("Invalid input data detected, returning neutral probabilities")
        return _handle_invalid_input()
    
    try:
        # Handle short history fallback
        if len(close_prices) < config.lookback_period:
            logger.info(f"Short history detected: {len(close_prices)} < {config.lookback_period}")
            return _handle_short_history(close_prices, config)
        
        # Core algorithm implementation following technical specification
        
        # 1. Smooth the close prices using a Gaussian filter
        smoothed_prices = gaussian_filter1d(close_prices, sigma=config.kernel_sigma)
        logger.debug("Applied Gaussian smoothing")
        
        # 2. Calculate the momentum/trend (gradient of the smoothed series)
        momentum = np.gradient(smoothed_prices)
        logger.debug("Calculated momentum gradient")
        
        # 3. Find the local peaks and troughs of the smoothed series
        peaks, troughs = find_local_extrema(smoothed_prices)
        logger.debug(f"Found {len(peaks)} peaks and {len(troughs)} troughs")
        
        # 4. Calculate the wave amplitude based on these extrema
        wave_amplitude = calculate_amplitude(smoothed_prices, peaks, troughs)
        
        # Apply amplitude_scaling if provided (extended parameter)
        amplitude_scaling = getattr(config, 'amplitude_scaling', 1.0)
        wave_amplitude *= amplitude_scaling
        logger.debug(f"Calculated wave amplitude: {wave_amplitude} (scaling={amplitude_scaling})")
        
        # 5. Combine momentum and amplitude into a decision variable
        decision_variable = config.alpha * momentum[-1] - config.beta * wave_amplitude
        logger.debug(f"Decision variable: {decision_variable}")
        
        # 6. Use a sigmoid function to get the final buy/sell probabilities
        probabilities = calculate_probabilities(decision_variable, config.signal_type)
        
        # 7. Return all the calculated components
        result = VDMCOutput(
            p_buy=probabilities.p_buy,
            p_sell=probabilities.p_sell,
            wave_amplitude=wave_amplitude,
            momentum=momentum[-1],
            warning_code=None
        )
        
        logger.debug(f"VDMC calculation completed successfully: p_buy={result.p_buy:.4f}, p_sell={result.p_sell:.4f}")
        return result
        
    except Exception as e:
        logger.error(f"VDMC computation failed: {e}", exc_info=True)
        raise VDMCComputationError(f"Failed to compute VDMC: {e}") from e


def _handle_short_history(close_prices: np.ndarray, config: VDMCConfig) -> VDMCOutput:
    """
    Handle case where history < lookback_period using exponential smoothing.
    
    This implements the fallback strategy specified in the technical specification:
    - Use exponential smoothing for smoothed prices
    - Set wave amplitude to 0
    - Return warning code 1002
    
    Args:
        close_prices: Short price array
        config: VDMC configuration
        
    Returns:
        VDMCOutput with fallback values and warning code
    """
    logger.warning(f"Applying short history fallback for {len(close_prices)} price points")
    _increment_fallback_metric("short_history")
    
    try:
        # Use exponential smoothing for short history
        # Apply smoothing_factor if provided (extended parameter)
        smooth_alpha = getattr(config, 'smoothing_factor', 0.3)
        smoothed_prices = exponential_smoothing(close_prices, alpha=smooth_alpha)
        
        # Calculate momentum from smoothed series
        momentum = np.gradient(smoothed_prices)
        
        # Set wave amplitude to 0 for short history as per specification
        wave_amplitude = 0.0
        
        # Calculate decision variable
        decision_variable = config.alpha * momentum[-1] - config.beta * wave_amplitude
        
        # Calculate probabilities
        probabilities = calculate_probabilities(decision_variable, config.signal_type)
        
        return VDMCOutput(
            p_buy=probabilities.p_buy,
            p_sell=probabilities.p_sell,
            wave_amplitude=wave_amplitude,
            momentum=momentum[-1],
            warning_code=1002  # Short history warning
        )
        
    except Exception as e:
        logger.error(f"Short history fallback failed: {e}")
        return _handle_invalid_input()


def _handle_invalid_input() -> VDMCOutput:
    """
    Handle NaN/inf inputs with neutral probabilities.
    
    This implements the fallback strategy for invalid inputs:
    - Set p_buy = p_sell = 0.5 (neutral)
    - Set amplitude and momentum to 0
    - Return warning code 1001
    
    Returns:
        VDMCOutput with neutral values and warning code
    """
    logger.warning("Returning neutral probabilities for invalid input")
    _increment_fallback_metric("nan_input")
    
    return VDMCOutput(
        p_buy=0.5,
        p_sell=0.5,
        wave_amplitude=0.0,
        momentum=0.0,
        warning_code=1001  # Invalid input warning
    ) 