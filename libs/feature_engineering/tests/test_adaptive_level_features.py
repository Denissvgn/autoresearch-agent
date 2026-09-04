"""Tests for DPU-041/DPU-042 adaptive support/resistance features."""

import numpy as np
import pandas as pd

from feature_engineering.contracts import (
    ADAPTIVE_LEVEL_FEATURE_CONTRACTS,
    get_feature_contracts,
    validate_feature_frame,
)
from feature_engineering.core.config import FeatureConfig
from feature_engineering.core.indicators import FeatureEngineer, compute_indicator_lookbacks


ADAPTIVE_LEVEL_COLUMNS = [
    "close_fib_bucket_24",
    "close_fib_bucket_96",
    "dist_to_support_24",
    "dist_to_resistance_24",
    "dist_to_support_96",
    "dist_to_resistance_96",
    "sma_local_to_long_ratio_24",
    "range_local_to_long_ratio_24",
    "ohlc_bucket_spread_24",
    "close_bucket_delta_24",
]

CYCLE_LABEL_ONLY_COLUMNS = [
    "swing_low_label",
    "swing_high_label",
    "cycle_phase_target",
    "cycle_transition_weight",
    "cycle_phase_proba",
]


def _fixed_grid_ohlcv(rows: int = 128) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC")
    close = np.linspace(90.0, 110.0, rows)
    volume = np.linspace(1_000_000.0, 1_100_000.0, rows)
    return pd.DataFrame(
        {
            "open": close,
            "high": np.full(rows, 110.0),
            "low": np.full(rows, 90.0),
            "close": close,
            "volume": volume,
        },
        index=index,
    )


def test_adaptive_level_features_are_flag_gated():
    df = _fixed_grid_ohlcv()

    disabled = FeatureEngineer(FeatureConfig(adaptive_levels_enabled=False)).calculate_all_features(df)
    enabled = FeatureEngineer(FeatureConfig(adaptive_levels_enabled=True)).calculate_all_features(df)

    assert not set(ADAPTIVE_LEVEL_COLUMNS) & set(disabled.columns)
    assert all(col in enabled.columns for col in ADAPTIVE_LEVEL_COLUMNS)


def test_adaptive_level_features_are_bounded_and_contract_valid():
    cfg = FeatureConfig(adaptive_levels_enabled=True)
    result = FeatureEngineer(cfg).calculate_all_features(_fixed_grid_ohlcv())
    adaptive = result[ADAPTIVE_LEVEL_COLUMNS]

    assert np.isfinite(adaptive.to_numpy()).all()
    for col in ("close_fib_bucket_24", "close_fib_bucket_96", "ohlc_bucket_spread_24"):
        assert adaptive[col].between(0, 6).all()
    assert adaptive["close_bucket_delta_24"].between(-6, 6).all()
    for col in (
        "dist_to_support_24",
        "dist_to_resistance_24",
        "dist_to_support_96",
        "dist_to_resistance_96",
    ):
        assert adaptive[col].between(0, 1).all()
    for col in ("sma_local_to_long_ratio_24", "range_local_to_long_ratio_24"):
        assert adaptive[col].between(0, 5).all()

    contracts = {
        name: ADAPTIVE_LEVEL_FEATURE_CONTRACTS[name]
        for name in ADAPTIVE_LEVEL_COLUMNS
    }
    assert validate_feature_frame(adaptive, mode="enforce", contracts=contracts).ok


def test_close_bucket_is_monotonic_on_fixed_grid():
    result = FeatureEngineer(FeatureConfig(adaptive_levels_enabled=True)).calculate_all_features(
        _fixed_grid_ohlcv()
    )

    assert result["close_fib_bucket_24"].is_monotonic_increasing
    assert set(result["close_fib_bucket_24"].unique()).issubset(set(range(7)))


def test_adaptive_level_features_are_causal():
    cfg = FeatureConfig(adaptive_levels_enabled=True)
    base = _fixed_grid_ohlcv(rows=160)
    mutated = base.copy()
    cutoff = 96
    mutated.iloc[cutoff:, mutated.columns.get_loc("high")] = 250.0
    mutated.iloc[cutoff:, mutated.columns.get_loc("low")] = 50.0
    mutated.iloc[cutoff:, mutated.columns.get_loc("close")] = 220.0

    base_features = FeatureEngineer(cfg).calculate_all_features(base)
    mutated_features = FeatureEngineer(cfg).calculate_all_features(mutated)

    pd.testing.assert_frame_equal(
        base_features.loc[base_features.index[:cutoff], ADAPTIVE_LEVEL_COLUMNS],
        mutated_features.loc[mutated_features.index[:cutoff], ADAPTIVE_LEVEL_COLUMNS],
    )


def test_adaptive_level_contracts_and_lookbacks_follow_flag():
    disabled = FeatureConfig(adaptive_levels_enabled=False)
    enabled = FeatureConfig(adaptive_levels_enabled=True)

    disabled_contracts = get_feature_contracts(disabled)
    enabled_contracts = get_feature_contracts(enabled)
    disabled_lookbacks = compute_indicator_lookbacks(disabled)
    enabled_lookbacks = compute_indicator_lookbacks(enabled)

    assert not set(ADAPTIVE_LEVEL_COLUMNS) & set(disabled_contracts)
    assert not set(ADAPTIVE_LEVEL_COLUMNS) & set(disabled_lookbacks)
    assert all(name in enabled_contracts for name in ADAPTIVE_LEVEL_COLUMNS)
    assert enabled_lookbacks["close_fib_bucket_24"] == 24
    assert enabled_lookbacks["sma_local_to_long_ratio_24"] == 96
    assert enabled_lookbacks["close_bucket_delta_24"] == 25


def test_cycle_targets_never_appear_in_live_feature_frame():
    result = FeatureEngineer(
        FeatureConfig(adaptive_levels_enabled=True)
    ).calculate_all_features(_fixed_grid_ohlcv())

    assert not set(CYCLE_LABEL_ONLY_COLUMNS) & set(result.columns)
