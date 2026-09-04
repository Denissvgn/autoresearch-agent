"""Spectral/FFT lane (new generator) + VDMC selection wiring + schema flags."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from feature_engineering import (
    SPECTRAL_FEATURE_CONTRACTS,
    FeatureConfig,
    FeatureEngineer,
    get_feature_contracts,
)
from feature_engineering.builders.feature_selection import select_direction_features
from feature_engineering.contracts import build_feature_schema_flags

_EVID = "reports/direction-tuning/features/dpu-050_spectral_feature_evidence_gate_2026-04-26.md"
_SPECTRAL_PREFIXES = ("spectral_", "freq_band_", "frequency_phase_")


def _ohlcv(n: int = 800, seed: int = 0) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    close = 100.0 + np.cumsum(rng.randn(n) * 0.5) + 5.0 * np.sin(np.arange(n) / 40.0)
    return pd.DataFrame({
        "open": close, "high": close + np.abs(rng.randn(n)) * 0.3,
        "low": close - np.abs(rng.randn(n)) * 0.3, "close": close,
        "volume": np.abs(rng.randn(n)) * 1e3,
    })


def _spectral_cols(frame) -> list[str]:
    return sorted(c for c in frame.columns if c.startswith(_SPECTRAL_PREFIXES))


# ---- spectral lane ----

def test_spectral_off_adds_no_columns():
    out = FeatureEngineer(FeatureConfig()).calculate_all_features(_ohlcv())
    assert _spectral_cols(out) == []


def test_spectral_on_matches_contract_and_bounded():
    cfg = FeatureConfig(spectral_features_enabled=True, spectral_evidence_report_path=_EVID)
    out = FeatureEngineer(cfg).calculate_all_features(_ohlcv())
    cols = _spectral_cols(out)
    assert cols == sorted(SPECTRAL_FEATURE_CONTRACTS.keys())
    assert not out[cols].isna().any().any()
    # entropy/centroid/flatness/band-energy ∈ [0,1]; phase sin/cos ∈ [-1,1]
    for c in cols:
        lo = -1.0 if "phase" in c else 0.0
        assert out[c].min() >= lo - 1e-9 and out[c].max() <= 1.0 + 1e-9


def test_spectral_is_causal_prefix_stable_and_deterministic():
    cfg = FeatureConfig(spectral_features_enabled=True, spectral_evidence_report_path=_EVID)
    df = _ohlcv()
    full = FeatureEngineer(cfg).calculate_all_features(df)
    pre = FeatureEngineer(cfg).calculate_all_features(df.iloc[:600])
    cols = _spectral_cols(full)
    for c in cols:
        assert np.allclose(full[c].values[:600], pre[c].values, equal_nan=True)
    again = FeatureEngineer(cfg).calculate_all_features(df)
    pd.testing.assert_frame_equal(full[cols], again[cols])


def test_spectral_two_engine_parity():
    cfg = FeatureConfig(spectral_features_enabled=True, spectral_evidence_report_path=_EVID)
    df = _ohlcv()
    a = FeatureEngineer(cfg).calculate_all_features(df)
    b = FeatureEngineer(cfg).calculate_all_features(df)
    cols = _spectral_cols(a)
    pd.testing.assert_frame_equal(a[cols], b[cols])


def test_spectral_contracts_and_selection_gated():
    on = FeatureConfig(spectral_features_enabled=True, spectral_evidence_report_path=_EVID)
    gc = get_feature_contracts(on)
    assert all(c in gc for c in SPECTRAL_FEATURE_CONTRACTS)
    assert not any(c in get_feature_contracts(FeatureConfig()) for c in SPECTRAL_FEATURE_CONTRACTS)
    out = FeatureEngineer(on).calculate_all_features(_ohlcv())
    sel_on = select_direction_features(list(out.columns), feature_config=on)
    sel_off = select_direction_features(list(out.columns), feature_config=FeatureConfig())
    assert any(c.startswith(_SPECTRAL_PREFIXES) for c in sel_on)
    assert not any(c.startswith(_SPECTRAL_PREFIXES) for c in sel_off)


def test_spectral_selected_for_volatility_when_enabled():
    # I5b: spectral is the one enrichment lane wired into volatility selection, so
    # enabling it in the volatility baseline actually feeds the magnitude model.
    from feature_engineering.builders.feature_selection import select_volatility_features

    on = FeatureConfig(spectral_features_enabled=True, spectral_evidence_report_path=_EVID)
    out = FeatureEngineer(on).calculate_all_features(_ohlcv())
    sel_on = select_volatility_features(list(out.columns), feature_config=on)
    sel_off = select_volatility_features(list(out.columns), feature_config=FeatureConfig())
    assert any(c.startswith(_SPECTRAL_PREFIXES) for c in sel_on)
    assert not any(c.startswith(_SPECTRAL_PREFIXES) for c in sel_off)


# ---- VDMC selection wiring (previously dormant) ----

def test_vdmc_selected_only_when_enabled():
    cfg = FeatureConfig(vdmc_enabled=True)
    out = FeatureEngineer(cfg).calculate_all_features(_ohlcv())
    sel_on = [c for c in select_direction_features(list(out.columns), feature_config=cfg) if c.startswith("vdmc_")]
    sel_off = [c for c in select_direction_features(list(out.columns), feature_config=FeatureConfig()) if c.startswith("vdmc_")]
    assert len(sel_on) >= 5  # the 9 vdmc_* features
    assert sel_off == []


# ---- schema flags (provenance/version) for the new lanes ----

def test_schema_flags_include_dc_and_spectral_and_vdmc():
    cfg = FeatureConfig(
        directional_change_features_enabled=True,
        vdmc_enabled=True,
        spectral_features_enabled=True,
        spectral_evidence_report_path=_EVID,
    )
    flags = build_feature_schema_flags(cfg, selected_feature_names=["dc_dir_s0"])
    assert flags["directional_change"]["enabled"] is True
    assert flags["vdmc"]["enabled"] is True
    assert flags["spectral_features"]["evidence_report_path"] == _EVID


def test_spectral_requires_evidence_path_when_enabled():
    # selection enforces the DPU-050 evidence gate
    out = FeatureEngineer(
        FeatureConfig(spectral_features_enabled=True, spectral_evidence_report_path=_EVID)
    ).calculate_all_features(_ohlcv())
    with pytest.raises(ValueError):
        select_direction_features(
            list(out.columns),
            feature_config=FeatureConfig(spectral_features_enabled=True),  # no evidence path
        )
