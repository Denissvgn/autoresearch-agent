"""DM-7: cross-asset BTC enhanced feature lane.

Pins the same Phase-4 discipline as the legacy ``cross_asset_features``
lane but for the backlog-defined enhanced column set:

  * opt-in (default off → schema unchanged for legacy configs);
  * graceful degradation (BTC absent → zero-fill + availability=0);
  * schema-flag validator requires the DPU-051 evidence-report path;
  * version validator rejects mismatched version strings;
  * train==serve parity: two engine instances produce bit-identical
    columns on the same input.
"""
import numpy as np
import pandas as pd
import pytest

from feature_engineering.contracts import (
    build_feature_schema_flags,
    get_feature_contracts,
)
from feature_engineering.core.config import (
    CROSS_ASSET_BTC_ENHANCED_EVIDENCE_REPORT,
    CROSS_ASSET_BTC_ENHANCED_VERSION,
    FeatureConfig,
)
from feature_engineering.core.indicators import FeatureEngineer


# Exact backlog-defined column set + parity flag.
BTC_ENHANCED_COLS = {
    "btc_return_1", "btc_return_3", "btc_return_5", "btc_return_10",
    "btc_volatility_zscore_20", "btc_volatility_zscore_60",
    "btc_dominance_proxy_zscore_60",
    "btc_enhanced_available",
}


def _ohlcv(n: int = 240, *, with_btc: bool = False) -> pd.DataFrame:
    """Synthetic 15-min OHLCV. ``with_btc`` adds a ``btc_close`` column the
    way ``merge_external_series`` would for a training run with BTC bars
    actually fetched."""
    rng = np.random.default_rng(0)
    idx = pd.date_range("2026-01-01", periods=n, freq="15min")
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame({
        "open": close + rng.normal(0, 0.2, n),
        "high": close + np.abs(rng.normal(0, 0.5, n)),
        "low": close - np.abs(rng.normal(0, 0.5, n)),
        "close": close,
        "volume": rng.uniform(1000, 5000, n),
    }, index=idx)
    if with_btc:
        df["btc_close"] = 30000 + np.cumsum(rng.normal(0, 50, n))
    return df


def _cols(cfg: FeatureConfig, df: pd.DataFrame):
    out = FeatureEngineer(cfg).calculate_all_features(df)
    return set(out.columns), out


# --------------------------------------------------------------------------- #
# Opt-in gating.
# --------------------------------------------------------------------------- #
def test_btc_enhanced_lane_disabled_adds_no_columns() -> None:
    """Default config = lane off → schema is unchanged for legacy configs."""
    cols, _ = _cols(FeatureConfig(), _ohlcv(with_btc=True))
    assert not (BTC_ENHANCED_COLS & cols)


def test_btc_enhanced_lane_disabled_by_default_in_config() -> None:
    cfg = FeatureConfig()
    assert cfg.cross_asset_btc_enhanced_enabled is False
    assert cfg.cross_asset_btc_enhanced_version == CROSS_ASSET_BTC_ENHANCED_VERSION


# --------------------------------------------------------------------------- #
# Enabled + BTC present: backlog-defined columns appear, bounded, no NaN.
# --------------------------------------------------------------------------- #
def test_btc_enhanced_lane_enabled_with_btc_close_emits_expected_columns() -> None:
    cfg = FeatureConfig(cross_asset_btc_enhanced_enabled=True)
    cols, out = _cols(cfg, _ohlcv(with_btc=True))
    # Every backlog column present.
    assert BTC_ENHANCED_COLS <= cols
    # No NaN on the BTC-enhanced columns (the lane handles warmup via fillna).
    btc_cols = sorted(BTC_ENHANCED_COLS)
    assert not out[btc_cols].isna().any().any()
    # Availability flag is 1 when BTC was present.
    assert (out["btc_enhanced_available"] == 1.0).all()
    # Z-scores should be finite (no inf bleed-through from a zero
    # rolling std on a synthetic series).
    for c in [
        "btc_volatility_zscore_20",
        "btc_volatility_zscore_60",
        "btc_dominance_proxy_zscore_60",
    ]:
        assert np.isfinite(out[c]).all(), c


# --------------------------------------------------------------------------- #
# Enabled + BTC absent: same column set, zero-filled, availability = 0.
# --------------------------------------------------------------------------- #
def test_btc_enhanced_lane_enabled_without_btc_is_zero_filled() -> None:
    """Parity contract: schema MUST be identical with or without BTC data.
    Mirrors the legacy ``cross_asset_features`` discipline so a training
    run on a window where data-ingest hasn't backfilled BTC bars doesn't
    silently drop columns the serving model expects."""
    cfg = FeatureConfig(cross_asset_btc_enhanced_enabled=True)
    cols, out = _cols(cfg, _ohlcv(with_btc=False))
    # Same columns.
    assert BTC_ENHANCED_COLS <= cols
    # All zero.
    for c in sorted(BTC_ENHANCED_COLS - {"btc_enhanced_available"}):
        assert (out[c] == 0.0).all(), c
    # Availability flagged.
    assert (out["btc_enhanced_available"] == 0.0).all()
    # No NaN.
    assert not out[sorted(BTC_ENHANCED_COLS)].isna().any().any()


