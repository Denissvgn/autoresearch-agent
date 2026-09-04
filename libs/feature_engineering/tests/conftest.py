"""Pytest configuration and fixtures for feature engineering tests."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """Generate sample OHLCV data for testing.
    
    Returns:
        DataFrame with 100 rows of synthetic OHLCV data
    """
    np.random.seed(42)
    n = 100
    
    # Generate realistic price series with trend
    close_prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    
    # Generate OHLC with realistic relationships
    high = close_prices + np.abs(np.random.randn(n)) * 0.5
    low = close_prices - np.abs(np.random.randn(n)) * 0.5
    open_prices = close_prices + np.random.randn(n) * 0.3
    
    # Ensure OHLC relationships are valid
    high = np.maximum(high, np.maximum(open_prices, close_prices))
    low = np.minimum(low, np.minimum(open_prices, close_prices))
    
    # Generate volume with some correlation to price movement
    volume = 1000000 + np.abs(np.random.randn(n)) * 100000
    
    df = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=n, freq='1h'),
        'open': open_prices,
        'high': high,
        'low': low,
        'close': close_prices,
        'volume': volume,
    })
    
    df.set_index('timestamp', inplace=True)
    
    return df


@pytest.fixture
def sample_feature_config():
    """Generate sample feature configuration for testing.
    
    Returns:
        FeatureConfig with standard parameters
    """
    from feature_engineering.core.config import FeatureConfig
    
    return FeatureConfig(
        sma_periods=[7, 14, 21],
        ema_periods=[12, 26],
        rsi_periods=[14],
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        bb_period=20,
        bb_std=2.0,
        atr_period=14,
        volume_sma_periods=[20],
    )


@pytest.fixture
def expected_feature_columns() -> list[str]:
    """List of expected feature columns from FeatureEngineer.
    
    Returns:
        List of feature column names
    """
    return [
        # Basic features
        'typical_price', 'price_range', 'body_range', 'body_range_ratio',
        # Moving averages
        'sma_7', 'sma_14', 'sma_21', 'ema_12', 'ema_26',
        'close_sma_7_ratio', 'close_sma_14_ratio', 'close_sma_21_ratio',
        'close_ema_12_ratio', 'close_ema_26_ratio',
        # RSI
        'rsi_14', 'rsi_14_oversold', 'rsi_14_overbought',
        # MACD
        'macd', 'macd_signal', 'macd_histogram', 'macd_bullish',
        # Bollinger Bands
        'bb_upper', 'bb_middle', 'bb_lower', 'bb_width', 'bb_position',
        # ATR
        'atr_14',
        # Volatility
        'volatility_20',
        # Volume
        'volume_sma_20', 'volume_ratio_20', 'obv',
        # Price changes
        'return_1', 'log_return_1',
        # Custom features
        'price_position_20', 'price_up_3', 'price_down_3',
        'consecutive_up', 'consecutive_down',
    ]
