"""Unified feature selection for train/serve parity.

ML-25 P1: Single source of truth for feature column selection.
Both the training pipeline and inference service must use these
functions so that the same features (in the same order) are used
in both contexts.

Usage:
    from feature_engineering.builders.feature_selection import (
        select_direction_features,
        select_volatility_features,
    )
"""

import logging
from typing import Any, List, Mapping, Optional, Sequence

from ..core.config import (
    ADAPTIVE_LEVEL_FEATURE_VERSION,
    SPECTRAL_FEATURE_EVIDENCE_REPORT,
    SPECTRAL_FEATURE_VERSION,
)

logger = logging.getLogger(__name__)

# ── Stationarity filter ──────────────────────────────────────────────
# Raw price-level features (sma_*, ema_*, typical_price, bb_upper/lower/middle,
# atr, macd, macd_signal, obv) are excluded because their magnitude is
# non-stationary and creates train/serve skew.

# ── Construct-overlap exclusions (ML-11 C1) ──────────────────────────
# Features with direct mathematical overlap against the ATR-based volatility
# label.  Excluded from the volatility model only.
VOLATILITY_LABEL_OVERLAP_FEATURES = frozenset({
    "atr_ratio",   # ATR / close — direct transform of label numerator
    "bb_width",    # Bollinger width ∝ rolling std ≈ ATR
})

# ── Pattern groups ────────────────────────────────────────────────────
# Each group is a list of substrings matched against column names via
# ``any(x in col for x in patterns)``.

# Patterns shared between both direction and volatility models
_SHARED_PATTERNS: dict[str, list[str]] = {
    "movement": [
        "return_", "log_return_",
        "price_position_",
        "close_sma_", "close_ema_",
    ],
    "volume": [
        "volume_ratio_",
    ],
    "momentum": [
        "rsi_",
        "macd_histogram", "macd_bullish",
    ],
    "regime": [
        "return_zscore_",
        "vol_ratio_",
        "vwap_dist_",
        "consec_up", "consec_down",
        "upper_wick_ratio", "lower_wick_ratio",
    ],
    "microstructure": [
        "return_autocorr_",
        "return_skew_", "return_kurt_",
        "vw_return_",
        "breakout_high_dist_", "breakout_low_dist_",
        "volume_spike_",
        "intrabar_momentum",
        "range_expansion_",
    ],
    "advanced_microstructure": [
        "vwap_",
        "vwap_ratio_",
        "spread_proxy_",
        "spread_proxy_ma_",
        "order_flow_imbalance_",
        "kyle_lambda_",
        "amihud_illiq_",
    ],
    "temporal": [
        "hour_sin", "hour_cos",
        "dow_sin", "dow_cos",
        "is_weekend",
        "session_asia", "session_europe", "session_us",
    ],
}

# Direction-only patterns (not in volatility)
_DIRECTION_ONLY_PATTERNS: dict[str, list[str]] = {
    "price_ratio": [
        "body_range_ratio",
        "bb_width", "bb_position",
    ],
    "custom_binary": [
        "price_up", "price_down",
    ],
}

# Volatility-only patterns (not in direction)
_VOLATILITY_ONLY_PATTERNS: dict[str, list[str]] = {
    "volatility_indicators": [
        "atr_ratio",
        "bb_width", "bb_position",
        "volatility_",
        "body_range_ratio",
    ],
    "momentum_binary": [
        "price_up", "price_down",
    ],
}

_ADAPTIVE_LEVEL_PATTERNS: dict[str, list[str]] = {
    "adaptive_levels": [
        "fib_bucket_",
        "dist_to_support_",
        "dist_to_resistance_",
        "sma_local_to_long_ratio_",
        "range_local_to_long_ratio_",
        "ohlc_bucket_spread_",
        "close_bucket_delta_",
    ],
}

_SPECTRAL_FEATURE_PATTERNS: dict[str, list[str]] = {
    "spectral": [
        "spectral_",
        "fft_",
        "freq_band_",
        "frequency_energy_",
        "frequency_phase_",
        "sempo_",
    ],
}

# Phase 4 opt-in lanes. Patterns deliberately match only the DERIVED columns,
# never the raw merged inputs (btc_close, eth_close, funding_rate,
# open_interest), so those passthrough columns can never leak into the model.
_CROSS_ASSET_PATTERNS: dict[str, list[str]] = {
    "cross_asset": [
        "btc_ret_lag1", "eth_ret_lag1",
        "btc_rel_strength", "eth_rel_strength",
        "btc_corr_", "eth_corr_",
        "cross_asset_available",
    ],
}

_FUNDING_PATTERNS: dict[str, list[str]] = {
    "funding": [
        "funding_rate_level", "funding_rate_sign", "funding_rate_zscore",
        "funding_available",
    ],
}
_OPEN_INTEREST_PATTERNS: dict[str, list[str]] = {
    "open_interest": [
        "oi_pct_change", "oi_zscore", "oi_price_divergence",
        "open_interest_available",
    ],
}
_DIRECTIONAL_CHANGE_PATTERNS: dict[str, list[str]] = {
    "directional_change": [
        "dc_dir_s", "dc_overshoot_s", "dc_bars_since_s", "dc_active_scale",
    ],
}
# VDMC canonical wave-function features (developed in advanced/vdmc.py with
# contracts, but previously never selected by any model). Gated like the other
# opt-in lanes; matches only the derived vdmc_* columns.
_VDMC_PATTERNS: dict[str, list[str]] = {
    "vdmc": ["vdmc_"],
}


