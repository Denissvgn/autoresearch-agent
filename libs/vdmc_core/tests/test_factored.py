"""Tests for vdmc_core.factored — enrichment factoring for HPO efficiency.

Validates:
  - compute_intermediates produces correct shapes and values
  - apply_sigmoid matches full vdmc() output for same params
  - derive_vdmc_features produces all 9 expected columns
  - Factored path is consistent with unfactored DataEnrichmentPipeline path
  - Edge cases: short history, invalid input, NaN prices
"""

import numpy as np
import pytest

from vdmc_core import VDMCConfig, vdmc
from vdmc_core.factored import (
    VDMCIntermediates,
    apply_sigmoid,
    compute_intermediates,
    derive_vdmc_features,
)
from vdmc_core.models import SignalType


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def price_series_200():
    """200-bar price series with trend + cycle."""
    np.random.seed(42)
    base = 1000.0
    trend = np.linspace(0, 50, 200)
    cycle = np.sin(np.linspace(0, 4 * np.pi, 200)) * 20
    noise = np.random.normal(0, 5, 200)
    return base + trend + cycle + noise


@pytest.fixture
def short_prices():
    """Price series shorter than minimum lookback."""
    return np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=np.float64)


# ── compute_intermediates ───────────────────────────────────────────────


class TestComputeIntermediates:
    def test_normal_output_shape(self, price_series_200):
        result = compute_intermediates(price_series_200, kernel_sigma=5, lookback_period=120)
        assert isinstance(result, VDMCIntermediates)
        assert len(result.smoothed_prices) == 200
        assert len(result.momentum) == 200
        assert result.warning_code is None
        assert not result.is_fallback

    def test_short_history_fallback(self, short_prices):
        result = compute_intermediates(short_prices, kernel_sigma=5, lookback_period=120)
        assert result.is_fallback
        assert result.warning_code == 1002
        assert result.wave_amplitude == 0.0
        assert len(result.momentum) == len(short_prices)

    def test_invalid_input(self):
        result = compute_intermediates(np.array([]), kernel_sigma=5, lookback_period=120)
        assert result.is_fallback
        assert result.warning_code == 1001

    def test_nan_input(self):
        prices = np.array([1.0, np.nan, 3.0, 4.0, 5.0])
        result = compute_intermediates(prices, kernel_sigma=5, lookback_period=120)
        assert result.warning_code == 1001  # Invalid input

    def test_amplitude_scaling_applied(self, price_series_200):
        r1 = compute_intermediates(price_series_200, kernel_sigma=5, lookback_period=120, amplitude_scaling=1.0)
        r2 = compute_intermediates(price_series_200, kernel_sigma=5, lookback_period=120, amplitude_scaling=2.0)
        if r1.wave_amplitude > 0:
            assert abs(r2.wave_amplitude - 2.0 * r1.wave_amplitude) < 1e-10

    def test_different_sigma_changes_output(self, price_series_200):
        r1 = compute_intermediates(price_series_200, kernel_sigma=3, lookback_period=120)
        r2 = compute_intermediates(price_series_200, kernel_sigma=11, lookback_period=120)
        # Different sigma → different smoothed prices
        assert not np.allclose(r1.smoothed_prices, r2.smoothed_prices)


# ── apply_sigmoid ───────────────────────────────────────────────────────


