"""
Utility functions for VDMC calculations.

This module contains helper functions for mathematical operations,
data validation, and signal processing used in VDMC algorithm.
"""

import logging
from typing import Tuple

import numpy as np
from scipy.signal import find_peaks

from .models import SignalType, VDMCProbabilities

logger = logging.getLogger(__name__)


def sigmoid(x: float) -> float:
    """
    Calculate sigmoid function with numerical stability.
    
    Args:
        x: Input value
        
    Returns:
        Sigmoid value between 0 and 1
    """
    # Clip to prevent overflow
    x = np.clip(x, -500, 500)
    return float(1.0 / (1.0 + np.exp(-x)))


def validate_input_data(close_prices: np.ndarray) -> bool:
    """
    Validate input price data for correctness.
    
    Args:
        close_prices: Array of closing prices
        
    Returns:
        True if data is valid, False otherwise
    """
    if not isinstance(close_prices, np.ndarray):
        logger.warning("Input is not a numpy array")
        return False
        
    if len(close_prices) == 0:
        logger.warning("Input array is empty")
        return False
        
    if not np.isfinite(close_prices).all():
        logger.warning("Input contains NaN or infinite values")
        return False
        
    if len(close_prices) < 5:
        logger.warning("Input array too short (< 5 points)")
        return False
        
    return True


def find_local_extrema(smoothed_prices: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Find local peaks and troughs in smoothed price series.
    
    Args:
        smoothed_prices: Smoothed price array
        
    Returns:
        Tuple of (peaks_indices, troughs_indices)
    """
    # Find peaks (local maxima)
    peaks, _ = find_peaks(smoothed_prices, distance=3)
    
    # Find troughs (local minima) by finding peaks in inverted series
    troughs, _ = find_peaks(-smoothed_prices, distance=3)
    
    return peaks, troughs


def calculate_amplitude(
    smoothed_prices: np.ndarray, 
    peaks: np.ndarray, 
    troughs: np.ndarray
) -> float:
    """
    Calculate wave amplitude based on peaks and troughs.
    
    Args:
        smoothed_prices: Smoothed price series
        peaks: Indices of local peaks
        troughs: Indices of local troughs
        
    Returns:
        Wave amplitude value
    """
    if len(peaks) == 0 or len(troughs) == 0:
        return 0.0
        
    # Get recent peak and trough values
    recent_peaks = smoothed_prices[peaks[-min(3, len(peaks)):]]
    recent_troughs = smoothed_prices[troughs[-min(3, len(troughs)):]]
    
    # Calculate amplitude as difference between mean peak and trough levels
    peak_level = np.mean(recent_peaks)
    trough_level = np.mean(recent_troughs)
    
    amplitude = abs(peak_level - trough_level) / np.mean(smoothed_prices[-20:])
    
    return float(amplitude)


def exponential_smoothing(prices: np.ndarray, alpha: float = 0.3) -> np.ndarray:
    """
    Apply exponential smoothing to price series.
    
    Used as fallback for short history cases.
    
    Args:
        prices: Price array
        alpha: Smoothing parameter (0 < alpha < 1)
        
    Returns:
        Exponentially smoothed price series
    """
    if len(prices) == 0:
        return prices
        
    smoothed = np.zeros_like(prices)
    smoothed[0] = prices[0]
    
    for i in range(1, len(prices)):
        smoothed[i] = alpha * prices[i] + (1 - alpha) * smoothed[i - 1]
        
    return smoothed


def calculate_probabilities(decision_variable: float, signal_type: SignalType) -> VDMCProbabilities:
    """
    Calculate buy/sell probabilities based on decision variable and signal type.
    
    Args:
        decision_variable: Combined momentum/amplitude decision value
        signal_type: Type of signal being calculated
        
    Returns:
        VDMCProbabilities with p_buy and p_sell values
    """
    if signal_type == SignalType.BUY:
        p_buy = sigmoid(decision_variable)
        p_sell = sigmoid(-decision_variable)
    else:  # SignalType.SELL
        p_buy = 1.0 - sigmoid(decision_variable)
        p_sell = 1.0 - sigmoid(-decision_variable)
        
    return VDMCProbabilities(p_buy=p_buy, p_sell=p_sell) 