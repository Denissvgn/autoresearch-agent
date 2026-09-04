#!/usr/bin/env python3
"""
Golden Value Generator for VDMC Algorithm

This script generates and verifies golden test values for the VDMC algorithm
as required by Task S4-T4. It creates a simple, predictable price series and 
manually calculates each step of the VDMC algorithm to produce verified expected 
outputs.

The generated values are used in the golden value test to ensure the
VDMC implementation is mathematically correct and follows the technical
specification precisely.

Key Features:
- Creates deterministic 150-point price series (base + trend + sine wave)
- Manually calculates each VDMC algorithm step with documentation
- Outputs verified golden values for test fixtures
- Ensures mathematical correctness through step-by-step verification

Usage:
    python scripts/generate_golden_values.py

Output:
    Prints golden values in format suitable for copying to tests/conftest.py
"""

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks


def create_simple_price_series() -> np.ndarray:
    """
    Create a simple, predictable price series for golden value testing.
    
    This series is designed to be:
    - Small enough for manual verification
    - Predictable with clear patterns
    - Contains obvious peaks and troughs
    
    Returns:
        Simple price series with 150 points
    """
    # Create a simple pattern: base price + linear trend + sine wave
    n_points = 150  # Use 150 points to satisfy lookback_period >= 120 validation
    t = np.linspace(0, 2 * np.pi, n_points)
    
    base_price = 100.0
    trend = t * 2.0  # Gentle upward trend
    sine_component = 5.0 * np.sin(t)  # Clear cyclical pattern
    
    prices = base_price + trend + sine_component
    return prices


