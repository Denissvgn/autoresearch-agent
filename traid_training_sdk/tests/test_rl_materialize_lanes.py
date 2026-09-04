"""Phase 4: materialize_rl_dataset must preserve the RL distilled-observation
lib lanes (VDMC signals + ATR price-path + spectral) so they reach the trainer,
while still dropping unrelated columns. Mirrors the enrichment lane attachment.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from traid_training_sdk.data.rl import (
    PRICE_PATH_FEATURE_COLUMNS,
    SPECTRAL_FEATURE_PREFIXES,
    materialize_rl_dataset,
)


def _frame(n: int = 30) -> pd.DataFrame:
    rng = np.random.RandomState(0)
    close = 100.0 + np.cumsum(rng.randn(n) * 0.2)
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="15min"),
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.abs(rng.randn(n)) * 100,
            "direction_proba": np.full(n, 0.55),
            "volatility_proba": np.full(n, 0.45),
            "ensemble_score": np.full(n, 0.5),
            "ret": np.zeros(n),
            # lanes that must survive
            "vdmc_buy_proba": np.full(n, 0.5),
            "spectral_entropy_32": np.linspace(0, 1, n),
            "freq_band_energy_low_96": np.linspace(0, 1, n),
            # unrelated column that must be dropped
            "some_raw_indicator": np.linspace(0, 1, n),
        }
    )
    for c in PRICE_PATH_FEATURE_COLUMNS:
        df[c] = np.linspace(-0.1, 0.1, n)
    # canonical cross-relation lane + bounded vdmc (must also survive)
    df["rel_corr_btc_120"] = np.linspace(-0.5, 0.5, n)
    df["rel_beta_btc_120"] = np.linspace(-1.0, 1.0, n)
    df["vdmc_momentum_z"] = np.linspace(-1.0, 1.0, n)
    return df


def test_materialize_preserves_lib_lanes_and_drops_extras(tmp_path):
    stats: dict = {}
    out_path = materialize_rl_dataset(_frame(), path=tmp_path / "rl.parquet", stats=stats)
    cols = set(pd.read_parquet(out_path).columns)

    # All price-path + spectral + vdmc lane columns survive.
    for c in PRICE_PATH_FEATURE_COLUMNS:
        assert c in cols, f"price-path column {c} dropped by materialize"
    assert "spectral_entropy_32" in cols
    assert "freq_band_energy_low_96" in cols
    assert "vdmc_buy_proba" in cols
    # cross-relation lane + bounded vdmc survive too.
    assert "rel_corr_btc_120" in cols and "rel_beta_btc_120" in cols
    assert "vdmc_momentum_z" in cols
    # Unrelated raw indicator is dropped (whitelist behavior preserved).
    assert "some_raw_indicator" not in cols
    # Required base/proba still present.
    for c in ("open", "high", "low", "close", "volume", "direction_proba"):
        assert c in cols


def test_sdk_price_path_constant_matches_lib_contract():
    # Drift guard: the SDK literal must equal the shared-lib contract when the
    # lib is importable in this environment.
    try:
        from feature_engineering.core.config import price_path_feature_columns
    except Exception:  # pragma: no cover - lib not installed in this env
        pytest.skip("feature_engineering lib not importable")
    assert list(PRICE_PATH_FEATURE_COLUMNS) == list(price_path_feature_columns())


def test_spectral_prefix_constant_covers_lib_columns():
    try:
        from feature_engineering import SPECTRAL_FEATURE_CONTRACTS
    except Exception:  # pragma: no cover - lib not installed in this env
        pytest.skip("feature_engineering lib not importable")
    for col in SPECTRAL_FEATURE_CONTRACTS:
        assert str(col).startswith(SPECTRAL_FEATURE_PREFIXES), col
