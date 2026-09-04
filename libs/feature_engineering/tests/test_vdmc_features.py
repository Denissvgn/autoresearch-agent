"""Canonical VDMC feature tests."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_VDMC_CORE = _PROJECT_ROOT / "libs" / "vdmc_core"
if str(_VDMC_CORE) not in sys.path:
    sys.path.insert(0, str(_VDMC_CORE))

from feature_engineering import FeatureConfig, FeatureEngineer
from feature_engineering.advanced.vdmc import (
    VDMC_FEATURE_COLUMNS,
    calculate_vdmc_indicators,
    canonical_vdmc_params,
    compute_vdmc_params_hash,
)
from feature_engineering.spec.generator import extract_feature_dtypes, generate_feature_spec
from feature_engineering.spec.hasher import compute_feature_spec_hash


def _ohlcv(rows: int = 150) -> pd.DataFrame:
    close = np.linspace(100.0, 112.0, rows) + np.sin(np.arange(rows) / 5.0)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=rows, freq="h"),
        "open": close - 0.1,
        "high": close + 0.4,
        "low": close - 0.5,
        "close": close,
        "volume": np.linspace(1000.0, 2000.0, rows),
    })


def test_vdmc_outputs_canonical_columns_and_warmup_defaults() -> None:
    features = calculate_vdmc_indicators(_ohlcv(), lookback_period=120)

    assert tuple(features) == VDMC_FEATURE_COLUMNS
    assert all(len(values) == 150 for values in features.values())
    assert np.allclose(features["vdmc_buy_proba"][:120], 0.5)
    assert np.allclose(features["vdmc_sell_proba"][:120], 0.5)
    assert np.allclose(features["vdmc_momentum"][:120], 0.0)
    assert np.all(features["vdmc_has_warning"][:120] == 1)
    assert np.any(features["vdmc_has_warning"][120:] == 0)


def test_feature_engineer_adds_vdmc_only_when_enabled() -> None:
    df = _ohlcv()

    disabled = FeatureEngineer(FeatureConfig()).calculate_all_features(df)
    enabled = FeatureEngineer(FeatureConfig(vdmc_enabled=True)).calculate_all_features(df)

    assert not any(col.startswith("vdmc_") for col in disabled.columns)
    assert all(col in enabled.columns for col in VDMC_FEATURE_COLUMNS)


def test_vdmc_params_hash_and_spec_hash_are_deterministic() -> None:
    config = FeatureConfig(vdmc_enabled=True, vdmc_alpha=1.4, vdmc_beta=0.6)
    df = FeatureEngineer(config).calculate_all_features(_ohlcv())
    feature_names = [
        col for col in df.columns
        if col not in {"timestamp", "open", "high", "low", "close", "volume"}
    ]

    params_hash = compute_vdmc_params_hash(canonical_vdmc_params(config))
    spec = generate_feature_spec(
        feature_names=feature_names,
        feature_dtypes=extract_feature_dtypes(df),
        config=config,
    )

    assert params_hash == compute_vdmc_params_hash(canonical_vdmc_params(config))
    assert params_hash is not None
    assert len(params_hash) == 64
    assert spec["feature_flags"]["vdmc"]["params"]["alpha"] == 1.4
    assert compute_feature_spec_hash(spec) == compute_feature_spec_hash(dict(spec))


def test_vdmc_params_hash_accepts_feature_and_trainer_key_styles() -> None:
    feature_style = {
        "vdmc_lookback_period": 240,
        "vdmc_alpha": 1.4,
        "vdmc_beta": 0.6,
        "vdmc_kernel_sigma": 7,
        "vdmc_smoothing_factor": 0.2,
        "vdmc_amplitude_scaling": 1.3,
    }
    trainer_style = {
        "lookback_period": 240,
        "signal_type": "sell",
        "alpha": 1.4,
        "beta": 0.6,
        "kernel_sigma": 7,
        "smoothing_factor": 0.2,
        "amplitude_scaling": 1.3,
    }

    feature_hash = compute_vdmc_params_hash(canonical_vdmc_params(feature_style))
    trainer_hash = compute_vdmc_params_hash(canonical_vdmc_params(trainer_style))

    assert feature_hash == trainer_hash
    assert len(feature_hash or "") == 64