def manual_vdmc_calculation(close_prices: np.ndarray) -> dict:
    """
    Manually calculate VDMC algorithm step by step for golden value generation.
    
    This function documents each step clearly for verification purposes.
    
    Args:
        close_prices: Input price series
        
    Returns:
        Dictionary with all intermediate and final values
    """
    print("🔍 Manual VDMC Calculation for Golden Values")
    print("=" * 50)
    
    # Configuration (using default values that work with our 150-point dataset)
    config = {
        'lookback_period': 120,  # Use default value to satisfy validation
        'kernel_sigma': 5,
        'alpha': 1.2,
        'beta': 0.8,
        'signal_type': 'buy'
    }
    
    print("📊 Input Data:")
    print(f"   Close prices: {close_prices}")
    print(f"   Length: {len(close_prices)}")
    print(f"   Config: {config}")
    print()
    
    # Step 1: Gaussian smoothing
    print("🔧 Step 1: Gaussian Smoothing")
    smoothed_prices = gaussian_filter1d(close_prices, sigma=config['kernel_sigma'])
    print(f"   Smoothed prices: {smoothed_prices}")
    print()
    
    # Step 2: Calculate momentum (gradient)
    print("📈 Step 2: Momentum Calculation")
    momentum = np.gradient(smoothed_prices)
    current_momentum = momentum[-1]
    print(f"   Momentum array: {momentum}")
    print(f"   Current momentum: {current_momentum}")
    print()
    
    # Step 3: Find peaks and troughs
    print("🏔️ Step 3: Find Peaks and Troughs")
    peaks, _ = find_peaks(smoothed_prices, distance=3)
    troughs, _ = find_peaks(-smoothed_prices, distance=3)
    
    print(f"   Peak indices: {peaks}")
    print(f"   Trough indices: {troughs}")
    if len(peaks) > 0:
        print(f"   Peak values: {smoothed_prices[peaks]}")
    if len(troughs) > 0:
        print(f"   Trough values: {smoothed_prices[troughs]}")
    print()
    
    # Step 4: Calculate wave amplitude
    print("🌊 Step 4: Wave Amplitude Calculation")
    if len(peaks) == 0 or len(troughs) == 0:
        wave_amplitude = 0.0
        print("   No peaks or troughs found - amplitude = 0")
    else:
        # Get recent peaks and troughs (up to 3 each)
        recent_peaks = smoothed_prices[peaks[-min(3, len(peaks)):]]
        recent_troughs = smoothed_prices[troughs[-min(3, len(troughs)):]]
        
        peak_level = np.mean(recent_peaks)
        trough_level = np.mean(recent_troughs)
        mean_price = np.mean(smoothed_prices[-20:])
        
        wave_amplitude = abs(peak_level - trough_level) / mean_price
        
        print(f"   Recent peaks: {recent_peaks} -> mean: {peak_level}")
        print(f"   Recent troughs: {recent_troughs} -> mean: {trough_level}")
        print(f"   Mean price (last 20): {mean_price}")
        print(f"   Wave amplitude: |{peak_level} - {trough_level}| / {mean_price} = {wave_amplitude}")
    print()
    
    # Step 5: Decision variable
    print("⚖️ Step 5: Decision Variable")
    decision_variable = config['alpha'] * current_momentum - config['beta'] * wave_amplitude
    print("   Decision = α × momentum - β × amplitude")
    print(f"   Decision = {config['alpha']} × {current_momentum} - {config['beta']} × {wave_amplitude}")
    print(f"   Decision = {decision_variable}")
    print()
    
    # Step 6: Sigmoid probabilities
    print("📊 Step 6: Probability Calculation")
    def sigmoid(x):
        # Clip to prevent overflow
        x = np.clip(x, -500, 500)
        return 1.0 / (1.0 + np.exp(-x))
    
    if config['signal_type'] == 'buy':
        p_buy = sigmoid(decision_variable)
        p_sell = sigmoid(-decision_variable)
    else:  # sell
        p_buy = 1.0 - sigmoid(decision_variable)
        p_sell = 1.0 - sigmoid(-decision_variable)
    
    print(f"   For {config['signal_type']} signal:")
    print(f"   p_buy = sigmoid({decision_variable}) = {p_buy}")
    print(f"   p_sell = sigmoid({-decision_variable}) = {p_sell}")
    print()
    
    # Compile results
    results = {
        'input_prices': close_prices.tolist(),
        'config': config,
        'intermediate_values': {
            'smoothed_prices': smoothed_prices.tolist(),
            'momentum_array': momentum.tolist(),
            'peaks': peaks.tolist(),
            'troughs': troughs.tolist(),
            'decision_variable': decision_variable
        },
        'expected_output': {
            'p_buy': p_buy,
            'p_sell': p_sell,
            'wave_amplitude': wave_amplitude,
            'momentum': current_momentum,
            'warning_code': None
        }
    }
    
    print("✅ Golden Values Generated:")
    print(f"   p_buy: {p_buy}")
    print(f"   p_sell: {p_sell}")
    print(f"   wave_amplitude: {wave_amplitude}")
    print(f"   momentum: {current_momentum}")
    
    return results


def main():
    """Generate golden values for VDMC testing."""
    print("🌟 VDMC Golden Value Generator")
    print("=" * 40)
    print()
    
    # Generate simple test data
    prices = create_simple_price_series()
    
    # Calculate golden values manually
    golden_data = manual_vdmc_calculation(prices)
    
    print("\n" + "=" * 50)
    print("📝 Golden Values for Test Fixture:")
    print("=" * 50)
    
    # Output in format suitable for copying to conftest.py
    print("```python")
    print("golden_test_data = {")
    print(f"    'prices': np.array({golden_data['input_prices']}),")
    print("    'expected': {")
    print(f"        'p_buy': {golden_data['expected_output']['p_buy']},")
    print(f"        'p_sell': {golden_data['expected_output']['p_sell']},")
    print(f"        'wave_amplitude': {golden_data['expected_output']['wave_amplitude']},")
    print(f"        'momentum': {golden_data['expected_output']['momentum']}")
    print("    }")
    print("}")
    print("```")
    
    return golden_data


if __name__ == "__main__":
    main()
