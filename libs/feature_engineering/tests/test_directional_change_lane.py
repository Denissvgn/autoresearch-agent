"""Directional-Change feature lane: gating, contract match, parity, selection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from feature_engineering import (
    DIRECTIONAL_CHANGE_FEATURE_CONTRACTS,
    FeatureConfig,
    FeatureEngineer,
    get_feature_contracts,
)
from feature_engineering.builders.feature_selection import select_direction_features


def _ohlcv(n: int = 600, seed: int = 0) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    close = 100.0 + np.cumsum(rng.randn(n) * 0.5) + 4.0 * np.sin(np.arange(n) / 45.0)
    return pd.DataFrame({
        "open": close,
        "high": close + np.abs(rng.randn(n)) * 0.3,
        "low": close - np.abs(rng.randn(n)) * 0.3,
        "close": close,
        "volume": np.abs(rng.randn(n)) * 1000.0,
    })


def test_lane_off_adds_no_columns():
    out = FeatureEngineer(FeatureConfig()).calculate_all_features(_ohlcv())
    assert [c for c in out.columns if c.startswith("dc_")] == []


def test_lane_on_matches_contract_columns_exactly():
    out = FeatureEngineer(
        FeatureConfig(directional_change_features_enabled=True)
    ).calculate_all_features(_ohlcv())
    dc_cols = sorted(c for c in out.columns if c.startswith("dc_"))
    assert dc_cols == sorted(DIRECTIONAL_CHANGE_FEATURE_CONTRACTS.keys())
    assert not out[dc_cols].isna().any().any()
    assert set(np.unique(out["dc_dir_s0"])).issubset({-1.0, 0.0, 1.0})


def test_contracts_gated_by_flag():
    on = get_feature_contracts(FeatureConfig(directional_change_features_enabled=True))
    off = get_feature_contracts(FeatureConfig())
    assert all(c in on for c in DIRECTIONAL_CHANGE_FEATURE_CONTRACTS)
    assert not any(c in off for c in DIRECTIONAL_CHANGE_FEATURE_CONTRACTS)


def test_selection_includes_dc_when_enabled_only():
    out = FeatureEngineer(
        FeatureConfig(directional_change_features_enabled=True)
    ).calculate_all_features(_ohlcv())
    sel_on = select_direction_features(
        list(out.columns),
        feature_config=FeatureConfig(directional_change_features_enabled=True),
    )
    sel_off = select_direction_features(
        list(out.columns), feature_config=FeatureConfig()
    )
    assert any(c.startswith("dc_") for c in sel_on)
    assert not any(c.startswith("dc_") for c in sel_off)


def test_train_serve_parity_identical_frames():
    # OHLCV-only lane: two independent engines on the same bars must agree exactly
    # (this is what makes serve == train without any feature-service fetch wiring).
    df = _ohlcv()
    cfg = FeatureConfig(directional_change_features_enabled=True)
    a = FeatureEngineer(cfg).calculate_all_features(df)
    b = FeatureEngineer(cfg).calculate_all_features(df)
    dc_cols = [c for c in a.columns if c.startswith("dc_")]
    pd.testing.assert_frame_equal(a[dc_cols], b[dc_cols])
