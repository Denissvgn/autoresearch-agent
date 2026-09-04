"""Tests for technical indicator calculations."""

import numpy as np
import pandas as pd
import pytest

from feature_engineering.core.indicators import FeatureEngineer


class TestFeatureEngineer:
    """Test suite for FeatureEngineer indicator calculations."""
    
    def test_calculate_all_features(self, sample_ohlcv_data, sample_feature_config):
        """Test that all features are calculated without errors."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)
        
        # Should return DataFrame with features
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(sample_ohlcv_data)
        
        # Should have feature columns
        assert len(result.columns) > 0
        
        # Should not have all NaN columns
        for col in result.columns:
            assert not result[col].isna().all(), f"Column {col} is all NaN"
    
    def test_basic_features(self, sample_ohlcv_data, sample_feature_config):
        """Test basic feature calculations."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)
        
        # Typical price = (high + low + close) / 3
        assert 'typical_price' in result.columns
        expected_typical = (sample_ohlcv_data['high'] + sample_ohlcv_data['low'] + sample_ohlcv_data['close']) / 3
        pd.testing.assert_series_equal(result['typical_price'], expected_typical, check_names=False)
        
        # High-low range = high - low
        assert 'high_low_range' in result.columns
        expected_range = sample_ohlcv_data['high'] - sample_ohlcv_data['low']
        pd.testing.assert_series_equal(result['high_low_range'], expected_range, check_names=False)
    
    def test_moving_averages(self, sample_ohlcv_data, sample_feature_config):
        """Test SMA and EMA calculations."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)
        
        # Check SMA columns exist
        for period in sample_feature_config.sma_periods:
            col_name = f'sma_{period}'
            assert col_name in result.columns, f"Missing {col_name}"
            
            # SMA should not be NaN after warmup period
            assert not result[col_name].iloc[period:].isna().all()
        
        # Check EMA columns exist
        for period in sample_feature_config.ema_periods:
            col_name = f'ema_{period}'
            assert col_name in result.columns, f"Missing {col_name}"
    
    def test_rsi_calculation(self, sample_ohlcv_data, sample_feature_config):
        """Test RSI calculation and bounds."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)
        
        rsi_col = f'rsi_{sample_feature_config.rsi_periods[0]}'
        assert rsi_col in result.columns
        
        # RSI should be between 0 and 100 (after warmup)
        rsi_values = result[rsi_col].dropna()
        assert (rsi_values >= 0).all(), "RSI values below 0"
        assert (rsi_values <= 100).all(), "RSI values above 100"
        
        # Check oversold/overbought flags
        assert f'{rsi_col}_oversold' in result.columns
        assert f'{rsi_col}_overbought' in result.columns
    
    def test_macd_calculation(self, sample_ohlcv_data, sample_feature_config):
        """Test MACD indicator calculation."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)
        
        # Check MACD components exist
        assert 'macd' in result.columns
        assert 'macd_signal' in result.columns
        assert 'macd_histogram' in result.columns
        assert 'macd_bullish' in result.columns
        
        # Histogram should equal MACD - Signal
        macd_hist = result['macd'] - result['macd_signal']
        pd.testing.assert_series_equal(
            result['macd_histogram'].dropna(),
            macd_hist.dropna(),
            check_names=False,
            atol=1e-6
        )
    
    def test_bollinger_bands(self, sample_ohlcv_data, sample_feature_config):
        """Test Bollinger Bands calculation."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)
        
        # Check BB components exist
        assert 'bb_upper' in result.columns
        assert 'bb_middle' in result.columns
        assert 'bb_lower' in result.columns
        assert 'bb_width' in result.columns
        assert 'bb_position' in result.columns
        
        # Upper band should be >= middle >= lower band
        valid_idx = result['bb_upper'].notna()
        assert (result.loc[valid_idx, 'bb_upper'] >= result.loc[valid_idx, 'bb_middle']).all()
        assert (result.loc[valid_idx, 'bb_middle'] >= result.loc[valid_idx, 'bb_lower']).all()
        
        # BB position should be mostly between 0 and 1 (allow outliers)
        bb_pos = result['bb_position'].dropna()
        # Just check that the feature exists and has reasonable values (not all NaN or inf)
        assert len(bb_pos) > 0
        assert not np.isinf(bb_pos).any()
    
    def test_atr_calculation(self, sample_ohlcv_data, sample_feature_config):
        """Test ATR (Average True Range) calculation."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)
        
        # ATR is stored as 'atr' not 'atr_{period}'
        assert 'atr' in result.columns
        
        # ATR should be non-negative
        atr_values = result['atr'].dropna()
        assert (atr_values >= 0).all(), "ATR should be non-negative"
    
    def test_volume_indicators(self, sample_ohlcv_data, sample_feature_config):
        """Test volume-based indicators."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)
        
        # Check volume SMA exists (uses plural 'periods')
        vol_sma_col = f'volume_sma_{sample_feature_config.volume_sma_periods[0]}'
        assert vol_sma_col in result.columns
        
        # Check volume ratio exists
        vol_ratio_col = f'volume_ratio_{sample_feature_config.volume_sma_periods[0]}'
        assert vol_ratio_col in result.columns
        
        # Check OBV exists
        assert 'obv' in result.columns
    
    def test_returns_calculation(self, sample_ohlcv_data, sample_feature_config):
        """Test return calculations."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)
        
        # Check return columns exist
        assert 'return_1' in result.columns
        assert 'log_return_1' in result.columns
        
        # Simple return calculation check (skip NaN values due to cleaning)
        expected_return = sample_ohlcv_data['close'].pct_change(1)
        # After cleaning, first row may be filled, so compare non-NaN values
        mask = expected_return.notna()
        pd.testing.assert_series_equal(
            result['return_1'][mask],
            expected_return[mask],
            check_names=False,
            atol=1e-6
        )
    
    def test_custom_features(self, sample_ohlcv_data, sample_feature_config):
        """Test custom feature calculations."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)
        
        # Check price position
        assert 'price_position_20' in result.columns
        
        # Check price up/down indicators (not period-based)
        assert 'price_up' in result.columns
        assert 'price_down' in result.columns
    
    def test_nan_handling(self, sample_ohlcv_data, sample_feature_config):
        """Test that NaN values are properly handled."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)
        
        # First few rows may have NaN due to lookback periods
        # But should not have inf values
        for col in result.columns:
            assert not np.isinf(result[col]).any(), f"Column {col} has inf values"
    
    def test_empty_dataframe(self, sample_feature_config):
        """Test handling of empty DataFrame."""
        engineer = FeatureEngineer(sample_feature_config)
        empty_df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        
        result = engineer.calculate_all_features(empty_df)
        
        # Should return empty DataFrame with feature columns
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
    
    def test_single_row(self, sample_feature_config):
        """Test handling of single row DataFrame."""
        engineer = FeatureEngineer(sample_feature_config)
        single_row = pd.DataFrame({
            'open': [100.0],
            'high': [101.0],
            'low': [99.0],
            'close': [100.5],
            'volume': [1000000.0],
        })
        
        result = engineer.calculate_all_features(single_row)
        
        # Should return DataFrame with 1 row
        assert len(result) == 1
        
        # Most features will be NaN due to lookback requirements
        # But basic features should exist
        assert 'typical_price' in result.columns
        assert not result['typical_price'].isna().all()

    def test_advanced_microstructure_features_present(self, sample_ohlcv_data, sample_feature_config):
        """Verify items 8-12 (v2.1.0 ML-39 parity) are computed."""
        engineer = FeatureEngineer(sample_feature_config)
        result = engineer.calculate_all_features(sample_ohlcv_data)

        expected_cols = [
            'vwap_10', 'vwap_20', 'vwap_60',
            'vwap_ratio_10', 'vwap_ratio_20', 'vwap_ratio_60',
            'spread_proxy_10', 'spread_proxy_20',
            'spread_proxy_ma_10', 'spread_proxy_ma_20',
            'order_flow_imbalance_10', 'order_flow_imbalance_20',
            'kyle_lambda_10', 'kyle_lambda_20',
            'amihud_illiq_10', 'amihud_illiq_20',
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing advanced microstructure feature: {col}"
            assert result[col].notna().sum() > 0, f"All NaN: {col}"


class TestIndicatorEdgeCases:
    """Test edge cases and error handling."""
    
    def test_constant_prices(self, sample_feature_config):
        """Test indicators with constant price series."""
        engineer = FeatureEngineer(sample_feature_config)
        
        # Create DataFrame with constant prices
        constant_df = pd.DataFrame({
            'open': [100.0] * 50,
            'high': [100.0] * 50,
            'low': [100.0] * 50,
            'close': [100.0] * 50,
            'volume': [1000000.0] * 50,
        })
        
        result = engineer.calculate_all_features(constant_df)
        
        # Should not raise errors
        assert isinstance(result, pd.DataFrame)
        
        # RSI for constant prices can be NaN or 100 (division by near-zero)
        rsi_col = f'rsi_{sample_feature_config.rsi_periods[0]}'
        if rsi_col in result.columns:
            rsi_values = result[rsi_col].dropna()
            if len(rsi_values) > 0:
                # RSI should exist and be reasonable (not necessarily 50 due to division by zero handling)
                assert (rsi_values >= 0).all() and (rsi_values <= 100).all()
    
    def test_missing_columns(self, sample_feature_config):
        """Test handling of missing required columns."""
        engineer = FeatureEngineer(sample_feature_config)
        
        # Missing 'close' column
        incomplete_df = pd.DataFrame({
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'volume': [1000000.0] * 10,
        })
        
        with pytest.raises(ValueError):
            engineer.calculate_all_features(incomplete_df)
