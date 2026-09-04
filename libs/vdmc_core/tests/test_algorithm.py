"""
Comprehensive test suite for VDMC algorithm.

This module contains unit tests for the core VDMC calculation function,
including golden value tests, edge cases, and error handling.
"""

import numpy as np

from vdmc_core import SignalType, VDMCConfig, VDMCOutput, vdmc


class TestVDMCAlgorithm:
    """Test suite for VDMC algorithm core functionality."""
    
    def test_vdmc_basic_functionality(self, sample_price_data, default_config):
        """Test basic VDMC functionality with valid inputs."""
        result = vdmc(sample_price_data, default_config)
        
        assert isinstance(result, VDMCOutput)
        assert 0.0 <= result.p_buy <= 1.0
        assert 0.0 <= result.p_sell <= 1.0
        assert isinstance(result.wave_amplitude, float)
        assert isinstance(result.momentum, float)
        assert result.warning_code is None
    
    def test_vdmc_buy_signal_type(self, sample_price_data, buy_signal_config):
        """Test VDMC with buy signal configuration."""
        result = vdmc(sample_price_data, buy_signal_config)
        
        assert isinstance(result, VDMCOutput)
        assert 0.0 <= result.p_buy <= 1.0
        assert 0.0 <= result.p_sell <= 1.0
        # For buy signals, probabilities should sum to approximately 1
        # (allowing for floating point precision)
        assert abs((result.p_buy + result.p_sell) - 1.0) < 0.01
    
    def test_vdmc_sell_signal_type(self, sample_price_data, sell_signal_config):
        """Test VDMC with sell signal configuration."""
        result = vdmc(sample_price_data, sell_signal_config)
        
        assert isinstance(result, VDMCOutput)
        assert 0.0 <= result.p_buy <= 1.0
        assert 0.0 <= result.p_sell <= 1.0
    
    def test_vdmc_different_parameters(self, sample_price_data):
        """Test VDMC with different parameter configurations."""
        # Test with different alpha/beta values
        config1 = VDMCConfig(alpha=0.5, beta=1.5)
        result1 = vdmc(sample_price_data, config1)
        
        config2 = VDMCConfig(alpha=2.0, beta=0.3)
        result2 = vdmc(sample_price_data, config2)
        
        # Results should be different with different parameters
        assert result1.p_buy != result2.p_buy
        assert result1.p_sell != result2.p_sell
    
    def test_vdmc_different_sigma(self, sample_price_data):
        """Test VDMC with different kernel sigma values."""
        config1 = VDMCConfig(kernel_sigma=3)
        result1 = vdmc(sample_price_data, config1)
        
        config2 = VDMCConfig(kernel_sigma=15)
        result2 = vdmc(sample_price_data, config2)
        
        # Different smoothing should produce different results
        assert result1.wave_amplitude != result2.wave_amplitude
        assert result1.momentum != result2.momentum
    
    def test_vdmc_reproducibility(self, sample_price_data, default_config):
        """Test that VDMC produces reproducible results."""
        result1 = vdmc(sample_price_data, default_config)
        result2 = vdmc(sample_price_data, default_config)
        
        assert result1.p_buy == result2.p_buy
        assert result1.p_sell == result2.p_sell
        assert result1.wave_amplitude == result2.wave_amplitude
        assert result1.momentum == result2.momentum
    
    def test_vdmc_probability_bounds(self, long_price_data, default_config):
        """Test that probabilities are always within valid bounds."""
        result = vdmc(long_price_data, default_config)
        
        assert 0.0 <= result.p_buy <= 1.0
        assert 0.0 <= result.p_sell <= 1.0
        
        # Test with extreme parameter values
        extreme_config = VDMCConfig(alpha=10.0, beta=10.0)
        extreme_result = vdmc(long_price_data, extreme_config)
        
        assert 0.0 <= extreme_result.p_buy <= 1.0
        assert 0.0 <= extreme_result.p_sell <= 1.0


class TestVDMCEdgeCases:
    """Test suite for VDMC edge cases and fallback scenarios."""
    
    def test_short_history_fallback(self, short_price_data, short_history_config):
        """Test fallback logic for short history."""
        result = vdmc(short_price_data, short_history_config)
        
        assert result.warning_code == 1002
        assert result.wave_amplitude == 0.0
        assert 0.0 <= result.p_buy <= 1.0
        assert 0.0 <= result.p_sell <= 1.0
        assert isinstance(result.momentum, float)
    
    def test_nan_input_handling(self, nan_price_data, default_config):
        """Test handling of NaN inputs."""
        result = vdmc(nan_price_data, default_config)
        
        assert result.warning_code == 1001
        assert result.p_buy == 0.5
        assert result.p_sell == 0.5
        assert result.wave_amplitude == 0.0
        assert result.momentum == 0.0
    
    def test_inf_input_handling(self, inf_price_data, default_config):
        """Test handling of infinite inputs."""
        result = vdmc(inf_price_data, default_config)
        
        assert result.warning_code == 1001
        assert result.p_buy == 0.5
        assert result.p_sell == 0.5
        assert result.wave_amplitude == 0.0
        assert result.momentum == 0.0
    
    def test_empty_array_handling(self, default_config):
        """Test handling of empty input arrays."""
        empty_data = np.array([])
        result = vdmc(empty_data, default_config)
        
        assert result.warning_code == 1001
        assert result.p_buy == 0.5
        assert result.p_sell == 0.5
    
    def test_very_short_array_handling(self, default_config):
        """Test handling of very short input arrays."""
        very_short_data = np.array([100.0, 101.0])
        result = vdmc(very_short_data, default_config)
        
        assert result.warning_code == 1001
        assert result.p_buy == 0.5
        assert result.p_sell == 0.5
    
    def test_constant_price_series(self, default_config):
        """Test handling of constant price series."""
        constant_data = np.full(200, 1000.0)
        result = vdmc(constant_data, default_config)
        
        # Should handle constant prices gracefully
        assert isinstance(result, VDMCOutput)
        assert 0.0 <= result.p_buy <= 1.0
        assert 0.0 <= result.p_sell <= 1.0
        # Wave amplitude should be very small for constant prices
        assert abs(result.wave_amplitude) < 0.01
    
    def test_extreme_volatility(self, default_config):
        """Test handling of extremely volatile price series."""
        # Create extremely volatile data
        base_prices = np.full(200, 1000.0)
        extreme_noise = np.random.RandomState(42).normal(0, 500, 200)
        volatile_data = base_prices + extreme_noise
        
        result = vdmc(volatile_data, default_config)
        
        # Should handle extreme volatility without crashing
        assert isinstance(result, VDMCOutput)
        assert 0.0 <= result.p_buy <= 1.0
        assert 0.0 <= result.p_sell <= 1.0


