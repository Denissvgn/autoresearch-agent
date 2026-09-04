"""Feature contracts — schema, semantics, constraints, and freshness SLAs.

This module enforces the data contract defined in FEATURES-1.md §6.
Every feature column produced by ``FeatureEngineer.calculate_all_features()``
has an entry in ``FEATURE_CONTRACTS`` that declares:

*  **type** – expected dtype family (``float``, ``int``, ``binary``)
*  **nullable** – whether NaN/None is ever acceptable after cleaning
*  **range** – (min, max) hard bounds; rows outside are constraint failures
*  **semantics** – human description (used in DATA-1.md lineage)
*  **group** – feature group for staged ablation

The ``validate_feature_frame()`` function applies all checks and returns
a structured report.  Callers can choose ``mode="warn"`` (log only) or
``mode="enforce"`` (raise on first violation).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .core.config import (
    ADAPTIVE_LEVEL_FEATURE_VERSION,
    CROSS_ASSET_BTC_ENHANCED_EVIDENCE_REPORT,
    CROSS_ASSET_BTC_ENHANCED_VERSION,
    DIRECTIONAL_CHANGE_FEATURE_VERSION,
    DIRECTIONAL_CHANGE_N_SCALES,
    SPECTRAL_FEATURE_EVIDENCE_REPORT,
    SPECTRAL_FEATURE_VERSION,
    SPECTRAL_FEATURE_WINDOWS,
    VDMC_FEATURE_VERSION,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Contract definition
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FeatureContract:
    """Immutable contract for a single feature column."""

    name: str
    dtype: str = "float"  # float | int | binary
    nullable: bool = False
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    semantics: str = ""
    group: str = "unknown"


# ---------------------------------------------------------------------------
# Registry — one entry per column output by FeatureEngineer v2.0
# ---------------------------------------------------------------------------
def _build_contracts() -> Dict[str, FeatureContract]:
    """Build the canonical feature contract registry."""
    contracts: Dict[str, FeatureContract] = {}

    def _add(name: str, **kw):
        contracts[name] = FeatureContract(name=name, **kw)

    # --- OHLCV pass-through (kept for downstream convenience) ---------------
    for col in ("open", "high", "low", "close", "volume"):
        _add(col, range_min=0, semantics=f"Raw {col} price/volume", group="raw")

    # --- Basic features (group=basic) ---------------------------------------
    for p in (5, 10, 20, 50):
        _add(f"sma_{p}", range_min=0, semantics=f"{p}-period SMA", group="ma")
        _add(f"ema_{p}", range_min=0, semantics=f"{p}-period EMA", group="ma")
        _add(
            f"close_sma_{p}_ratio",
            range_min=0,
            range_max=5.0,
            semantics=f"close / SMA({p})",
            group="ma",
        )
        _add(
            f"close_ema_{p}_ratio",
            range_min=0,
            range_max=5.0,
            semantics=f"close / EMA({p})",
            group="ma",
        )

    # --- RSI -----------------------------------------------------------------
    for p in (14, 21):
        _add(f"rsi_{p}", range_min=0, range_max=100, semantics=f"RSI({p})", group="momentum")
        _add(f"rsi_{p}_overbought", dtype="binary", range_min=0, range_max=1, semantics=f"RSI({p})>70", group="momentum")
        _add(f"rsi_{p}_oversold", dtype="binary", range_min=0, range_max=1, semantics=f"RSI({p})<30", group="momentum")

    # --- MACD ----------------------------------------------------------------
    _add("macd", semantics="MACD line (fast EMA − slow EMA)", group="momentum")
    _add("macd_signal", semantics="MACD signal", group="momentum")
    _add("macd_histogram", semantics="MACD histogram", group="momentum")
    _add("macd_bullish", dtype="binary", range_min=0, range_max=1, semantics="MACD > signal", group="momentum")

    # --- Bollinger Bands -----------------------------------------------------
    _add("bb_upper", range_min=0, semantics="Upper BB(20,2)", group="volatility")
    _add("bb_middle", range_min=0, semantics="Middle BB(20)", group="volatility")
    _add("bb_lower", range_min=0, semantics="Lower BB(20,2)", group="volatility")
    _add("bb_width", range_min=0, semantics="BB width", group="volatility")
    _add("bb_position", range_min=-5, range_max=5, semantics="BB %B", group="volatility")

    # --- ATR -----------------------------------------------------------------
    _add("atr", range_min=0, semantics="ATR(14)", group="volatility")
    _add("atr_ratio", range_min=0, semantics="ATR / close — normalised ATR", group="volatility")

    # --- Price structure -----------------------------------------------------
    _add("typical_price", range_min=0, semantics="(high+low+close)/3", group="basic")
    _add("high_low_range", range_min=0, semantics="high − low", group="basic")
    _add("open_close_range", range_min=0, semantics="|close − open|", group="basic")
    _add("body_range_ratio", range_min=0, semantics="|close-open|/(high-low)", group="basic")

    # --- Volume features -----------------------------------------------------
    for p in (10, 20):
        _add(f"volume_sma_{p}", range_min=0, semantics=f"Volume SMA({p})", group="volume")
        _add(
            f"volume_ratio_{p}",
            range_min=0,
            range_max=100,
            semantics=f"Volume / SMA-vol({p})",
            group="volume",
        )
    _add("obv", semantics="On-balance volume", group="volume")

    # --- Returns / price change -----------------------------------------------
    for p in (1, 3, 5, 10):
        _add(f"return_{p}", semantics=f"{p}-bar return", group="returns")
        _add(f"log_return_{p}", semantics=f"{p}-bar log return", group="returns")

    # --- Price position -------------------------------------------------------
    for p in (10, 20):
        _add(f"price_position_{p}", range_min=0, range_max=1, semantics=f"Close position in {p}-bar range", group="basic")

    # --- Volatility (realized) -----------------------------------------------
    for p in (10, 20):
        _add(f"volatility_{p}", range_min=0, semantics=f"Rolling vol({p})", group="volatility")

    # --- Custom features (legacy group) --------------------------------------
    _add("price_up", dtype="binary", range_min=0, range_max=1, semantics="Close > prev close", group="custom")
    _add("price_down", dtype="binary", range_min=0, range_max=1, semantics="Close < prev close", group="custom")

    # --- Regime features (v2.0) ----------------------------------------------
    for fast, slow in [(5, 60), (10, 120), (20, 240)]:
        _add(
            f"return_zscore_{fast}_{slow}",
            range_min=-10,
            range_max=10,
            semantics=f"Mean-return z-score fast={fast} slow={slow}",
            group="regime",
        )
    for short, long in [(10, 60), (20, 120)]:
        _add(
            f"vol_ratio_{short}_{long}",
            range_min=0,
            range_max=50,
            semantics=f"Vol ratio short={short} long={long}",
            group="regime",
        )
    for p in (20, 60):
        _add(f"vwap_dist_{p}", range_min=-50, range_max=50, semantics=f"VWAP distance ({p})", group="regime")
    _add("consec_up", range_min=0, range_max=200, semantics="Consecutive up bars", group="regime")
    _add("consec_down", range_min=0, range_max=200, semantics="Consecutive down bars", group="regime")
    _add("upper_wick_ratio", range_min=-2, range_max=2, semantics="Upper wick / full range", group="regime")
    _add("lower_wick_ratio", range_min=-10, range_max=10, semantics="Lower wick / full range", group="regime")

    # --- Microstructure features (v2.0) --------------------------------------
    for lag in (5, 10, 20):
        _add(
            f"return_autocorr_{lag}",
            range_min=-1,
            range_max=1,
            semantics=f"Return autocorrelation lag={lag}",
            group="microstructure",
        )
    for w in (20, 60):
        _add(f"return_skew_{w}", range_min=-10, range_max=10, semantics=f"Return skewness w={w}", group="microstructure")
        _add(f"return_kurt_{w}", range_min=-7, range_max=100, semantics=f"Return kurtosis w={w}", group="microstructure")
    for w in (10, 20):
        _add(f"vw_return_{w}", semantics=f"Volume-weighted return w={w}", group="microstructure")
    for w in (10, 20):
        _add(f"breakout_high_dist_{w}", range_max=0, semantics=f"Close-to-high breakout dist ({w})", group="microstructure")
        _add(f"breakout_low_dist_{w}", range_min=0, semantics=f"Close-to-low breakout dist ({w})", group="microstructure")
    for w in (10, 20):
        _add(f"volume_spike_{w}", range_min=0, range_max=1.01, semantics=f"Volume / rolling-max-volume ({w})", group="microstructure")
    _add("intrabar_momentum", semantics="(close-open)/ATR", group="microstructure")
    for w in (10, 20):
        _add(f"range_expansion_{w}", range_min=0, semantics=f"Range / avg-range ({w})", group="microstructure")

    # --- Advanced microstructure features (v2.1, ML-39 parity) ---------------
    # 8. VWAP
    for p in (10, 20, 60):
        _add(f"vwap_{p}", range_min=0, semantics=f"VWAP({p})", group="adv_microstructure")
        _add(f"vwap_ratio_{p}", range_min=0, range_max=5.0, semantics=f"close / VWAP({p})", group="adv_microstructure")
    # 9. Spread proxy
    for p in (10, 20):
        _add(f"spread_proxy_{p}", range_min=0, semantics=f"Bid-ask spread proxy ({p})", group="adv_microstructure")
        _add(f"spread_proxy_ma_{p}", range_min=0, semantics=f"Spread proxy MA ({p})", group="adv_microstructure")
    # 10. Order flow imbalance
    for p in (10, 20):
        _add(f"order_flow_imbalance_{p}", range_min=-1, range_max=1, semantics=f"Order flow imbalance ({p})", group="adv_microstructure")
    # 11. Kyle's lambda
    for p in (10, 20):
        _add(f"kyle_lambda_{p}", range_min=0, semantics=f"Kyle's lambda proxy ({p})", group="adv_microstructure")
    # 12. Amihud illiquidity
    for p in (10, 20):
        _add(f"amihud_illiq_{p}", range_min=0, semantics=f"Amihud illiquidity ({p})", group="adv_microstructure")

    # --- Temporal features (v2.0) --------------------------------------------
    _add("hour_sin", range_min=-1, range_max=1, semantics="sin(2π·hour/24)", group="temporal")
    _add("hour_cos", range_min=-1, range_max=1, semantics="cos(2π·hour/24)", group="temporal")
    _add("dow_sin", range_min=-1, range_max=1, semantics="sin(2π·dow/7)", group="temporal")
    _add("dow_cos", range_min=-1, range_max=1, semantics="cos(2π·dow/7)", group="temporal")
    _add("is_weekend", dtype="binary", range_min=0, range_max=1, semantics="Saturday or Sunday", group="temporal")
    _add("session_asia", dtype="binary", range_min=0, range_max=1, semantics="UTC 00-08", group="temporal")
    _add("session_europe", dtype="binary", range_min=0, range_max=1, semantics="UTC 07-16", group="temporal")
    _add("session_us", dtype="binary", range_min=0, range_max=1, semantics="UTC 13-22", group="temporal")

    return contracts


FEATURE_CONTRACTS: Dict[str, FeatureContract] = _build_contracts()


def _build_adaptive_level_contracts() -> Dict[str, FeatureContract]:
    """Build contracts for opt-in adaptive support/resistance features."""
    return {
        "close_fib_bucket_24": FeatureContract(
            name="close_fib_bucket_24",
            dtype="int",
            range_min=0,
            range_max=6,
            semantics="Close location in causal 24-bar Fibonacci support/resistance grid",
            group="adaptive_levels",
        ),
        "close_fib_bucket_96": FeatureContract(
            name="close_fib_bucket_96",
            dtype="int",
            range_min=0,
            range_max=6,
            semantics="Close location in causal 96-bar Fibonacci support/resistance grid",
            group="adaptive_levels",
        ),
        "dist_to_support_24": FeatureContract(
            name="dist_to_support_24",
            range_min=0,
            range_max=1,
            semantics="Close distance above nearest 24-bar adaptive support, normalized by range",
            group="adaptive_levels",
        ),
        "dist_to_resistance_24": FeatureContract(
            name="dist_to_resistance_24",
            range_min=0,
            range_max=1,
            semantics="Close distance below nearest 24-bar adaptive resistance, normalized by range",
            group="adaptive_levels",
        ),
        "dist_to_support_96": FeatureContract(
            name="dist_to_support_96",
            range_min=0,
            range_max=1,
            semantics="Close distance above nearest 96-bar adaptive support, normalized by range",
            group="adaptive_levels",
        ),
        "dist_to_resistance_96": FeatureContract(
            name="dist_to_resistance_96",
            range_min=0,
            range_max=1,
            semantics="Close distance below nearest 96-bar adaptive resistance, normalized by range",
            group="adaptive_levels",
        ),
        "sma_local_to_long_ratio_24": FeatureContract(
            name="sma_local_to_long_ratio_24",
            range_min=0,
            range_max=5,
            semantics="Ratio of causal SMA(24) to SMA(96), clipped for stability",
            group="adaptive_levels",
        ),
        "range_local_to_long_ratio_24": FeatureContract(
            name="range_local_to_long_ratio_24",
            range_min=0,
            range_max=5,
            semantics="Ratio of causal 24-bar price range to 96-bar price range",
            group="adaptive_levels",
        ),
        "ohlc_bucket_spread_24": FeatureContract(
            name="ohlc_bucket_spread_24",
            dtype="int",
            range_min=0,
            range_max=6,
            semantics="Intrabar spread between OHLC adaptive buckets on the 24-bar grid",
            group="adaptive_levels",
        ),
        "close_bucket_delta_24": FeatureContract(
            name="close_bucket_delta_24",
            dtype="int",
            range_min=-6,
            range_max=6,
            semantics="One-bar change in close adaptive bucket on the 24-bar grid",
            group="adaptive_levels",
        ),
    }


ADAPTIVE_LEVEL_FEATURE_CONTRACTS: Dict[str, FeatureContract] = _build_adaptive_level_contracts()


def _build_vdmc_contracts() -> Dict[str, FeatureContract]:
    """Build optional canonical VDMC feature contracts."""
    contracts: Dict[str, FeatureContract] = {}

    def _add(name: str, **kw):
        contracts[name] = FeatureContract(name=name, **kw)

    _add(
        "vdmc_buy_proba",
        range_min=0,
        range_max=1,
        semantics="Canonical vdmc_core buy probability",
        group="vdmc",
    )
    _add(
        "vdmc_sell_proba",
        range_min=0,
        range_max=1,
        semantics="Canonical vdmc_core sell probability",
        group="vdmc",
    )
    _add("vdmc_momentum", semantics="Canonical vdmc_core momentum", group="vdmc")
    _add(
        "vdmc_amplitude",
        range_min=0,
        semantics="Canonical vdmc_core wave amplitude",
        group="vdmc",
    )
    _add(
        "vdmc_signal_strength",
        range_min=0,
        range_max=1,
        semantics="Absolute VDMC buy probability distance from neutral",
        group="vdmc",
    )
    for name, semantics in {
        "vdmc_trend_signal": "Binary VDMC trend signal",
        "vdmc_reversal_signal": "Binary VDMC reversal signal",
        "vdmc_neutral_signal": "Binary VDMC neutral signal",
        "vdmc_has_warning": "Binary VDMC warning indicator",
    }.items():
        _add(name, dtype="binary", range_min=0, range_max=1, semantics=semantics, group="vdmc")

    return contracts


VDMC_FEATURE_CONTRACTS: Dict[str, FeatureContract] = _build_vdmc_contracts()


def _build_cross_asset_contracts() -> Dict[str, FeatureContract]:
    """Phase 4 opt-in: cross-asset (BTC/ETH) lead-lag features."""
    contracts: Dict[str, FeatureContract] = {}
    for major in ("btc", "eth"):
        contracts[f"{major}_ret_lag1"] = FeatureContract(
            name=f"{major}_ret_lag1", dtype="float",
            semantics=f"{major.upper()} prior-bar return (lead-lag predictor)",
            group="cross_asset",
        )
        contracts[f"{major}_rel_strength"] = FeatureContract(
            name=f"{major}_rel_strength", dtype="float",
            semantics=f"Instrument return minus {major.upper()} return",
            group="cross_asset",
        )
        for w in (24, 96):
            contracts[f"{major}_corr_{w}"] = FeatureContract(
                name=f"{major}_corr_{w}", dtype="float",
                range_min=-1.0, range_max=1.0,
                semantics=f"Rolling {w}-bar return correlation with {major.upper()}",
                group="cross_asset",
            )
    contracts["cross_asset_available"] = FeatureContract(
        name="cross_asset_available", dtype="binary", range_min=0, range_max=1,
        semantics="1 when a cross-asset series was present (else zero-filled)",
        group="cross_asset",
    )
    return contracts


def _build_funding_contracts() -> Dict[str, FeatureContract]:
    """Phase 4 opt-in: funding-rate sub-lane of derivatives."""
    return {
        "funding_rate_level": FeatureContract(
            name="funding_rate_level", dtype="float",
            semantics="Funding rate at the bar", group="derivatives",
        ),
        "funding_rate_sign": FeatureContract(
            name="funding_rate_sign", dtype="float", range_min=-1.0, range_max=1.0,
            semantics="Sign of funding rate (-1/0/1)", group="derivatives",
        ),
        "funding_rate_zscore": FeatureContract(
            name="funding_rate_zscore", dtype="float",
            semantics="Funding rate z-score over a 48-bar window", group="derivatives",
        ),
        "funding_available": FeatureContract(
            name="funding_available", dtype="binary", range_min=0, range_max=1,
            semantics="1 when funding-rate data was present (else zero-filled)",
            group="derivatives",
        ),
    }


def _build_open_interest_contracts() -> Dict[str, FeatureContract]:
    """Phase 4 opt-in: open-interest sub-lane of derivatives."""
    return {
        "oi_pct_change": FeatureContract(
            name="oi_pct_change", dtype="float",
            semantics="Open-interest bar-over-bar pct change", group="derivatives",
        ),
        "oi_zscore": FeatureContract(
            name="oi_zscore", dtype="float",
            semantics="Open-interest z-score over a 96-bar window", group="derivatives",
        ),
        "oi_price_divergence": FeatureContract(
            name="oi_price_divergence", dtype="float", range_min=-1.0, range_max=1.0,
            semantics="Sign agreement between OI change and price return", group="derivatives",
        ),
        "open_interest_available": FeatureContract(
            name="open_interest_available", dtype="binary", range_min=0, range_max=1,
            semantics="1 when open-interest data was present (else zero-filled)",
            group="derivatives",
        ),
    }


CROSS_ASSET_FEATURE_CONTRACTS: Dict[str, FeatureContract] = _build_cross_asset_contracts()


def _build_cross_asset_btc_enhanced_contracts() -> Dict[str, FeatureContract]:
    """DM-7: enhanced BTC cross-asset features (separate from the v1 lane).

    Backlog-specified column set; all are stationary / z-scored so they
    sit alongside the existing model features without re-normalisation.
    """
    contracts: Dict[str, FeatureContract] = {}
    for lag in (1, 3, 5, 10):
        contracts[f"btc_return_{lag}"] = FeatureContract(
            name=f"btc_return_{lag}", dtype="float",
            semantics=(
                f"BTC pct-change over the last {lag} bars, lagged 1 bar "
                "to enforce causal availability"
            ),
            group="cross_asset_btc_enhanced",
        )
    for window in (20, 60):
        contracts[f"btc_volatility_zscore_{window}"] = FeatureContract(
            name=f"btc_volatility_zscore_{window}", dtype="float",
            semantics=(
                f"Z-score of BTC realised volatility over the last "
                f"{window} bars (vol normalised by its own rolling mean+std)"
            ),
            group="cross_asset_btc_enhanced",
        )
    contracts["btc_dominance_proxy_zscore_60"] = FeatureContract(
        name="btc_dominance_proxy_zscore_60", dtype="float",
        semantics=(
            "Z-score of log(DOGE_close / BTC_close) over a 60-bar window — "
            "proxy for relative-strength / BTC dominance shifts"
        ),
        group="cross_asset_btc_enhanced",
    )
    contracts["btc_enhanced_available"] = FeatureContract(
        name="btc_enhanced_available", dtype="binary",
        range_min=0, range_max=1,
        semantics="1 when btc_close was present (else zero-filled)",
        group="cross_asset_btc_enhanced",
    )
    return contracts


CROSS_ASSET_BTC_ENHANCED_FEATURE_CONTRACTS: Dict[str, FeatureContract] = (
    _build_cross_asset_btc_enhanced_contracts()
)
FUNDING_FEATURE_CONTRACTS: Dict[str, FeatureContract] = _build_funding_contracts()
OPEN_INTEREST_FEATURE_CONTRACTS: Dict[str, FeatureContract] = _build_open_interest_contracts()
# Back-compat aggregate (both sub-lanes); prefer the per-lane contracts above.
DERIVATIVES_FEATURE_CONTRACTS: Dict[str, FeatureContract] = {
    **FUNDING_FEATURE_CONTRACTS,
    **OPEN_INTEREST_FEATURE_CONTRACTS,
}


def _build_directional_change_contracts() -> Dict[str, FeatureContract]:
    """Causal multi-scale Directional-Change feature contracts (fixed scale count)."""
    out: Dict[str, FeatureContract] = {}
    for s in range(DIRECTIONAL_CHANGE_N_SCALES):
        out[f"dc_dir_s{s}"] = FeatureContract(
            name=f"dc_dir_s{s}",
            range_min=-1,
            range_max=1,
            semantics=f"Confirmed Directional-Change leg direction at ATR scale {s} (causal)",
            group="directional_change",
        )
        out[f"dc_overshoot_s{s}"] = FeatureContract(
            name=f"dc_overshoot_s{s}",
            range_min=-5,
            range_max=5,
            semantics=f"Signed fractional move since last confirmed extreme at scale {s}",
            group="directional_change",
        )
        out[f"dc_bars_since_s{s}"] = FeatureContract(
            name=f"dc_bars_since_s{s}",
            range_min=0,
            range_max=5000,
            semantics=f"Bars since last confirmed reversal at scale {s}",
            group="directional_change",
        )
    out["dc_active_scale"] = FeatureContract(
        name="dc_active_scale",
        range_min=0,
        range_max=DIRECTIONAL_CHANGE_N_SCALES,
        semantics="Count of DC scales currently in a confirmed leg (finer activity)",
        group="directional_change",
    )
    return out


DIRECTIONAL_CHANGE_FEATURE_CONTRACTS: Dict[str, FeatureContract] = (
    _build_directional_change_contracts()
)


def _build_spectral_contracts() -> Dict[str, FeatureContract] :
    """Causal rolling-FFT spectral feature contracts (fixed windows)."""
    out: Dict[str, FeatureContract] = {}
    for w in SPECTRAL_FEATURE_WINDOWS:
        out[f"spectral_entropy_{w}"] = FeatureContract(
            name=f"spectral_entropy_{w}", range_min=0, range_max=1,
            semantics=f"Normalized spectral entropy of {w}-bar return power spectrum (causal)",
            group="spectral",
        )
        out[f"spectral_centroid_{w}"] = FeatureContract(
            name=f"spectral_centroid_{w}", range_min=0, range_max=1,
            semantics=f"Normalized spectral centroid over {w}-bar window",
            group="spectral",
        )
        out[f"spectral_flatness_{w}"] = FeatureContract(
            name=f"spectral_flatness_{w}", range_min=0, range_max=1,
            semantics=f"Spectral flatness (tonality) over {w}-bar window",
            group="spectral",
        )
        for band in ("low", "mid", "high"):
            out[f"freq_band_energy_{band}_{w}"] = FeatureContract(
                name=f"freq_band_energy_{band}_{w}", range_min=0, range_max=1,
                semantics=f"Fraction of {w}-bar spectral power in the {band} band",
                group="spectral",
            )
        out[f"frequency_phase_sin_{w}"] = FeatureContract(
            name=f"frequency_phase_sin_{w}", range_min=-1, range_max=1,
            semantics=f"Sine of dominant-frequency phase over {w}-bar window",
            group="spectral",
        )
        out[f"frequency_phase_cos_{w}"] = FeatureContract(
            name=f"frequency_phase_cos_{w}", range_min=-1, range_max=1,
            semantics=f"Cosine of dominant-frequency phase over {w}-bar window",
            group="spectral",
        )
    return out


SPECTRAL_FEATURE_CONTRACTS: Dict[str, FeatureContract] = _build_spectral_contracts()


def get_feature_contracts(
    feature_config: Optional[Any] = None,
) -> Dict[str, FeatureContract]:
    """Return contracts active for the supplied feature configuration."""
    contracts = dict(FEATURE_CONTRACTS)
    if bool(_config_get(feature_config, "adaptive_levels_enabled", False)):
        contracts.update(ADAPTIVE_LEVEL_FEATURE_CONTRACTS)
    if bool(_config_get(feature_config, "vdmc_enabled", False)):
        contracts.update(VDMC_FEATURE_CONTRACTS)
    if bool(_config_get(feature_config, "cross_asset_features_enabled", False)):
        contracts.update(CROSS_ASSET_FEATURE_CONTRACTS)
    # DM-7: enhanced BTC lane — separate, additive contract set.
    if bool(_config_get(feature_config, "cross_asset_btc_enhanced_enabled", False)):
        contracts.update(CROSS_ASSET_BTC_ENHANCED_FEATURE_CONTRACTS)
    _deriv_master = bool(_config_get(feature_config, "derivatives_features_enabled", False))
    if _deriv_master or bool(_config_get(feature_config, "funding_features_enabled", False)):
        contracts.update(FUNDING_FEATURE_CONTRACTS)
    if _deriv_master or bool(_config_get(feature_config, "open_interest_features_enabled", False)):
        contracts.update(OPEN_INTEREST_FEATURE_CONTRACTS)
    if bool(_config_get(feature_config, "directional_change_features_enabled", False)):
        contracts.update(DIRECTIONAL_CHANGE_FEATURE_CONTRACTS)
    if bool(_config_get(feature_config, "spectral_features_enabled", False)):
        contracts.update(SPECTRAL_FEATURE_CONTRACTS)
    return contracts


# ---------------------------------------------------------------------------
# Schema hash context
# ---------------------------------------------------------------------------
def build_feature_schema_flags(
    feature_config: Optional[Any] = None,
    *,
    selected_feature_names: Optional[Sequence[str]] = None,
) -> Dict[str, dict]:
    """Build feature flag metadata for train/serve schema hashing.

    Default/off-mode returns an empty dict so legacy flag-off schema hashes do
    not change. When optional lanes such as adaptive levels or spectral
    features are enabled, their version, evidence metadata, and selected model
    feature names become part of the hash payload.
    """

    adaptive_enabled = bool(_config_get(feature_config, "adaptive_levels_enabled", False))
    spectral_enabled = bool(_config_get(feature_config, "spectral_features_enabled", False))
    vdmc_enabled = bool(_config_get(feature_config, "vdmc_enabled", False))
    dc_enabled = bool(
        _config_get(feature_config, "directional_change_features_enabled", False)
    )
    # DM-7: enhanced BTC lane participates in schema-flag accounting so the
    # versioned column set is part of the train/serve hash payload.
    btc_enhanced_enabled = bool(
        _config_get(feature_config, "cross_asset_btc_enhanced_enabled", False)
    )
    stationary_enabled = bool(
        _config_get(feature_config, "stationary_features_enabled", False)
    )
    if (
        not adaptive_enabled
        and not spectral_enabled
        and not vdmc_enabled
        and not dc_enabled
        and not btc_enhanced_enabled
        and not stationary_enabled
    ):
        return {}

    flags: Dict[str, dict] = {}
    if stationary_enabled:
        from .core.config import STATIONARY_FEATURE_VERSION

        version = str(
            _config_get(
                feature_config,
                "stationary_features_version",
                STATIONARY_FEATURE_VERSION,
            )
        )
        if version != STATIONARY_FEATURE_VERSION:
            raise ValueError(
                f"Unsupported stationary_features_version {version!r}; "
                f"expected {STATIONARY_FEATURE_VERSION!r}"
            )
        flags["stationary_features"] = {
            "enabled": True,
            "version": version,
            "selected_feature_names": list(selected_feature_names or ()),
        }
    if adaptive_enabled:
        version = str(
            _config_get(
                feature_config,
                "adaptive_levels_version",
                ADAPTIVE_LEVEL_FEATURE_VERSION,
            )
        )
        if version != ADAPTIVE_LEVEL_FEATURE_VERSION:
            raise ValueError(
                f"Unsupported adaptive_levels_version {version!r}; "
                f"expected {ADAPTIVE_LEVEL_FEATURE_VERSION!r}"
            )
        flags["adaptive_levels"] = {
            "enabled": True,
            "version": version,
            "selected_feature_names": list(selected_feature_names or ()),
        }

    if vdmc_enabled:
        version = str(_config_get(feature_config, "vdmc_version", VDMC_FEATURE_VERSION))
        if version != VDMC_FEATURE_VERSION:
            raise ValueError(
                f"Unsupported vdmc_version {version!r}; "
                f"expected {VDMC_FEATURE_VERSION!r}"
            )
        flags["vdmc"] = {
            "enabled": True,
            "version": version,
            "params": {
                "variant": "vdmc_core_wave",
                "lookback_period": int(_config_get(feature_config, "vdmc_lookback_period", 120)),
                "alpha": float(_config_get(feature_config, "vdmc_alpha", 1.2)),
                "beta": float(_config_get(feature_config, "vdmc_beta", 0.8)),
                "kernel_sigma": int(_config_get(feature_config, "vdmc_kernel_sigma", 5)),
                "smoothing_factor": float(
                    _config_get(feature_config, "vdmc_smoothing_factor", 0.3)
                ),
                "amplitude_scaling": float(
                    _config_get(feature_config, "vdmc_amplitude_scaling", 1.0)
                ),
            },
            "selected_feature_names": list(selected_feature_names or ()),
        }

    if spectral_enabled:
        version = str(
            _config_get(
                feature_config,
                "spectral_features_version",
                SPECTRAL_FEATURE_VERSION,
            )
        )
        evidence_path = str(
            _config_get(
                feature_config,
                "spectral_evidence_report_path",
                "",
            )
            or ""
        )
        if version != SPECTRAL_FEATURE_VERSION:
            raise ValueError(
                f"Unsupported spectral_features_version {version!r}; "
                f"expected {SPECTRAL_FEATURE_VERSION!r}"
            )
        if evidence_path != SPECTRAL_FEATURE_EVIDENCE_REPORT:
            raise ValueError(
                "spectral_evidence_report_path must reference the DPU-050 "
                f"evidence gate report {SPECTRAL_FEATURE_EVIDENCE_REPORT!r}"
            )
        flags["spectral_features"] = {
            "enabled": True,
            "version": version,
            "evidence_report_path": evidence_path,
            "selected_feature_names": list(selected_feature_names or ()),
        }

    if dc_enabled:
        version = str(
            _config_get(
                feature_config,
                "directional_change_version",
                DIRECTIONAL_CHANGE_FEATURE_VERSION,
            )
        )
        if version != DIRECTIONAL_CHANGE_FEATURE_VERSION:
            raise ValueError(
                f"Unsupported directional_change_version {version!r}; "
                f"expected {DIRECTIONAL_CHANGE_FEATURE_VERSION!r}"
            )
        flags["directional_change"] = {
            "enabled": True,
            "version": version,
            "params": {
                "atr_period": int(
                    _config_get(feature_config, "directional_change_atr_period", 14)
                ),
                "atr_mults": list(
                    _config_get(
                        feature_config,
                        "directional_change_atr_mults",
                        [8.0, 4.0, 2.0, 1.0, 0.5],
                    )
                    or []
                ),
            },
            "selected_feature_names": list(selected_feature_names or ()),
        }

    if btc_enhanced_enabled:
        # DM-7 evidence gate (DPU-051). Same shape as spectral_features —
        # version + evidence-path validators; rejects mis-matching paths
        # so a model accidentally enabling the lane without naming the
        # gating report fails fast in CI rather than silently shipping.
        version = str(
            _config_get(
                feature_config,
                "cross_asset_btc_enhanced_version",
                CROSS_ASSET_BTC_ENHANCED_VERSION,
            )
        )
        evidence_path = str(
            _config_get(
                feature_config,
                "cross_asset_btc_enhanced_evidence_report_path",
                "",
            )
            or ""
        )
        if version != CROSS_ASSET_BTC_ENHANCED_VERSION:
            raise ValueError(
                f"Unsupported cross_asset_btc_enhanced_version {version!r}; "
                f"expected {CROSS_ASSET_BTC_ENHANCED_VERSION!r}"
            )
        if evidence_path != CROSS_ASSET_BTC_ENHANCED_EVIDENCE_REPORT:
            raise ValueError(
                "cross_asset_btc_enhanced_evidence_report_path must reference "
                f"the DPU-051 evidence gate report "
                f"{CROSS_ASSET_BTC_ENHANCED_EVIDENCE_REPORT!r}"
            )
        flags["cross_asset_btc_enhanced"] = {
            "enabled": True,
            "version": version,
            "evidence_report_path": evidence_path,
            "selected_feature_names": list(selected_feature_names or ()),
        }

    return flags


def build_feature_schema_hash_payload(
    feature_names: Sequence[str],
    feature_dtypes: Optional[Mapping[str, str]] = None,
    *,
    feature_config: Optional[Any] = None,
    selected_feature_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Build the canonical feature schema hash payload."""

    ordered_names = list(feature_names)
    payload: Dict[str, Any] = {"feature_names": ordered_names}
    if feature_dtypes:
        payload["feature_dtypes"] = {
            name: feature_dtypes.get(name, "unknown") for name in ordered_names
        }

    flags = build_feature_schema_flags(
        feature_config,
        selected_feature_names=(
            selected_feature_names
            if selected_feature_names is not None
            else ordered_names
        ),
    )
    if flags:
        payload["feature_flags"] = flags
    return payload


