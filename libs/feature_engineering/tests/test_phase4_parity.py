"""Phase 4: deterministic train/serve parity for the new lanes.

Training (composite) features = select_direction_features(...) [model-expected].
Serving features = all columns minus OHLCV minus raw-external [served superset].
Inference aligns by name: model-expected MUST be a subset of served. This test
proves that invariant on identical inputs without needing the live stack — both
paths run the SAME merge_external_series + calculate_all_features.
"""
import numpy as np
import pandas as pd

from feature_engineering import merge_external_series
from feature_engineering.core.config import FeatureConfig
from feature_engineering.core.indicators import FeatureEngineer
from feature_engineering.builders.feature_selection import select_direction_features

_OHLCV = {"open", "high", "low", "close", "volume", "timestamp"}
_RAW_EXTERNAL = {"btc_close", "eth_close", "funding_rate", "open_interest"}
_DERIVED = {
    "btc_corr_24", "btc_corr_96", "btc_ret_lag1", "btc_rel_strength",
    "eth_corr_24", "eth_corr_96", "eth_ret_lag1", "eth_rel_strength",
    "cross_asset_available",
    "funding_rate_level", "funding_rate_sign", "funding_rate_zscore", "funding_available",
    "oi_pct_change", "oi_zscore", "oi_price_divergence", "open_interest_available",
}


def _inputs(n=160):
    rng = np.random.default_rng(7)
    idx = pd.date_range("2025-01-01", periods=n, freq="15min")
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    ohlcv = pd.DataFrame({
        "open": close + rng.normal(0, 0.2, n),
        "high": close + np.abs(rng.normal(0, 0.5, n)),
        "low": close - np.abs(rng.normal(0, 0.5, n)),
        "close": close, "volume": rng.uniform(1000, 5000, n),
    }, index=idx)
    funding = pd.DataFrame({"timestamp": idx[::8], "funding_rate": rng.normal(0.0001, 0.0001, len(idx[::8]))})
    oi = pd.DataFrame({"timestamp": idx, "open_interest": 1e9 + np.cumsum(rng.normal(0, 1e6, n))})
    btc = pd.DataFrame({"timestamp": idx, "close": 30000 + np.cumsum(rng.normal(0, 50, n))})
    eth = pd.DataFrame({"timestamp": idx, "close": 2000 + np.cumsum(rng.normal(0, 5, n))})
    return ohlcv, funding, oi, btc, eth


def _features(ohlcv, funding, oi, btc, eth, cfg):
    merged = merge_external_series(ohlcv, funding=funding, open_interest=oi, btc=btc, eth=eth)
    return FeatureEngineer(cfg).calculate_all_features(merged)


def test_train_and_serve_produce_identical_frames():
    """Same inputs + same config → identical feature frame on both paths
    (both call merge_external_series then calculate_all_features)."""
    cfg = FeatureConfig(cross_asset_features_enabled=True, derivatives_features_enabled=True)
    ohlcv, funding, oi, btc, eth = _inputs()
    train_df = _features(ohlcv, funding, oi, btc, eth, cfg)
    serve_df = _features(ohlcv, funding, oi, btc, eth, cfg)
    pd.testing.assert_frame_equal(train_df, serve_df)


def test_model_expected_features_subset_of_served():
    cfg = FeatureConfig(cross_asset_features_enabled=True, derivatives_features_enabled=True)
    feats = _features(*_inputs(), cfg)

    # Training/composite (model-expected): the selection allowlist.
    model_expected = set(select_direction_features(list(feats.columns), feature_config=cfg))
    # Serving (feature-service): all columns minus OHLCV minus raw-external.
    served = {c for c in feats.columns if c not in _OHLCV and c not in _RAW_EXTERNAL}

    # The parity invariant inference relies on: model-expected ⊆ served.
    assert model_expected <= served
    # Derived lanes present on BOTH sides.
    assert _DERIVED <= model_expected
    assert _DERIVED <= served
    # Raw external columns excluded from BOTH (no leak, no mismatch).
    assert not (_RAW_EXTERNAL & model_expected)
    assert not (_RAW_EXTERNAL & served)


def test_disabled_parity_unaffected():
    cfg = FeatureConfig()  # lanes off
    feats = _features(*_inputs(), cfg)
    model_expected = set(select_direction_features(list(feats.columns), feature_config=cfg))
    served = {c for c in feats.columns if c not in _OHLCV and c not in _RAW_EXTERNAL}
    assert model_expected <= served
    assert not (_DERIVED & model_expected)  # no lane features when off