class TestVDMCInputValidation:
    """Test suite for VDMC input validation."""
    
    def test_non_numpy_array_input(self, default_config):
        """Test handling of non-numpy array inputs."""
        list_input = [100, 101, 102, 103, 104]
        
        # Should handle list input by converting or rejecting
        result = vdmc(np.array(list_input), default_config)
        assert result.warning_code == 1002  # Short history
    
    def test_configuration_validation(self, sample_price_data):
        """Test that configuration validation works correctly."""
        # Valid configuration should work
        valid_config = VDMCConfig(
            lookback_period=200,
            kernel_sigma=10,
            alpha=1.5,
            beta=0.5
        )
        
        result = vdmc(sample_price_data, valid_config)
        assert isinstance(result, VDMCOutput)
    
    def test_signal_type_behavior(self, sample_price_data):
        """Test that different signal types produce different results."""
        buy_config = VDMCConfig(signal_type=SignalType.BUY)
        sell_config = VDMCConfig(signal_type=SignalType.SELL)
        
        buy_result = vdmc(sample_price_data, buy_config)
        sell_result = vdmc(sample_price_data, sell_config)
        
        # Buy and sell signals should produce different probability distributions
        assert buy_result.p_buy != sell_result.p_buy
        assert buy_result.p_sell != sell_result.p_sell


class TestVDMCGoldenValues:
    """Test suite for VDMC golden value verification."""
    
    def test_vdmc_with_golden_data(self, golden_test_data):
        """
        Test VDMC with pre-calculated golden values.
        
        This test verifies that the VDMC implementation produces the exact
        expected outputs for a known input dataset. The expected values were
        manually calculated and verified using scripts/generate_golden_values.py.
        
        This test ensures mathematical correctness of the VDMC algorithm
        implementation as required by Task S4-T4.
        """
        # Arrange
        test_prices = golden_test_data['prices']
        expected = golden_test_data['expected']
        
        # Use configuration that matches the golden value generation
        # (uses default lookback_period=120 which satisfies validation)
        config = VDMCConfig(
            lookback_period=120,     # Default value, satisfies validation
            kernel_sigma=5,          # Default value
            alpha=1.2,              # Default value
            beta=0.8,               # Default value
            signal_type=SignalType.BUY  # Default value
        )
        
        # Act
        result = vdmc(test_prices, config)
        
        # Assert - Verify all components match expected golden values
        assert isinstance(result, VDMCOutput)
        assert result.warning_code is None, "Golden test should not trigger any warnings"
        
        # Check probabilities (rounded to 6 decimal places for floating point precision)
        assert round(result.p_buy, 6) == round(expected['p_buy'], 6), \
            f"p_buy mismatch: got {result.p_buy}, expected {expected['p_buy']}"
        assert round(result.p_sell, 6) == round(expected['p_sell'], 6), \
            f"p_sell mismatch: got {result.p_sell}, expected {expected['p_sell']}"
        
        # Check intermediate values (rounded to 8 decimal places)
        assert round(result.wave_amplitude, 8) == round(expected['wave_amplitude'], 8), \
            f"wave_amplitude mismatch: got {result.wave_amplitude}, expected {expected['wave_amplitude']}"
        assert round(result.momentum, 8) == round(expected['momentum'], 8), \
            f"momentum mismatch: got {result.momentum}, expected {expected['momentum']}"
        
        # Verify probabilities sum to approximately 1.0 (fundamental check)
        probability_sum = result.p_buy + result.p_sell
        assert abs(probability_sum - 1.0) < 0.001, \
            f"Probabilities should sum to ~1.0, got {probability_sum}"
    
    def test_golden_values_are_deterministic(self, golden_test_data):
        """
        Test that golden values are deterministic and reproducible.
        
        This test ensures that running the same calculation multiple times
        produces identical results, which is crucial for a golden value test.
        """
        test_prices = golden_test_data['prices']
        config = VDMCConfig(
            lookback_period=120,     # Default value, satisfies validation
            kernel_sigma=5,
            alpha=1.2,
            beta=0.8,
            signal_type=SignalType.BUY
        )
        
        # Run calculation multiple times
        results = []
        for _ in range(5):
            result = vdmc(test_prices, config)
            results.append(result)
        
        # All results should be identical
        base_result = results[0]
        for i, result in enumerate(results[1:], 1):
            assert result.p_buy == base_result.p_buy, f"Run {i+1} p_buy differs from run 1"
            assert result.p_sell == base_result.p_sell, f"Run {i+1} p_sell differs from run 1"
            assert result.wave_amplitude == base_result.wave_amplitude, f"Run {i+1} wave_amplitude differs from run 1"
            assert result.momentum == base_result.momentum, f"Run {i+1} momentum differs from run 1"