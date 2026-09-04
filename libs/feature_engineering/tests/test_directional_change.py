"""Causal Directional-Change core: correctness, causality, determinism."""

from __future__ import annotations

import numpy as np
import pandas as pd

from feature_engineering.directional_change import (
    dc_confirmed_state,
    dc_forward_direction,
    dc_pivots,
    theta_from_atr,
    wilder_atr,
)


def _zigzag(n: int = 2000, seed: int = 7) -> np.ndarray:
    rng = np.random.RandomState(seed)
    trend = 5.0 * np.sin(np.arange(n) / 40.0)
    return 100.0 + np.cumsum(rng.randn(n) * 0.3) + trend


def test_pivots_alternate_peak_trough():
    close = _zigzag()
    theta = np.full(close.shape, 0.01)
    pivots, _ = dc_pivots(close, theta)
    assert len(pivots) >= 2
    kinds = [k for _, _, k in pivots]
    # confirmed pivots strictly alternate peak(+1)/trough(-1)
    assert all(kinds[i] != kinds[i + 1] for i in range(len(kinds) - 1))


def test_confirmed_mode_is_causal_prefix_stable():
    close = _zigzag()
    theta = np.full(close.shape, 0.01)
    full = dc_confirmed_state(close, theta)["dir"]
    cut = 1200
    prefix = dc_confirmed_state(close[:cut], theta[:cut])["dir"]
    # Confirmed (causal) state on a prefix must equal the full-series state for
    # those bars — i.e. it uses no future information.
    assert np.array_equal(full[:cut], prefix)


def test_forward_direction_uses_next_pivot_and_is_deterministic():
    close = _zigzag()
    theta = np.full(close.shape, 0.01)
    a = dc_forward_direction(close, theta)
    b = dc_forward_direction(close, theta)
    assert np.array_equal(a, b)
    assert set(np.unique(a)).issubset({-1.0, 0.0, 1.0})
    # tail after the last pivot is unresolved (0)
    assert a[-1] == 0.0


def test_higher_threshold_yields_fewer_pivots():
    close = _zigzag()
    fine, _ = dc_pivots(close, np.full(close.shape, 0.005))
    coarse, _ = dc_pivots(close, np.full(close.shape, 0.05))
    assert len(coarse) <= len(fine)


def test_theta_from_atr_fraction_and_wilder_atr():
    n = 100
    close = np.linspace(100, 110, n)
    atr = np.full(n, 2.0)
    theta = theta_from_atr(close, atr, 1.0)
    assert np.isclose(theta[0], 2.0 / 100.0)
    df = pd.DataFrame({
        "high": close + 1, "low": close - 1, "close": close,
    })
    atr_s = wilder_atr(df["high"], df["low"], df["close"], period=14)
    assert atr_s.notna().sum() > 0