def _config_get(feature_config: Optional[Any], key: str, default: Any) -> Any:
    if feature_config is None:
        return default
    if isinstance(feature_config, Mapping):
        return feature_config.get(key, default)
    return getattr(feature_config, key, default)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    """Structured output from ``validate_feature_frame``."""

    ok: bool = True
    missing_columns: List[str] = field(default_factory=list)
    extra_columns: List[str] = field(default_factory=list)
    null_violations: Dict[str, int] = field(default_factory=dict)
    range_violations: Dict[str, dict] = field(default_factory=dict)
    total_rows: int = 0

    def summary(self) -> str:
        parts = [f"rows={self.total_rows}"]
        if self.missing_columns:
            parts.append(f"missing_cols={len(self.missing_columns)}")
        if self.extra_columns:
            parts.append(f"extra_cols={len(self.extra_columns)}")
        if self.null_violations:
            parts.append(f"null_violations={sum(self.null_violations.values())}")
        if self.range_violations:
            parts.append(f"range_violations={len(self.range_violations)}")
        status = "PASS" if self.ok else "FAIL"
        return f"[{status}] " + ", ".join(parts)


def validate_feature_frame(
    df: pd.DataFrame,
    *,
    mode: str = "warn",
    contracts: Optional[Dict[str, FeatureContract]] = None,
    feature_config: Optional[Any] = None,
    ignore_extra: bool = True,
) -> ValidationResult:
    """Validate a feature DataFrame against the canonical contracts.

    Parameters
    ----------
    df : pd.DataFrame
        Feature frame produced by ``FeatureEngineer.calculate_all_features()``.
    mode : str
        ``"warn"`` — log violations but return normally.
        ``"enforce"`` — raise ``FeatureContractViolation`` on first violation.
    contracts : dict, optional
        Override the default ``FEATURE_CONTRACTS`` (useful for tests).
    feature_config : optional
        Feature configuration used to select opt-in contract families.
    ignore_extra : bool
        If True, extra columns in *df* that aren't in the contract are
        noted but not treated as violations.

    Returns
    -------
    ValidationResult
    """
    c = contracts if contracts is not None else get_feature_contracts(feature_config)
    result = ValidationResult(total_rows=len(df))

    # 1. Schema completeness -------------------------------------------------
    expected_cols = set(c.keys())
    actual_cols = set(df.columns)
    result.missing_columns = sorted(expected_cols - actual_cols)
    result.extra_columns = sorted(actual_cols - expected_cols)

    if result.missing_columns:
        result.ok = False
        _emit(mode, f"Missing contracted columns: {result.missing_columns}")

    # 2. Null checks ---------------------------------------------------------
    for col_name, contract in c.items():
        if col_name not in df.columns:
            continue
        if not contract.nullable:
            n_null = int(df[col_name].isna().sum())
            if n_null > 0:
                result.null_violations[col_name] = n_null
                result.ok = False
                _emit(mode, f"Column '{col_name}' has {n_null} nulls (contract says non-nullable)")

    # 3. Range checks --------------------------------------------------------
    for col_name, contract in c.items():
        if col_name not in df.columns:
            continue
        vals = df[col_name].dropna()
        if len(vals) == 0:
            continue

        violations: dict = {}
        if contract.range_min is not None:
            n_below = int((vals < contract.range_min).sum())
            if n_below > 0:
                violations["below_min"] = {
                    "count": n_below,
                    "actual_min": float(vals.min()),
                    "contract_min": contract.range_min,
                }
        if contract.range_max is not None:
            n_above = int((vals > contract.range_max).sum())
            if n_above > 0:
                violations["above_max"] = {
                    "count": n_above,
                    "actual_max": float(vals.max()),
                    "contract_max": contract.range_max,
                }
        if violations:
            result.range_violations[col_name] = violations
            result.ok = False
            _emit(mode, f"Range violation in '{col_name}': {violations}")

    return result


