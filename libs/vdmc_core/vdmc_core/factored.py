"""
Factored VDMC computation for HPO efficiency.

Splits the VDMC algorithm into two stages:
  Stage 1 (expensive): Gaussian smoothing, gradient, extrema detection
  Stage 2 (cheap):     Sigmoid application with (alpha, beta) — <1 ms

This enables O(|sigma × lookback|) enrichment precomputation, after which
arbitrary (alpha, beta) sweeps reuse cached intermediates without
recomputing the Gaussian filter or extrema detection.

Reference: FEATURES-2.md §10–§11
"""

import logging
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter1d

from .models import SignalType, VDMCConfig, VDMCOutput
from .utils import (
    calculate_amplitude,
    calculate_probabilities,
    exponential_smoothing,
    find_local_extrema,
    validate_input_data,
)

logger = logging.getLogger(__name__)


@dataclass
class VDMCIntermediates:
    """Cached intermediate results from Stage 1 (Gaussian + extrema).

    These depend only on ``kernel_sigma`` and ``lookback_period``
    (and the raw close prices), NOT on ``alpha`` or ``beta``.
    """
    smoothed_prices: np.ndarray
    momentum: np.ndarray       # np.gradient(smoothed_prices)
    wave_amplitude: float      # from peak/trough detection
    warning_code: int | None   # 1001/1002 if fallback, else None
    is_fallback: bool          # True when short-history path was used


def compute_intermediates(
    close_prices: np.ndarray,
    kernel_sigma: int = 5,
    lookback_period: int = 120,
    smoothing_factor: float = 0.3,
    amplitude_scaling: float = 1.0,
) -> VDMCIntermediates:
    """Stage 1: compute Gaussian-smoothed features (expensive, ~60 s/212 K rows).

    This is the part that must be recomputed when ``kernel_sigma`` or
    ``lookback_period`` changes, but can be reused across all ``(alpha, beta)``
    trials.

    Args:
        close_prices: Raw close price array.
        kernel_sigma: Gaussian filter bandwidth.
        lookback_period: Minimum data length before fallback.
        smoothing_factor: Exponential smoothing alpha for short-history fallback.
        amplitude_scaling: Multiplier applied to wave_amplitude.

    Returns:
        VDMCIntermediates with cached smoothed values.
    """
    # Validate input
    if not validate_input_data(close_prices):
        return VDMCIntermediates(
            smoothed_prices=np.array([]),
            momentum=np.array([]),
            wave_amplitude=0.0,
            warning_code=1001,
            is_fallback=True,
        )

    if len(close_prices) < lookback_period:
        # Short-history fallback
        smoothed = exponential_smoothing(close_prices, alpha=smoothing_factor)
        momentum = np.gradient(smoothed)
        return VDMCIntermediates(
            smoothed_prices=smoothed,
            momentum=momentum,
            wave_amplitude=0.0,
            warning_code=1002,
            is_fallback=True,
        )

    # Full computation
    smoothed = gaussian_filter1d(close_prices, sigma=kernel_sigma)
    momentum = np.gradient(smoothed)
    peaks, troughs = find_local_extrema(smoothed)
    wave_amplitude = calculate_amplitude(smoothed, peaks, troughs)
    wave_amplitude *= amplitude_scaling

    return VDMCIntermediates(
        smoothed_prices=smoothed,
        momentum=momentum,
        wave_amplitude=wave_amplitude,
        warning_code=None,
        is_fallback=False,
    )


def apply_sigmoid(
    intermediates: VDMCIntermediates,
    alpha: float = 1.2,
    beta: float = 0.8,
    signal_type: SignalType = SignalType.BUY,
) -> VDMCOutput:
    """Stage 2: apply (alpha, beta) to cached intermediates (cheap, <1 ms).

    Args:
        intermediates: Pre-computed smoothed features.
        alpha: Trend coefficient.
        beta: Wave amplitude coefficient.
        signal_type: BUY or SELL.

    Returns:
        VDMCOutput with probabilities.
    """
    if intermediates.warning_code == 1001:
        # Invalid input — neutral
        return VDMCOutput(
            p_buy=0.5,
            p_sell=0.5,
            wave_amplitude=0.0,
            momentum=0.0,
            warning_code=1001,
        )

    momentum_value = float(intermediates.momentum[-1])
    decision_variable = alpha * momentum_value - beta * intermediates.wave_amplitude
    probas = calculate_probabilities(decision_variable, signal_type)

    return VDMCOutput(
        p_buy=probas.p_buy,
        p_sell=probas.p_sell,
        wave_amplitude=intermediates.wave_amplitude,
        momentum=momentum_value,
        warning_code=intermediates.warning_code,
    )


def derive_vdmc_features(
    buy_output: VDMCOutput,
    sell_output: VDMCOutput,
) -> dict[str, float]:
    """Derive the 9 VDMC feature columns from buy/sell outputs.

    Matches the column schema produced by
    ``DataEnrichmentPipeline.calculate_vdmc_features()``.

    Returns:
        Dict with keys: vdmc_buy_proba, vdmc_sell_proba, vdmc_momentum,
        vdmc_amplitude, vdmc_signal_strength, vdmc_trend_signal,
        vdmc_reversal_signal, vdmc_neutral_signal, vdmc_has_warning.
    """
    bp = buy_output.p_buy
    sp = sell_output.p_sell
    return {
        "vdmc_buy_proba": bp,
        "vdmc_sell_proba": sp,
        "vdmc_momentum": buy_output.momentum,
        "vdmc_amplitude": buy_output.wave_amplitude,
        "vdmc_signal_strength": abs(bp - 0.5) * 2.0,
        "vdmc_trend_signal": int(bp > 0.6),
        "vdmc_reversal_signal": int(sp > 0.6),
        "vdmc_neutral_signal": int(0.4 <= bp <= 0.6),
        "vdmc_has_warning": int(
            (buy_output.warning_code or 0) > 0
            or (sell_output.warning_code or 0) > 0
        ),
    }
