"""Version management for feature engineering library."""

# Library version (semantic versioning)
LIBRARY_VERSION = "2.3.0"

# Feature spec schema version
FEATURE_SPEC_VERSION = "2.3"

# Version history
VERSION_HISTORY = {
    "2.3.0": {
        "date": "2026-05-03",
        "changes": [
            "Add optional canonical vdmc_core wave-function feature lane for strict "
            "train/serve parity",
            "Include VDMC feature metadata and parameters in feature spec hashes "
            "when vdmc_enabled is true",
        ],
        "breaking_changes": [
            "Feature spec hash changed because the library/spec version changed; "
            "models pinned to v2.2.0 should run with v2.2.0 serving or be retrained",
        ],
    },
    "2.2.0": {
        "date": "2026-04-01",
        "changes": [
            "Port 11 ML-25 Phase 2 features from legacy feature_engineering.py:",
            "  - Lagged volatility: volatility_10_lag1, volatility_20_lag1",
            "  - Lagged ranges: high_low_range_lag1/lag2/lag3",
            "  - Residualized features: atr_ratio_resid, bb_width_resid",
            "  - Volume-regime interactions: volume_spike_x_return_zscore, "
            "volume_ratio_10_x_volatility_10, volume_ratio_10_x_volatility_20",
            "Close final feature parity gap with legacy — 0 missing features",
        ],
        "breaking_changes": [
            "Feature spec hash changed — models trained on v2.1 features should be re-trained "
            "for full parity; v2.1 models still work (new features are additive)",
        ],
    },
    "2.1.0": {
        "date": "2026-03-21",
        "changes": [
            "Add advanced microstructure features (items 8-12): VWAP, spread proxy, "
            "order flow imbalance, Kyle's lambda, Amihud illiquidity (ML-39)",
            "Close 27-column parity gap vs legacy feature_engineering.py",
            "Add feature contracts for 16 new columns",
        ],
        "breaking_changes": [
            "Feature spec hash changed — models trained on v2.0 features should be re-trained "
            "for full parity; v2.0 models still work (new features are additive)",
        ],
    },
    "2.0.0": {
        "date": "2025-01-20",
        "changes": [
            "Add regime features (return z-scores, vol ratios, VWAP distance, wick ratios)",
            "Add microstructure features (autocorrelation, skew/kurtosis, volume spikes, breakouts)",
            "Add temporal features (cyclic hour/DOW encoding, session flags)",
            "Fix _clean_features: ffill-only (remove bfill to prevent future leakage)",
            "Full train/serve feature parity — 87 feature column output",
        ],
        "breaking_changes": [
            "Feature spec hash changed — existing models trained on v1.0 features require re-training",
            "_clean_features no longer bfills — leading warm-up rows now zero-filled",
        ],
    },
    "1.0.0": {
        "date": "2024-11-04",
        "changes": [
            "Initial release",
            "Extract feature computation from ensemble-trainer",
            "Add spec generation and hashing",
            "Support for SMA, EMA, RSI, MACD, Bollinger Bands, ATR, volume, price changes",
        ],
        "breaking_changes": [],
    }
}


def get_version_info() -> dict:
    """Get current version information."""
    return {
        "library_version": LIBRARY_VERSION,
        "feature_spec_version": FEATURE_SPEC_VERSION,
        "history": VERSION_HISTORY.get(LIBRARY_VERSION, {}),
    }