def _emit(mode: str, msg: str):
    if mode == "enforce":
        raise FeatureContractViolation(msg)
    logger.warning("Feature contract: %s", msg)


class FeatureContractViolation(Exception):
    """Raised when ``mode='enforce'`` and a contract check fails."""


# ---------------------------------------------------------------------------
# Drift detection helpers
# ---------------------------------------------------------------------------

def compute_psi(
    reference: pd.Series,
    current: pd.Series,
    n_bins: int = 10,
    eps: float = 1e-6,
) -> float:
    """Population Stability Index between two distributions.

    PSI < 0.1 ➜ stable, 0.1-0.25 ➜ moderate drift, >0.25 ➜ significant.
    """
    ref_vals = reference.dropna().values
    cur_vals = current.dropna().values
    if len(ref_vals) < n_bins or len(cur_vals) < n_bins:
        return 0.0

    breakpoints = np.percentile(ref_vals, np.linspace(0, 100, n_bins + 1))
    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf

    ref_counts = np.histogram(ref_vals, bins=breakpoints)[0].astype(float) + eps
    cur_counts = np.histogram(cur_vals, bins=breakpoints)[0].astype(float) + eps

    ref_pct = ref_counts / ref_counts.sum()
    cur_pct = cur_counts / cur_counts.sum()

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return psi


def compute_drift_report(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    psi_threshold: float = 0.25,
) -> Dict[str, dict]:
    """Compute per-feature PSI and flag drifted columns.

    Parameters
    ----------
    reference_df : training / baseline feature frame
    current_df   : live / recent feature frame
    psi_threshold: PSI value above which a feature is "drifted"

    Returns
    -------
    dict mapping feature name → {psi, drifted, ref_mean, cur_mean, ref_std, cur_std}
    """
    common = sorted(set(reference_df.columns) & set(current_df.columns))
    report: Dict[str, dict] = {}
    for col in common:
        ref = reference_df[col]
        cur = current_df[col]
        psi = compute_psi(ref, cur)
        report[col] = {
            "psi": round(psi, 6),
            "drifted": psi > psi_threshold,
            "ref_mean": round(float(ref.mean()), 6),
            "cur_mean": round(float(cur.mean()), 6),
            "ref_std": round(float(ref.std()), 6),
            "cur_std": round(float(cur.std()), 6),
        }
    return report