def select_adaptive_level_features(available_columns: Sequence[str]) -> List[str]:
    """Select adaptive level columns from a produced feature frame."""

    return sorted(set(_match_patterns(available_columns, _ADAPTIVE_LEVEL_PATTERNS)))


def select_spectral_features(available_columns: Sequence[str]) -> List[str]:
    """Select SEMPO-inspired spectral/FFT columns from a produced feature frame."""

    return sorted(set(_match_patterns(available_columns, _SPECTRAL_FEATURE_PATTERNS)))


def resolve_adaptive_level_feature_config(
    feature_config: Optional[Any] = None,
    *,
    adaptive_levels_enabled: Optional[bool] = None,
    adaptive_levels_version: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve adaptive level feature flag/version from config or overrides."""

    enabled = adaptive_levels_enabled
    if enabled is None:
        enabled = bool(_config_get(feature_config, "adaptive_levels_enabled", False))

    version = adaptive_levels_version
    if version is None:
        version = _config_get(
            feature_config,
            "adaptive_levels_version",
            ADAPTIVE_LEVEL_FEATURE_VERSION,
        )
    version = str(version)

    if enabled and version != ADAPTIVE_LEVEL_FEATURE_VERSION:
        raise ValueError(
            f"Unsupported adaptive_levels_version {version!r}; "
            f"expected {ADAPTIVE_LEVEL_FEATURE_VERSION!r}"
        )

    return {
        "enabled": bool(enabled),
        "version": version,
    }


def resolve_spectral_feature_config(
    feature_config: Optional[Any] = None,
    *,
    spectral_features_enabled: Optional[bool] = None,
    spectral_features_version: Optional[str] = None,
    spectral_evidence_report_path: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve the DPU-050 spectral feature evidence gate.

    Spectral columns can be selected only when the caller explicitly enables
    the lane, pins the supported version, and references the DPU-050 evidence
    report. This keeps FFT/SEMPO-inspired work opt-in and auditable.
    """

    enabled = spectral_features_enabled
    if enabled is None:
        enabled = bool(_config_get(feature_config, "spectral_features_enabled", False))

    version = spectral_features_version
    if version is None:
        version = _config_get(
            feature_config,
            "spectral_features_version",
            SPECTRAL_FEATURE_VERSION,
        )
    version = str(version)

    evidence_path = spectral_evidence_report_path
    if evidence_path is None:
        evidence_path = _config_get(
            feature_config,
            "spectral_evidence_report_path",
            None,
        )
    evidence_path = str(evidence_path or "")

    if enabled and version != SPECTRAL_FEATURE_VERSION:
        raise ValueError(
            f"Unsupported spectral_features_version {version!r}; "
            f"expected {SPECTRAL_FEATURE_VERSION!r}"
        )
    if enabled and evidence_path != SPECTRAL_FEATURE_EVIDENCE_REPORT:
        raise ValueError(
            "spectral_evidence_report_path must reference the DPU-050 evidence "
            f"gate report {SPECTRAL_FEATURE_EVIDENCE_REPORT!r}"
        )

    return {
        "enabled": bool(enabled),
        "version": version,
        "evidence_report_path": evidence_path,
    }


def _match_patterns(
    available_columns: Sequence[str],
    pattern_groups: dict[str, list[str]],
    exclude: frozenset[str] = frozenset(),
) -> List[str]:
    """Select columns matching any pattern in *pattern_groups*, minus *exclude*."""
    selected: list[str] = []
    for col in available_columns:
        if col in exclude:
            continue
        for patterns in pattern_groups.values():
            if any(p in col for p in patterns):
                selected.append(col)
                break  # avoid duplicates from overlapping groups
    return selected


def select_direction_features(
    available_columns: Sequence[str],
    feature_config: Optional[Any] = None,
    *,
    adaptive_levels_enabled: Optional[bool] = None,
    adaptive_levels_version: Optional[str] = None,
    spectral_features_enabled: Optional[bool] = None,
    spectral_features_version: Optional[str] = None,
    spectral_evidence_report_path: Optional[str] = None,
    cross_asset_features_enabled: Optional[bool] = None,
    derivatives_features_enabled: Optional[bool] = None,
    funding_features_enabled: Optional[bool] = None,
    open_interest_features_enabled: Optional[bool] = None,
    directional_change_features_enabled: Optional[bool] = None,
    vdmc_enabled: Optional[bool] = None,
) -> List[str]:
    """Select stationary features for the direction model.

    Args:
        available_columns: All column names produced by FeatureEngineer.

    Returns:
        Sorted, deduplicated list of selected feature column names.
    """
    adaptive_config = resolve_adaptive_level_feature_config(
        feature_config,
        adaptive_levels_enabled=adaptive_levels_enabled,
        adaptive_levels_version=adaptive_levels_version,
    )
    spectral_config = resolve_spectral_feature_config(
        feature_config,
        spectral_features_enabled=spectral_features_enabled,
        spectral_features_version=spectral_features_version,
        spectral_evidence_report_path=spectral_evidence_report_path,
    )
    # Phase 4 opt-in lanes — read the flag from explicit override or config.
    if cross_asset_features_enabled is None:
        cross_asset_features_enabled = bool(
            _config_get(feature_config, "cross_asset_features_enabled", False)
        )
    if derivatives_features_enabled is None:
        derivatives_features_enabled = bool(
            _config_get(feature_config, "derivatives_features_enabled", False)
        )
    if funding_features_enabled is None:
        funding_features_enabled = bool(
            _config_get(feature_config, "funding_features_enabled", False)
        )
    if open_interest_features_enabled is None:
        open_interest_features_enabled = bool(
            _config_get(feature_config, "open_interest_features_enabled", False)
        )
    # The derivatives master enables BOTH sub-lanes; each sub-flag enables its own.
    funding_on = bool(funding_features_enabled or derivatives_features_enabled)
    open_interest_on = bool(open_interest_features_enabled or derivatives_features_enabled)
    if directional_change_features_enabled is None:
        directional_change_features_enabled = bool(
            _config_get(feature_config, "directional_change_features_enabled", False)
        )
    if vdmc_enabled is None:
        vdmc_enabled = bool(_config_get(feature_config, "vdmc_enabled", False))
    merged = {**_SHARED_PATTERNS, **_DIRECTION_ONLY_PATTERNS}
    if adaptive_config["enabled"]:
        merged = {**merged, **_ADAPTIVE_LEVEL_PATTERNS}
    if spectral_config["enabled"]:
        merged = {**merged, **_SPECTRAL_FEATURE_PATTERNS}
    if cross_asset_features_enabled:
        merged = {**merged, **_CROSS_ASSET_PATTERNS}
    if funding_on:
        merged = {**merged, **_FUNDING_PATTERNS}
    if open_interest_on:
        merged = {**merged, **_OPEN_INTEREST_PATTERNS}
    if directional_change_features_enabled:
        merged = {**merged, **_DIRECTIONAL_CHANGE_PATTERNS}
    if vdmc_enabled:
        merged = {**merged, **_VDMC_PATTERNS}
    selected = _match_patterns(available_columns, merged)
    result = sorted(set(selected))
    logger.info(
        "Direction feature selection: %d / %d columns (adaptive_levels=%s, spectral=%s)",
        len(result),
        len(available_columns),
        adaptive_config["enabled"],
        spectral_config["enabled"],
    )
    return result


def select_volatility_features(
    available_columns: Sequence[str],
    feature_config: Optional[Any] = None,
    *,
    adaptive_levels_enabled: Optional[bool] = None,
    adaptive_levels_version: Optional[str] = None,
    spectral_features_enabled: Optional[bool] = None,
    spectral_features_version: Optional[str] = None,
    spectral_evidence_report_path: Optional[str] = None,
) -> List[str]:
    """Select stationary features for the volatility model.

    ML-11 C1: Excludes construct-overlap features (atr_ratio, bb_width).

    Args:
        available_columns: All column names produced by FeatureEngineer.

    Returns:
        Sorted, deduplicated list of selected feature column names.
    """
    adaptive_config = resolve_adaptive_level_feature_config(
        feature_config,
        adaptive_levels_enabled=adaptive_levels_enabled,
        adaptive_levels_version=adaptive_levels_version,
    )
    spectral_config = resolve_spectral_feature_config(
        feature_config,
        spectral_features_enabled=spectral_features_enabled,
        spectral_features_version=spectral_features_version,
        spectral_evidence_report_path=spectral_evidence_report_path,
    )
    merged = {**_SHARED_PATTERNS, **_VOLATILITY_ONLY_PATTERNS}
    if adaptive_config["enabled"]:
        merged = {**merged, **_ADAPTIVE_LEVEL_PATTERNS}
    if spectral_config["enabled"]:
        merged = {**merged, **_SPECTRAL_FEATURE_PATTERNS}
    selected = _match_patterns(
        available_columns, merged, exclude=VOLATILITY_LABEL_OVERLAP_FEATURES,
    )
    result = sorted(set(selected))
    logger.info(
        "Volatility feature selection: %d / %d columns "
        "(excluded %d overlap, adaptive_levels=%s, spectral=%s)",
        len(result),
        len(available_columns),
        len(VOLATILITY_LABEL_OVERLAP_FEATURES),
        adaptive_config["enabled"],
        spectral_config["enabled"],
    )
    return result


def _config_get(feature_config: Optional[Any], key: str, default: Any) -> Any:
    if feature_config is None:
        return default
    if isinstance(feature_config, Mapping):
        return feature_config.get(key, default)
    return getattr(feature_config, key, default)