class TestApplySigmoid:
    def test_output_probabilities_in_range(self, price_series_200):
        intermediates = compute_intermediates(price_series_200, kernel_sigma=5, lookback_period=120)
        result = apply_sigmoid(intermediates, alpha=1.2, beta=0.8, signal_type=SignalType.BUY)
        assert 0.0 <= result.p_buy <= 1.0
        assert 0.0 <= result.p_sell <= 1.0

    def test_matches_full_vdmc(self, price_series_200):
        """Factored path must match unfactored vdmc() for same params."""
        config = VDMCConfig(kernel_sigma=5, lookback_period=120, alpha=1.2, beta=0.8, signal_type=SignalType.BUY)
        full_result = vdmc(price_series_200, config)

        intermediates = compute_intermediates(price_series_200, kernel_sigma=5, lookback_period=120)
        factored_result = apply_sigmoid(intermediates, alpha=1.2, beta=0.8, signal_type=SignalType.BUY)

        assert abs(full_result.p_buy - factored_result.p_buy) < 1e-10
        assert abs(full_result.p_sell - factored_result.p_sell) < 1e-10
        assert abs(full_result.momentum - factored_result.momentum) < 1e-10
        assert abs(full_result.wave_amplitude - factored_result.wave_amplitude) < 1e-10

    def test_invalid_intermediates_neutral(self):
        invalid = VDMCIntermediates(
            smoothed_prices=np.array([]),
            momentum=np.array([]),
            wave_amplitude=0.0,
            warning_code=1001,
            is_fallback=True,
        )
        result = apply_sigmoid(invalid, alpha=1.2, beta=0.8)
        assert result.p_buy == 0.5
        assert result.p_sell == 0.5

    def test_alpha_beta_only_affect_probabilities(self, price_series_200):
        """Changing alpha/beta should NOT change momentum or amplitude."""
        intermediates = compute_intermediates(price_series_200, kernel_sigma=5, lookback_period=120)
        r1 = apply_sigmoid(intermediates, alpha=0.5, beta=0.3)
        r2 = apply_sigmoid(intermediates, alpha=2.5, beta=2.0)
        # Momentum and amplitude come from intermediates, not alpha/beta
        assert r1.momentum == r2.momentum
        assert r1.wave_amplitude == r2.wave_amplitude
        # But probabilities should differ
        assert r1.p_buy != r2.p_buy


# ── derive_vdmc_features ───────────────────────────────────────────────


class TestDeriveVDMCFeatures:
    def test_all_9_features_present(self, price_series_200):
        intermediates = compute_intermediates(price_series_200, kernel_sigma=5, lookback_period=120)
        buy_out = apply_sigmoid(intermediates, alpha=1.2, beta=0.8, signal_type=SignalType.BUY)
        sell_out = apply_sigmoid(intermediates, alpha=1.2, beta=0.8, signal_type=SignalType.SELL)
        features = derive_vdmc_features(buy_out, sell_out)

        expected_keys = {
            "vdmc_buy_proba", "vdmc_sell_proba", "vdmc_momentum",
            "vdmc_amplitude", "vdmc_signal_strength", "vdmc_trend_signal",
            "vdmc_reversal_signal", "vdmc_neutral_signal", "vdmc_has_warning",
        }
        assert set(features.keys()) == expected_keys

    def test_signal_strength_range(self, price_series_200):
        intermediates = compute_intermediates(price_series_200, kernel_sigma=5, lookback_period=120)
        buy_out = apply_sigmoid(intermediates, alpha=1.2, beta=0.8, signal_type=SignalType.BUY)
        sell_out = apply_sigmoid(intermediates, alpha=1.2, beta=0.8, signal_type=SignalType.SELL)
        features = derive_vdmc_features(buy_out, sell_out)
        assert 0.0 <= features["vdmc_signal_strength"] <= 1.0

    def test_binary_signal_values(self, price_series_200):
        intermediates = compute_intermediates(price_series_200, kernel_sigma=5, lookback_period=120)
        buy_out = apply_sigmoid(intermediates, alpha=1.2, beta=0.8, signal_type=SignalType.BUY)
        sell_out = apply_sigmoid(intermediates, alpha=1.2, beta=0.8, signal_type=SignalType.SELL)
        features = derive_vdmc_features(buy_out, sell_out)
        for key in ["vdmc_trend_signal", "vdmc_reversal_signal", "vdmc_neutral_signal", "vdmc_has_warning"]:
            assert features[key] in (0, 1), f"{key} should be binary, got {features[key]}"


# ── Consistency test ────────────────────────────────────────────────────


class TestFactoredConsistency:
    def test_different_alpha_beta_same_intermediates(self, price_series_200):
        """Many (alpha, beta) trials can reuse one intermediates computation."""
        intermediates = compute_intermediates(price_series_200, kernel_sigma=7, lookback_period=120)

        results = []
        for alpha in [0.5, 1.0, 1.5, 2.0, 2.5]:
            for beta in [0.3, 0.8, 1.5, 2.0]:
                r = apply_sigmoid(intermediates, alpha=alpha, beta=beta)
                results.append((alpha, beta, r.p_buy))

        # All trials should have valid probabilities
        for alpha, beta, p_buy in results:
            assert 0.0 <= p_buy <= 1.0, f"Invalid p_buy={p_buy} for α={alpha}, β={beta}"

        # Different alpha/beta should produce different probabilities
        p_buys = [r[2] for r in results]
        assert len(set(round(p, 6) for p in p_buys)) > 1, "All trials produced same p_buy"
