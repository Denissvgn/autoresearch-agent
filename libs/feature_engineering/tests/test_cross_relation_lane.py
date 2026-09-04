"""Canonical cross-instrument relation lane (cross_relation.v1)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from feature_engineering.advanced.cross_relation import (
    CROSS_RELATION_FEATURE_VERSION,
    compute_cross_relation_features,
    cross_relation_feature_columns,
    rank_donors_by_correlation,
)

_COLS = cross_relation_feature_columns()


def _rets(n=400, seed=0):
    rng = np.random.RandomState(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    btc = pd.Series(rng.randn(n) * 0.01, index=idx)
    # target partially follows BTC + idiosyncratic noise
    tgt = 0.6 * btc + pd.Series(rng.randn(n) * 0.01, index=idx)
    basket = 0.4 * btc + pd.Series(rng.randn(n) * 0.01, index=idx)
    return tgt, btc, basket


def test_version_and_canonical_columns():
    assert CROSS_RELATION_FEATURE_VERSION == "cross_relation.v1"
    assert _COLS == [
        "rel_corr_btc_30", "rel_corr_btc_120",
        "rel_beta_btc_120", "rel_strength_btc_30",
        "rel_corr_donorbasket_30", "rel_corr_donorbasket_120",
        "rel_strength_donorbasket_30",
    ]


def test_emits_exact_contract_and_bounded():
    tgt, btc, basket = _rets()
    out = compute_cross_relation_features(tgt, btc, basket)
    assert list(out.columns) == _COLS
    assert len(out) == len(tgt) and out.index.equals(tgt.index)
    assert not out.isna().any().any()
    for c in out.columns:
        if "corr" in c:
            assert out[c].min() >= -1.0 - 1e-9 and out[c].max() <= 1.0 + 1e-9
        elif "beta" in c:
            assert out[c].min() >= -5.0 - 1e-9 and out[c].max() <= 5.0 + 1e-9
        else:  # strength
            assert out[c].min() >= -0.5 - 1e-9 and out[c].max() <= 0.5 + 1e-9


def test_canonical_columns_are_instrument_independent():
    # Same column SET + order regardless of which target / donors — the property
    # that lets ONE pooled policy read any instrument's relations identically.
    a = compute_cross_relation_features(*_rets(seed=1))
    b = compute_cross_relation_features(*_rets(seed=2))
    assert list(a.columns) == list(b.columns) == _COLS


def test_missing_references_degrade_to_zero():
    tgt, _, _ = _rets()
    out = compute_cross_relation_features(tgt, btc_ret=None, donor_basket_ret=None)
    assert list(out.columns) == _COLS
    assert (out.abs().sum().sum()) == 0.0  # all zero when no references


def test_positive_correlation_is_detected():
    tgt, btc, basket = _rets(n=600)
    out = compute_cross_relation_features(tgt, btc, basket)
    # target was constructed to co-move with BTC (beta ~0.6) -> mean corr > 0.
    assert out["rel_corr_btc_120"].iloc[200:].mean() > 0.2
    assert out["rel_beta_btc_120"].iloc[200:].mean() > 0.2


def test_rank_donors_picks_most_correlated_top_k():
    rng = np.random.RandomState(7)
    n = 500
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    tgt = pd.Series(rng.randn(n) * 0.01, index=idx)
    cands = {
        "HIGH_USDT": 0.9 * tgt + pd.Series(rng.randn(n) * 0.002, index=idx),   # ~0.97
        "MED_USDT": 0.5 * tgt + pd.Series(rng.randn(n) * 0.01, index=idx),     # ~0.6
        "LOW_USDT": 0.1 * tgt + pd.Series(rng.randn(n) * 0.02, index=idx),     # ~0.1 (below thr)
        "NOISE_USDT": pd.Series(rng.randn(n) * 0.01, index=idx),               # ~0
    }
    picked = rank_donors_by_correlation(tgt, cands, k=3, min_corr=0.3)
    assert picked[:2] == ["HIGH_USDT", "MED_USDT"]   # ranked by corr desc
    assert "LOW_USDT" not in picked and "NOISE_USDT" not in picked  # below threshold


def test_rank_donors_empty_when_none_clear_threshold():
    idx = pd.date_range("2024-01-01", periods=200, freq="15min")
    tgt = pd.Series(np.random.RandomState(1).randn(200) * 0.01, index=idx)
    cands = {"X_USDT": pd.Series(np.random.RandomState(2).randn(200) * 0.01, index=idx)}
    assert rank_donors_by_correlation(tgt, cands, k=3, min_corr=0.5) == []


def test_is_causal():
    tgt, btc, basket = _rets()
    full = compute_cross_relation_features(tgt, btc, basket)
    pre = compute_cross_relation_features(tgt.iloc[:300], btc.iloc[:300], basket.iloc[:300])
    for c in _COLS:
        assert np.allclose(full[c].values[:300], pre[c].values, equal_nan=True), c
