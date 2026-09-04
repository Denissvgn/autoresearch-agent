"""Integrations module providing reusable feature engineering and indicator calculations."""

from .indicators import (
    build_direction_feature_set,
    build_indicator_features,
    calculate_atr,
    calculate_bollinger,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
    calculate_vdmc,
    calculate_vdmc_macd_proxy,
    calculate_vwap,
    compare_feature_parity,
)

__all__ = [
    "build_direction_feature_set",
    "build_indicator_features",
    "calculate_atr",
    "calculate_bollinger",
    "calculate_ema",
    "calculate_macd",
    "calculate_rsi",
    "calculate_sma",
    "calculate_vdmc",
    "calculate_vdmc_macd_proxy",
    "calculate_vwap",
    "compare_feature_parity",
]
