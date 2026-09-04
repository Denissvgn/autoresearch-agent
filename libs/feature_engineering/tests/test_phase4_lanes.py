"""Phase 4: cross-asset + derivatives feature lanes in the shared library.

Pins: (1) opt-in gating — disabled (default) adds nothing, so existing models'
schema is unchanged; (2) graceful degradation — when enabled, the column SET is
identical whether or not the external series is present (zero-filled + an
availability flag), which is what keeps train/serve parity; (3) contracts are
included only when the lane is enabled and validate the produced frame.
"""
import numpy as np
import pandas as pd
import pytest

from feature_engineering.core.config import FeatureConfig
from feature_engineering.core.indicators import FeatureEngineer
from feature_engineering.contracts import get_feature_contracts, validate_feature_frame
from feature_engineering.builders.feature_selection import select_direction_features

CROSS_ASSET_COLS = {
    "btc_ret_lag1", "btc_rel_strength", "btc_corr_24", "btc_corr_96",
    "eth_ret_lag1", "eth_rel_strength", "eth_corr_24", "eth_corr_96",
    "cross_asset_available",
}
FUNDING_COLS = {
    "funding_rate_level", "funding_rate_sign", "funding_rate_zscore",
    "funding_available",
}
OI_COLS = {
    "oi_pct_change", "oi_zscore", "oi_price_divergence", "open_interest_available",
}
DERIV_COLS = FUNDING_COLS | OI_COLS  # derivatives master = both sub-lanes


def _ohlcv(n=160, *, with_majors=False, with_derivs=False):
    rng = np.random.default_rng(0)
    idx = pd.date_range("2025-01-01", periods=n, freq="15min")
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame({
        "open": close + rng.normal(0, 0.2, n),
        "high": close + np.abs(rng.normal(0, 0.5, n)),
        "low": close - np.abs(rng.normal(0, 0.5, n)),
        "close": close,
        "volume": rng.uniform(1000, 5000, n),
    }, index=idx)
    if with_majors:
        df["btc_close"] = 30000 + np.cumsum(rng.normal(0, 50, n))
        df["eth_close"] = 2000 + np.cumsum(rng.normal(0, 5, n))
    if with_derivs:
        df["funding_rate"] = rng.normal(0.0001, 0.0001, n)
        df["open_interest"] = 1e9 + np.cumsum(rng.normal(0, 1e6, n))
    return df


def _cols(config, df):
    out = FeatureEngineer(config).calculate_all_features(df)
    return set(out.columns), out


def test_lanes_disabled_by_default_add_nothing():
    base_cols, _ = _cols(FeatureConfig(), _ohlcv())
    assert not (CROSS_ASSET_COLS & base_cols)
    assert not (DERIV_COLS & base_cols)


def test_cross_asset_enabled_with_majors():
    cfg = FeatureConfig(cross_asset_features_enabled=True)
    cols, out = _cols(cfg, _ohlcv(with_majors=True))
    assert CROSS_ASSET_COLS <= cols
    assert (out["cross_asset_available"] == 1.0).all()
    for w in (24, 96):
        v = out["btc_corr_" + str(w)].dropna()
        assert ((v >= -1.0001) & (v <= 1.0001)).all()
    assert out[list(CROSS_ASSET_COLS)].notna().all().all()


def test_cross_asset_enabled_without_majors_is_zero_filled():
    """Parity: same columns even when the external series is absent."""
    cfg = FeatureConfig(cross_asset_features_enabled=True)
    cols, out = _cols(cfg, _ohlcv(with_majors=False))
    assert CROSS_ASSET_COLS <= cols  # schema identical to the with-majors case
    assert (out["cross_asset_available"] == 0.0).all()
    assert (out["btc_corr_24"] == 0.0).all()
    assert out[list(CROSS_ASSET_COLS)].notna().all().all()