# --------------------------------------------------------------------------- #
# Schema-flag validator: version + evidence-path checks.
# --------------------------------------------------------------------------- #
def test_btc_enhanced_schema_flag_includes_version_and_evidence_path() -> None:
    cfg = FeatureConfig(
        cross_asset_btc_enhanced_enabled=True,
        cross_asset_btc_enhanced_evidence_report_path=CROSS_ASSET_BTC_ENHANCED_EVIDENCE_REPORT,
    )
    flags = build_feature_schema_flags(
        cfg, selected_feature_names=sorted(BTC_ENHANCED_COLS),
    )
    assert "cross_asset_btc_enhanced" in flags
    entry = flags["cross_asset_btc_enhanced"]
    assert entry["enabled"] is True
    assert entry["version"] == CROSS_ASSET_BTC_ENHANCED_VERSION
    assert entry["evidence_report_path"] == CROSS_ASSET_BTC_ENHANCED_EVIDENCE_REPORT
    assert set(entry["selected_feature_names"]) == BTC_ENHANCED_COLS


def test_btc_enhanced_evidence_path_validator_rejects_missing_path() -> None:
    """A model enabling the lane without naming the gating report must
    fail fast — same discipline as the spectral evidence gate."""
    cfg = FeatureConfig(cross_asset_btc_enhanced_enabled=True)
    # No evidence path supplied — validator raises.
    with pytest.raises(ValueError, match="cross_asset_btc_enhanced_evidence_report_path"):
        build_feature_schema_flags(cfg)


def test_btc_enhanced_evidence_path_validator_rejects_wrong_path() -> None:
    cfg = FeatureConfig(
        cross_asset_btc_enhanced_enabled=True,
        cross_asset_btc_enhanced_evidence_report_path="reports/wrong/path.md",
    )
    with pytest.raises(ValueError, match="DPU-051 evidence gate report"):
        build_feature_schema_flags(cfg)


def test_btc_enhanced_version_validator_rejects_mismatch() -> None:
    cfg = FeatureConfig(
        cross_asset_btc_enhanced_enabled=True,
        cross_asset_btc_enhanced_version="cross_asset_btc_enhanced.v2",
        cross_asset_btc_enhanced_evidence_report_path=CROSS_ASSET_BTC_ENHANCED_EVIDENCE_REPORT,
    )
    with pytest.raises(ValueError, match="cross_asset_btc_enhanced_version"):
        build_feature_schema_flags(cfg)


# --------------------------------------------------------------------------- #
# Contracts include the lane's columns when enabled, exclude when disabled.
# --------------------------------------------------------------------------- #
def test_btc_enhanced_contracts_included_when_lane_enabled() -> None:
    cfg = FeatureConfig(cross_asset_btc_enhanced_enabled=True)
    contracts = get_feature_contracts(cfg)
    for col in BTC_ENHANCED_COLS:
        assert col in contracts, col


def test_btc_enhanced_contracts_excluded_when_lane_disabled() -> None:
    contracts = get_feature_contracts(FeatureConfig())
    for col in BTC_ENHANCED_COLS:
        assert col not in contracts, col


# --------------------------------------------------------------------------- #
# Train==serve parity: two engine instances → bit-identical columns.
# --------------------------------------------------------------------------- #
def test_btc_enhanced_two_engine_parity() -> None:
    cfg = FeatureConfig(cross_asset_btc_enhanced_enabled=True)
    df = _ohlcv(with_btc=True)
    a = FeatureEngineer(cfg).calculate_all_features(df)
    b = FeatureEngineer(cfg).calculate_all_features(df)
    cols = sorted(BTC_ENHANCED_COLS)
    pd.testing.assert_frame_equal(a[cols], b[cols])


def test_btc_enhanced_independent_of_legacy_cross_asset_lane() -> None:
    """Both lanes can be enabled together; columns don't collide and the
    schema-flag bucket names stay distinct."""
    cfg = FeatureConfig(
        cross_asset_features_enabled=True,
        cross_asset_btc_enhanced_enabled=True,
        cross_asset_btc_enhanced_evidence_report_path=CROSS_ASSET_BTC_ENHANCED_EVIDENCE_REPORT,
    )
    cols, _ = _cols(cfg, _ohlcv(with_btc=True))
    # Both lanes' columns present.
    assert BTC_ENHANCED_COLS <= cols
    assert "btc_ret_lag1" in cols  # legacy lane's column
    # No overlap in column names.
    legacy_cols = {"btc_ret_lag1", "btc_rel_strength", "btc_corr_24", "btc_corr_96"}
    assert not (legacy_cols & BTC_ENHANCED_COLS)
    # Schema-flag buckets are distinct.
    flags = build_feature_schema_flags(cfg, selected_feature_names=sorted(cols))
    assert "cross_asset_btc_enhanced" in flags
    # (Legacy ``cross_asset_features`` lane doesn't register a schema-flag
    # bucket per the pre-DM-7 design — only the enhanced lane does.)
