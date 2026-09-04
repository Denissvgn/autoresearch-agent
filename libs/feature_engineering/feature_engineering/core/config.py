"""Feature configuration for technical indicators."""

from typing import List, Optional
from pydantic import BaseModel, Field

ADAPTIVE_LEVEL_FEATURE_VERSION = "adaptive_levels.v1"
SPECTRAL_FEATURE_VERSION = "spectral_features.v1"
VDMC_FEATURE_VERSION = "vdmc_core_wave.v1"
# Stationarity pass: replaces the raw price/volume-scale columns
# (vwap levels, kyle_lambda, amihud, macd_histogram, vdmc momentum/amplitude)
# with scale-free counterparts. Opt-in so existing schemas are unchanged.
STATIONARY_FEATURE_VERSION = "stationary_features.v1"
# Causal trailing window for the rolling z-scores of the microstructure
# columns (15 days of 15m bars). Part of the versioned feature semantics.
STATIONARY_Z_WINDOW = 1440
# Phase 4: cross-asset (BTC/ETH lead-lag) and derivatives (funding/OI)
# microstructure lanes. Both are opt-in (default disabled) so existing models
# and their feature schemas are unchanged until a model explicitly enables them.
CROSS_ASSET_FEATURE_VERSION = "cross_asset.v1"
DERIVATIVES_FEATURE_VERSION = "derivatives.v1"
DIRECTIONAL_CHANGE_FEATURE_VERSION = "directional_change.v1"
# Rolling-FFT spectral feature windows (short + long cycle structure). Fixed so
# the spectral column set / contract is deterministic.
SPECTRAL_FEATURE_WINDOWS = (32, 96)
# Number of scales in the Directional-Change feature ladder. Fixed so the feature
# column set (and contract) is deterministic; the multiplier VALUES are tunable but
# changing the COUNT is a version-bump concern.
DIRECTIONAL_CHANGE_N_SCALES = 5
SPECTRAL_FEATURE_EVIDENCE_REPORT = (
    "reports/direction-tuning/features/"
    "dpu-050_spectral_feature_evidence_gate_2026-04-26.md"
)
# DM-7: cross-asset BTC enhanced lane. Backlog
# (DIRECTION-MODEL-COMPOSITE-LIFT-BACKLOG-res_be66790e192e.md §P1/DM-7)
# called for a richer column set than the legacy ``cross_asset.v1`` lane
# (btc_return_{1,3,5,10}, btc_volatility_zscore_{20,60},
# btc_dominance_proxy_zscore_60). Ships as a NEW lane so the legacy lane
# stays untouched and old artifacts load unchanged.
CROSS_ASSET_BTC_ENHANCED_VERSION = "cross_asset_btc_enhanced.v1"
CROSS_ASSET_BTC_ENHANCED_EVIDENCE_REPORT = (
    "reports/direction-tuning/features/"
    "dpu-051_cross_asset_btc_enhanced_evidence_gate_2026-05-29.md"
)
# ML-OBS: ATR-normalized price-path lane (OHLCV-only). Stationary, bounded
# replacements for the raw OHLCV window in the RL `distilled` observation
# profile. Computed self-contained (fixed ATR/EMA params) so the shared lib and
# the trainer's legacy FeatureEngineer produce byte-identical columns. The
# column set + windows are fixed so the contract is deterministic.
PRICE_PATH_FEATURE_VERSION = "price_path_features.v1"
PRICE_PATH_RETURN_PERIODS = (1, 4, 16)
PRICE_PATH_ATR_PERIOD = 14
PRICE_PATH_EMA_WINDOW = 20
PRICE_PATH_DD_WINDOW = 20
PRICE_PATH_VOV_WINDOW = 20


def price_path_feature_columns() -> list[str]:
    """Deterministic ATR price-path column list (fixed order = obs contract)."""
    cols = [f"ret_{n}" for n in PRICE_PATH_RETURN_PERIODS]
    cols += [
        "atr_norm_range",
        "atr_pct",
        "close_vs_ema_atr",
        "dd_from_peak_atr",
        "vol_of_vol",
    ]
    return cols


