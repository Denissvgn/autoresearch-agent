"""Stationarity pass (stationary_features.v1).

Opt-in lane that replaces price/volume-scale columns with scale-free
counterparts. Pins: schema with flag OFF is unchanged (legacy hash safety),
flag ON swaps the documented columns, the rolling z is strictly causal, and
the schema-flags builder versions the lane.
"""

import numpy as np
import pandas as pd
import pytest

from feature_engineering.contracts import build_feature_schema_flags
from feature_engineering.core.config import FeatureConfig
from feature_engineering.core.indicators import FeatureEngineer

LEVEL_COLUMNS = [
    "vwap_10", "vwap_20", "vwap_60",
    "kyle_lambda_10", "kyle_lambda_20",
    "amihud_illiq_10", "amihud_illiq_20",
    "macd", "macd_signal", "macd_histogram",
]
STATIONARY_COLUMNS = [
    "kyle_lambda_z_10", "kyle_lambda_z_20",
    "amihud_illiq_z_10", "amihud_illiq_z_20",
    "macd_histogram_pct",
]


def _features(sample_ohlcv_data, **config_overrides) -> pd.DataFrame:
    config = FeatureConfig(**config_overrides)
    return FeatureEngineer(config).calculate_all_features(sample_ohlcv_data)


def test_flag_off_keeps_legacy_schema(sample_ohlcv_data):
    out = _features(sample_ohlcv_data)
    for col in LEVEL_COLUMNS:
        assert col in out.columns, col
    for col in STATIONARY_COLUMNS:
        assert col not in out.columns, col


def test_flag_on_swaps_level_columns(sample_ohlcv_data):
    out = _features(sample_ohlcv_data, stationary_features_enabled=True)
    for col in LEVEL_COLUMNS:
        assert col not in out.columns, col
    for col in STATIONARY_COLUMNS:
        assert col in out.columns, col
    # The scale-free ratio family stays in both modes.
    assert "vwap_ratio_10" in out.columns
    assert "macd_bullish" in out.columns


def test_flag_on_swaps_vdmc_price_scale_columns(sample_ohlcv_data):
    # VDMC needs >=120 rows of history — extend the sample.
    n = 300
    rng = np.random.default_rng(5)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    df = pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.3, n),
            "high": close + np.abs(rng.normal(0, 0.5, n)),
            "low": close - np.abs(rng.normal(0, 0.5, n)),
            "close": close,
            "volume": 1e6 + np.abs(rng.normal(0, 1e5, n)),
        },
        index=pd.date_range("2024-01-01", periods=n, freq="1h"),
    )
    out = _features(
        df, stationary_features_enabled=True, vdmc_enabled=True,
    )
    assert "vdmc_momentum" not in out.columns
    assert "vdmc_amplitude" not in out.columns
    assert "vdmc_momentum_rel" in out.columns
    assert "vdmc_amplitude_rel" in out.columns
    # Probability outputs are scale-free already and stay untouched.
    assert "vdmc_buy_proba" in out.columns


def test_causal_z_is_truncation_invariant():
    """Causality: values computed on a prefix must equal the same rows
    computed on the full series (no future rows can change past z-scores)."""
    rng = np.random.default_rng(11)
    s = pd.Series(rng.lognormal(0, 1, 2000))
    full = FeatureEngineer._causal_z(s)
    prefix = FeatureEngineer._causal_z(s.iloc[:1500])
    pd.testing.assert_series_equal(full.iloc[:1500], prefix)


def test_schema_flags_version_the_lane():
    config = FeatureConfig(stationary_features_enabled=True)
    flags = build_feature_schema_flags(config, selected_feature_names=["a", "b"])
    assert flags["stationary_features"]["enabled"] is True
    assert flags["stationary_features"]["version"] == "stationary_features.v1"
    assert flags["stationary_features"]["selected_feature_names"] == ["a", "b"]


def test_schema_flags_empty_when_all_lanes_off():
    assert build_feature_schema_flags(FeatureConfig()) == {}


def test_schema_flags_reject_unknown_version():
    config = FeatureConfig(
        stationary_features_enabled=True,
        stationary_features_version="stationary_features.v999",
    )
    with pytest.raises(ValueError, match="stationary_features_version"):
        build_feature_schema_flags(config)