def test_derivatives_enabled_present_and_absent():
    cfg = FeatureConfig(derivatives_features_enabled=True)  # master → both sub-lanes
    cols_present, out_present = _cols(cfg, _ohlcv(with_derivs=True))
    cols_absent, out_absent = _cols(cfg, _ohlcv(with_derivs=False))
    assert DERIV_COLS <= cols_present and DERIV_COLS <= cols_absent  # stable schema
    assert (out_present["funding_available"] == 1.0).all()
    assert (out_present["open_interest_available"] == 1.0).all()
    assert (out_absent["funding_available"] == 0.0).all()
    assert (out_absent["open_interest_available"] == 0.0).all()
    assert out_present[list(DERIV_COLS)].notna().all().all()
    assert (out_absent["oi_pct_change"] == 0.0).all()


def test_funding_only_lane_excludes_open_interest():
    """Sub-lane independence: funding on, open-interest off → only funding cols,
    consistently across indicators, selection, and contracts."""
    cfg = FeatureConfig(funding_features_enabled=True)
    cols, out = _cols(cfg, _ohlcv(with_derivs=True))
    assert FUNDING_COLS <= cols          # funding lane produced
    assert not (OI_COLS & cols)          # open-interest lane NOT produced
    assert (out["funding_available"] == 1.0).all()
    sel = set(select_direction_features(list(cols), funding_features_enabled=True))
    assert FUNDING_COLS <= sel and not (OI_COLS & sel)
    contracts = set(get_feature_contracts(cfg))
    assert FUNDING_COLS <= contracts and not (OI_COLS & contracts)


def test_open_interest_only_lane_excludes_funding():
    cfg = FeatureConfig(open_interest_features_enabled=True)
    cols, out = _cols(cfg, _ohlcv(with_derivs=True))
    assert OI_COLS <= cols               # open-interest lane produced
    assert not (FUNDING_COLS & cols)     # funding lane NOT produced
    assert (out["open_interest_available"] == 1.0).all()
    sel = set(select_direction_features(list(cols), open_interest_features_enabled=True))
    assert OI_COLS <= sel and not (FUNDING_COLS & sel)
    contracts = set(get_feature_contracts(cfg))
    assert OI_COLS <= contracts and not (FUNDING_COLS & contracts)


def test_selection_gates_lanes_and_never_leaks_raw_inputs():
    """select_direction_features picks the DERIVED lane features only when the
    flag is on, and NEVER selects the raw merged inputs (no leakage)."""
    produced = [
        "close", "rsi_14",
        "btc_close", "eth_close", "funding_rate", "open_interest",  # raw inputs
        *CROSS_ASSET_COLS, *DERIV_COLS,                              # derived
    ]
    off = set(select_direction_features(produced))
    on = set(select_direction_features(
        produced, cross_asset_features_enabled=True, derivatives_features_enabled=True
    ))
    # Disabled: none of the lane features selected.
    assert not ((CROSS_ASSET_COLS | DERIV_COLS) & off)
    # Enabled: all lane features selected.
    assert (CROSS_ASSET_COLS | DERIV_COLS) <= on
    # Raw inputs never selected in either mode.
    raw = {"btc_close", "eth_close", "funding_rate", "open_interest"}
    assert not (raw & on) and not (raw & off)


def test_contracts_conditional_and_validate():
    assert not (set(get_feature_contracts(FeatureConfig())) & CROSS_ASSET_COLS)
    cfg = FeatureConfig(cross_asset_features_enabled=True, derivatives_features_enabled=True)
    contracts = get_feature_contracts(cfg)
    assert CROSS_ASSET_COLS <= set(contracts) and DERIV_COLS <= set(contracts)
    _, out = _cols(cfg, _ohlcv(with_majors=True, with_derivs=True))
    res = validate_feature_frame(out, mode="warn", feature_config=cfg)
    # No contracted column should be missing from the produced frame.
    assert not (CROSS_ASSET_COLS & set(res.missing_columns))
    assert not (DERIV_COLS & set(res.missing_columns))