class FeatureConfig(BaseModel):
    """Configuration for feature engineering.
    
    Defines which technical indicators to compute and their parameters.
    All configurations are deterministic and versioned for reproducibility.
    """
    
    # Moving averages
    sma_periods: List[int] = Field(
        default=[5, 10, 20, 50],
        description="Simple Moving Average periods"
    )
    ema_periods: List[int] = Field(
        default=[5, 10, 20, 50],
        description="Exponential Moving Average periods"
    )
    
    # RSI settings
    rsi_periods: List[int] = Field(
        default=[14, 21],
        description="Relative Strength Index periods"
    )
    
    # MACD settings
    macd_fast: int = Field(default=12, description="MACD fast EMA period")
    macd_slow: int = Field(default=26, description="MACD slow EMA period")
    macd_signal: int = Field(default=9, description="MACD signal line period")
    
    # Bollinger Bands
    bb_period: int = Field(default=20, description="Bollinger Bands period")
    bb_std: float = Field(default=2.0, description="Bollinger Bands standard deviations")
    
    # ATR settings
    atr_period: int = Field(default=14, description="Average True Range period")
    
    # Volume indicators
    volume_sma_periods: List[int] = Field(
        default=[10, 20],
        description="Volume Simple Moving Average periods"
    )
    
    # Price change features
    price_change_periods: List[int] = Field(
        default=[1, 3, 5, 10],
        description="Price change lookback periods"
    )
    
    # Volatility features
    volatility_periods: List[int] = Field(
        default=[10, 20],
        description="Historical volatility periods"
    )

    # Stationarity pass (opt-in). When enabled, the raw price/volume-scale
    # columns are NOT emitted and scale-free counterparts take their place:
    # vwap_{p} dropped (vwap_ratio_{p} already carries the signal),
    # kyle_lambda_{p}/amihud_illiq_{p} → causal rolling z-scores,
    # macd/macd_signal/macd_histogram → macd_histogram_pct (close-relative),
    # vdmc_momentum/vdmc_amplitude → close-relative _rel variants.
    # Non-stationary level features cannot generalize across price regimes
    # (2019 DOGE ≈ $0.002 vs 2026 ≈ $0.2) and are NaN-masked for pooled
    # donors — the scale-free forms keep the signal in both cases.
    stationary_features_enabled: bool = Field(
        default=False,
        description="Replace price/volume-scale columns with scale-free forms"
    )
    stationary_features_version: str = Field(
        default=STATIONARY_FEATURE_VERSION,
        description="Version identifier for the stationarity-pass semantics"
    )

    # Canonical VDMC wave-function lane. Disabled by default so the historical
    # v2 feature surface stays explicit; enable when serving models trained with
    # vdmc_core enrichment.
    vdmc_enabled: bool = Field(
        default=False,
        description="Enable canonical vdmc_core wave-function features"
    )
    vdmc_version: str = Field(
        default=VDMC_FEATURE_VERSION,
        description="Version identifier for canonical VDMC feature semantics"
    )
    vdmc_lookback_period: int = Field(
        default=120,
        ge=120,
        le=720,
        description="VDMC kernel smoothing lookback period"
    )
    vdmc_alpha: float = Field(
        default=1.2,
        description="VDMC trend coefficient in logistic transform"
    )
    vdmc_beta: float = Field(
        default=0.8,
        description="VDMC wave amplitude coefficient"
    )
    vdmc_kernel_sigma: int = Field(
        default=5,
        ge=3,
        le=21,
        description="VDMC gaussian_filter1d sigma parameter"
    )
    vdmc_smoothing_factor: float = Field(
        default=0.3,
        gt=0.0,
        le=1.0,
        description="VDMC exponential smoothing factor for short-history fallback"
    )
    vdmc_amplitude_scaling: float = Field(
        default=1.0,
        gt=0.0,
        le=5.0,
        description="VDMC wave amplitude scaling factor"
    )

    # Adaptive OHLCV support/resistance feature lane
    adaptive_levels_enabled: bool = Field(
        default=False,
        description="Enable adaptive OHLCV level support/resistance features"
    )
    adaptive_levels_version: str = Field(
        default=ADAPTIVE_LEVEL_FEATURE_VERSION,
        description="Version identifier for adaptive OHLCV level feature semantics"
    )

    # Hierarchical ATR-scaled Directional-Change feature lane (causal). OHLCV-only
    # (no external data), so train/serve parity is automatic once both run this lib
    # with the flag on — no feature-service fetch wiring needed. Opt-in; disabled by
    # default → no schema change. Fixed DIRECTIONAL_CHANGE_N_SCALES scales.
    directional_change_features_enabled: bool = Field(
        default=False,
        description="Enable causal multi-scale Directional-Change features"
    )
    directional_change_version: str = Field(
        default=DIRECTIONAL_CHANGE_FEATURE_VERSION,
        description="Version identifier for Directional-Change feature semantics"
    )
    directional_change_atr_mults: List[float] = Field(
        default_factory=lambda: [8.0, 4.0, 2.0, 1.0, 0.5],
        description="ATR-multiple ladder (coarse→fine) for DC features; "
        "length must equal DIRECTIONAL_CHANGE_N_SCALES"
    )
    directional_change_atr_period: int = Field(
        default=14,
        description="ATR period for the per-bar DC feature thresholds"
    )

    # Optional SEMPO-inspired spectral feature lane. This is a gate and schema
    # contract only; runtime spectral feature generation is intentionally not
    # enabled by default.
    spectral_features_enabled: bool = Field(
        default=False,
        description="Enable versioned spectral/FFT feature selection"
    )
    spectral_features_version: str = Field(
        default=SPECTRAL_FEATURE_VERSION,
        description="Version identifier for spectral/FFT feature semantics"
    )
    spectral_evidence_report_path: Optional[str] = Field(
        default=None,
        description="DPU-050 evidence report path required when spectral features are enabled"
    )

    # Phase 4: cross-asset lead-lag lane. Reads optional merged columns
    # (btc_close, eth_close, ...) supplied by the caller; degrades gracefully
    # (availability flag = 0) when they are absent. Opt-in.
    cross_asset_features_enabled: bool = Field(
        default=False,
        description="Enable cross-asset (BTC/ETH) lead-lag/correlation features"
    )
    cross_asset_features_version: str = Field(
        default=CROSS_ASSET_FEATURE_VERSION,
        description="Version identifier for cross-asset feature semantics"
    )
    # DM-7: cross-asset BTC enhanced lane (separate from cross_asset_features
    # above). Backlog-defined column set: btc_return_{1,3,5,10},
    # btc_volatility_zscore_{20,60}, btc_dominance_proxy_zscore_60,
    # btc_enhanced_available. Reads optional merged ``btc_close`` and
    # (for dominance proxy) ``eth_close``; degrades to zero-fill when
    # absent, matching the legacy cross_asset lane's parity discipline.
    cross_asset_btc_enhanced_enabled: bool = Field(
        default=False,
        description="DM-7: enable cross-asset BTC enhanced lane "
        "(returns / vol z-scores / dominance proxy)"
    )
    cross_asset_btc_enhanced_version: str = Field(
        default=CROSS_ASSET_BTC_ENHANCED_VERSION,
        description="Version identifier for cross-asset BTC enhanced lane"
    )
    cross_asset_btc_enhanced_evidence_report_path: Optional[str] = Field(
        default=None,
        description="DPU-051 evidence report path required when DM-7 lane is enabled"
    )
    # Phase 4: derivatives microstructure lane. Reads optional merged columns
    # (funding_rate, open_interest); degrades gracefully when absent. Opt-in.
    derivatives_features_enabled: bool = Field(
        default=False,
        description="Master toggle: enable BOTH derivatives sub-lanes (funding + "
        "open-interest). Equivalent to setting both sub-flags below."
    )
    # Sub-lane toggles so funding and open-interest can be enabled independently
    # (e.g. funding has multi-year history but binance OI is retained only ~30d).
    # A sub-lane is active when its own flag OR the derivatives master is set;
    # only an active sub-lane is fetched and contributes its feature columns.
    funding_features_enabled: bool = Field(
        default=False,
        description="Enable funding-rate features (derivatives sub-lane)"
    )
    open_interest_features_enabled: bool = Field(
        default=False,
        description="Enable open-interest features (derivatives sub-lane)"
    )
    derivatives_features_version: str = Field(
        default=DERIVATIVES_FEATURE_VERSION,
        description="Version identifier for derivatives feature semantics"
    )

    # ML-OBS: ATR-normalized price-path lane (OHLCV-only, opt-in). Stationary,
    # bounded path/volatility/drawdown context for the RL distilled observation.
    price_path_features_enabled: bool = Field(
        default=False,
        description="Enable the versioned ATR-normalized price-path lane "
        "(ret_*, atr_norm_range, atr_pct, close_vs_ema_atr, dd_from_peak_atr, "
        "vol_of_vol)"
    )
    price_path_features_version: str = Field(
        default=PRICE_PATH_FEATURE_VERSION,
        description="Version identifier for the ATR price-path lane"
    )

    class Config:
        """Pydantic configuration."""
        frozen = True  # Make config immutable for reproducibility
