"""ATR-normalized price-path lane (price_path_features.v1) — plan Phase 3.

Covers: default-off, deterministic column contract, bounded ranges + no NaN
after warmup, strict causality, and determinism. The lane is computed only by
the shared lib; the trainer's legacy FeatureConfig merely carries the flag.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from feature_engineering import FeatureConfig, FeatureEngineer
from feature_engineering.core.config import (
    PRICE_PATH_ATR_PERIOD,
    PRICE_PATH_FEATURE_VERSION,
    PRICE_PATH_RETURN_PERIODS,
    price_path_feature_columns,
)

_PP_COLS = price_path_feature_columns()
# Per-column clip bounds asserted by the generator (price_path_features.v1).
_PP_BOUNDS = {
    "ret_1": (-1.0, 1.0),
    "ret_4": (-1.0, 1.0),
    "ret_16": (-1.0, 1.0),
    "atr_norm_range": (0.0, 20.0),
    "atr_pct": (0.0, 1.0),
    "close_vs_ema_atr": (-10.0, 10.0),
    "dd_from_peak_atr": (-20.0, 0.0),
    "vol_of_vol": (0.0, 1.0),
}


def _ohlcv(n: int = 800, seed: int = 0) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    close = 100.0 + np.cumsum(rng.randn(n) * 0.5) + 5.0 * np.sin(np.arange(n) / 40.0)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + np.abs(rng.randn(n)) * 0.3,
            "low": close - np.abs(rng.randn(n)) * 0.3,
            "close": close,
            "volume": np.abs(rng.randn(n)) * 1e3,
        }
    )


def test_version_and_contract_columns():
    assert PRICE_PATH_FEATURE_VERSION == "price_path_features.v1"
    assert _PP_COLS == [
        "ret_1",
        "ret_4",
        "ret_16",
        "atr_norm_range",
        "atr_pct",
        "close_vs_ema_atr",
        "dd_from_peak_atr",
        "vol_of_vol",
    ]
    # Return columns are derived from the fixed period tuple.
    assert [f"ret_{n}" for n in PRICE_PATH_RETURN_PERIODS] == _PP_COLS[:3]


def test_price_path_off_adds_no_columns():
    out = FeatureEngineer(FeatureConfig()).calculate_all_features(_ohlcv())
    assert not any(c in out.columns for c in _PP_COLS)


def test_price_path_on_emits_exact_contract():
    cfg = FeatureConfig(price_path_features_enabled=True)
    out = FeatureEngineer(cfg).calculate_all_features(_ohlcv())
    for c in _PP_COLS:
        assert c in out.columns


def test_price_path_bounded_and_no_nan_after_warmup():
    cfg = FeatureConfig(price_path_features_enabled=True)
    out = FeatureEngineer(cfg).calculate_all_features(_ohlcv())
    # Warmup = longest lookback (max return period). After that, all defined.
    warmup = max(PRICE_PATH_RETURN_PERIODS) + PRICE_PATH_ATR_PERIOD
    tail = out.iloc[warmup:]
    for c, (lo, hi) in _PP_BOUNDS.items():
        assert not tail[c].isna().any(), f"{c} has NaN after warmup"
        assert tail[c].min() >= lo - 1e-9, f"{c} below {lo}"
        assert tail[c].max() <= hi + 1e-9, f"{c} above {hi}"


def test_price_path_is_causal():
    cfg = FeatureConfig(price_path_features_enabled=True)
    df = _ohlcv()
    full = FeatureEngineer(cfg).calculate_all_features(df)
    pre = FeatureEngineer(cfg).calculate_all_features(df.iloc[:600])
    # Computing on a truncated prefix yields identical values for those rows —
    # i.e. no future bar influences an earlier feature value.
    for c in _PP_COLS:
        assert np.allclose(
            full[c].values[:600], pre[c].values, equal_nan=True
        ), f"{c} is not causal"


def test_price_path_future_perturbation_does_not_leak():
    cfg = FeatureConfig(price_path_features_enabled=True)
    df = _ohlcv()
    base = FeatureEngineer(cfg).calculate_all_features(df)
    # Perturb a late bar; everything strictly before it must be unchanged.
    k = 700
    df2 = df.copy()
    df2.loc[df2.index[k], ["open", "high", "low", "close"]] *= 1.05
    pert = FeatureEngineer(cfg).calculate_all_features(df2)
    for c in _PP_COLS:
        assert np.allclose(
            base[c].values[:k], pert[c].values[:k], equal_nan=True
        ), f"{c} leaks future info at/after row {k}"


def test_price_path_deterministic():
    cfg = FeatureConfig(price_path_features_enabled=True)
    df = _ohlcv()
    a = FeatureEngineer(cfg).calculate_all_features(df)
    b = FeatureEngineer(cfg).calculate_all_features(df)
    pd.testing.assert_frame_equal(a[_PP_COLS], b[_PP_COLS])


def test_price_path_empty_frame_emits_typed_empty_columns():
    cfg = FeatureConfig(price_path_features_enabled=True)
    out = FeatureEngineer(cfg).calculate_all_features(
        pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    )
    for c in _PP_COLS:
        assert c in out.columns
        assert len(out[c]) == 0
