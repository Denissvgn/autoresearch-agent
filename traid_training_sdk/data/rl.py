from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, MutableMapping, Sequence

import numpy as np
import pandas as pd

from ..core.errors import ConfigurationError


@dataclass(frozen=True)
class RLDatasetStats:
    """Metadata describing a materialised RL dataset."""

    path: str
    rows: int
    columns: list[str]


_REQUIRED_BASE_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
_REQUIRED_PROBA_COLUMNS = ("direction_proba", "volatility_proba", "ensemble_score")

DIRECTION_PROBA_PROVENANCE_COLUMN = "direction_proba_provenance"
VOLATILITY_PROBA_PROVENANCE_COLUMN = "volatility_proba_provenance"
DIRECTION_OOF_AVAILABLE_COLUMN = "direction_oof_available"
VOLATILITY_OOF_AVAILABLE_COLUMN = "volatility_oof_available"

PROVENANCE_OOF = "oof"
PROVENANCE_HOLDOUT = "holdout"
PROVENANCE_SDK_PROXY = "sdk_proxy"
PROVENANCE_NEUTRAL_FALLBACK = "neutral_fallback"
PROVENANCE_MODEL_INFERENCE_FALLBACK = "model_inference_fallback"
PROVENANCE_LEGACY_INFERRED = "legacy_inferred"

HONEST_PROBA_PROVENANCE = frozenset({PROVENANCE_OOF, PROVENANCE_HOLDOUT})
UNSAFE_DIRECTION_PROBA_PROVENANCE = frozenset(
    {
        PROVENANCE_SDK_PROXY,
        PROVENANCE_NEUTRAL_FALLBACK,
        PROVENANCE_MODEL_INFERENCE_FALLBACK,
        PROVENANCE_LEGACY_INFERRED,
        "missing",
        "unknown",
    }
)

_PROVENANCE_COLUMNS = {
    "direction": DIRECTION_PROBA_PROVENANCE_COLUMN,
    "volatility": VOLATILITY_PROBA_PROVENANCE_COLUMN,
}
_OOF_AVAILABLE_COLUMNS = {
    "direction": DIRECTION_OOF_AVAILABLE_COLUMN,
    "volatility": VOLATILITY_OOF_AVAILABLE_COLUMN,
}

# RL distilled-observation lib lanes that materialize_rl_dataset must preserve
# when present (alongside the vdmc_* signals). Names mirror the shared lib's
# feature_engineering.core.config.price_path_feature_columns(); kept as a local
# literal so the SDK has no hard dependency on the lib (a unit test guards drift).
PRICE_PATH_FEATURE_COLUMNS = (
    "ret_1",
    "ret_4",
    "ret_16",
    "atr_norm_range",
    "atr_pct",
    "close_vs_ema_atr",
    "dd_from_peak_atr",
    "vol_of_vol",
)
SPECTRAL_FEATURE_PREFIXES = (
    "spectral_",
    "freq_band_",
    "frequency_phase_",
    "frequency_energy_",
    "fft_",
    "sempo_",
)
# Canonical cross-instrument relation lane columns (rel_corr_*/rel_beta_*/
# rel_strength_*). vdmc_*_z bounded forms are already kept by the vdmc_ prefix.
CROSS_RELATION_FEATURE_PREFIXES = ("rel_corr_", "rel_beta_", "rel_strength_")


def _ensure_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" not in df.columns:
        raise ConfigurationError("RL dataset requires a 'timestamp' column")
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="raise")
    return df.sort_values("timestamp").reset_index(drop=True)


def _as_float_series(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default).astype(float)


def _direction_proba(df: pd.DataFrame) -> pd.Series:
    momentum = df.get("vdmc_momentum")
    if momentum is None:
        close = _as_float_series(df["close"])
        momentum = close.pct_change().rolling(5, min_periods=1).mean()
    momentum = _as_float_series(momentum)
    # Ensure we return a pandas Series by using pandas operations
    sigmoid_values = 1.0 / (1.0 + np.exp(-3.0 * momentum))
    return pd.Series(sigmoid_values).clip(0.0, 1.0)


def _volatility_proba(df: pd.DataFrame) -> pd.Series:
    amplitude = df.get("vdmc_wave_amplitude")
    if amplitude is None:
        close = _as_float_series(df["close"])
        amplitude = close.pct_change().abs().rolling(20, min_periods=1).mean()
    amplitude = _as_float_series(amplitude).abs()
    normaliser = np.maximum(amplitude.max(), 1e-6)
    # Ensure we return a pandas Series
    normalized_values = amplitude / (normaliser + amplitude)
    return pd.Series(normalized_values).clip(0.0, 1.0)


def _ensemble_score(direction: pd.Series, volatility: pd.Series) -> pd.Series:
    score = 0.7 * direction + 0.3 * (1.0 - volatility)
    # Ensure we return a pandas Series
    return pd.Series(score).clip(0.0, 1.0)


def proba_provenance_column(channel: str) -> str:
    """Return the provenance column name for a probability channel."""

    try:
        return _PROVENANCE_COLUMNS[channel]
    except KeyError as exc:
        raise ValueError(f"Unsupported probability channel {channel!r}") from exc


def oof_available_column(channel: str) -> str:
    """Return the OOF availability flag column name for a probability channel."""

    try:
        return _OOF_AVAILABLE_COLUMNS[channel]
    except KeyError as exc:
        raise ValueError(f"Unsupported probability channel {channel!r}") from exc


def summarize_probability_provenance(
    df: pd.DataFrame,
    channel: str = "direction",
) -> dict[str, object]:
    """Summarize row-level probability provenance for RL gate artifacts."""

    provenance_col = proba_provenance_column(channel)
    oof_col = oof_available_column(channel)
    rows = int(len(df))

    if provenance_col in df.columns:
        provenance = (
            df[provenance_col]
            .fillna("missing")
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace("-", "_", regex=False)
        )
    elif oof_col in df.columns:
        available = df[oof_col].fillna(False).astype(bool)
        provenance = pd.Series(
            np.where(available, PROVENANCE_OOF, PROVENANCE_NEUTRAL_FALLBACK),
            index=df.index,
        )
    else:
        provenance = pd.Series(
            [PROVENANCE_LEGACY_INFERRED] * rows,
            index=df.index,
            dtype="object",
        )

    counts = {str(key): int(value) for key, value in provenance.value_counts().items()}
    honest_mask = provenance.isin(HONEST_PROBA_PROVENANCE)
    unsafe_mask = provenance.isin(UNSAFE_DIRECTION_PROBA_PROVENANCE)
    if oof_col in df.columns:
        oof_available_count = int(df[oof_col].fillna(False).astype(bool).sum())
    else:
        oof_available_count = int(honest_mask.sum())

    return {
        "channel": channel,
        "rows": rows,
        "counts": counts,
        "honest_count": int(honest_mask.sum()),
        "honest_coverage": float(honest_mask.mean()) if rows else 0.0,
        "oof_available_count": oof_available_count,
        "oof_available_coverage": float(oof_available_count / rows) if rows else 0.0,
        "unsafe_count": int(unsafe_mask.sum()),
        "unsafe_values": sorted(str(value) for value in provenance[unsafe_mask].unique()),
    }


def _ensure_channel_provenance(
    frame: pd.DataFrame,
    *,
    provenance_col: str,
    oof_col: str,
) -> None:
    if provenance_col not in frame.columns:
        if oof_col in frame.columns:
            available = frame[oof_col].fillna(False).astype(bool)
            frame[provenance_col] = np.where(
                available,
                PROVENANCE_OOF,
                PROVENANCE_NEUTRAL_FALLBACK,
            )
        else:
            frame[provenance_col] = PROVENANCE_LEGACY_INFERRED
    if oof_col not in frame.columns:
        provenance = (
            frame[provenance_col]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace("-", "_", regex=False)
        )
        frame[oof_col] = provenance.isin(HONEST_PROBA_PROVENANCE).astype(np.int8)


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def materialize_rl_dataset(
    df: pd.DataFrame,
    *,
    path: Path,
    feature_columns: Sequence[str] | None = None,
    stats: MutableMapping[str, object] | None = None,
) -> str:
    """Persist an enriched RL dataset derived from the provided dataframe.

    Args:
        df: Source dataframe containing bars and enrichment columns.
        path: Target parquet path.
        feature_columns: Optional extra feature names to retain.
        stats: Optional mapping that will be updated in-place with dataset metadata.

    Returns:
        The string representation of the written parquet path.
    """
    if df.empty:
        raise ConfigurationError("Cannot materialize RL dataset from an empty dataframe")

    frame = _ensure_timestamp(df)
    frame = frame.copy()
    frame["open"] = _as_float_series(frame["open"])
    frame["high"] = _as_float_series(frame["high"])
    frame["low"] = _as_float_series(frame["low"])
    frame["close"] = _as_float_series(frame["close"])
    frame["volume"] = _as_float_series(frame["volume"], default=0.0)

    if "ret" not in frame.columns:
        frame["ret"] = frame["close"].pct_change().fillna(0.0).astype(float)

    if "direction_proba" not in frame.columns:
        frame["direction_proba"] = _direction_proba(frame)
        frame[DIRECTION_PROBA_PROVENANCE_COLUMN] = PROVENANCE_SDK_PROXY
        frame[DIRECTION_OOF_AVAILABLE_COLUMN] = 0
    else:
        frame["direction_proba"] = frame["direction_proba"].clip(0.0, 1.0)
        _ensure_channel_provenance(
            frame,
            provenance_col=DIRECTION_PROBA_PROVENANCE_COLUMN,
            oof_col=DIRECTION_OOF_AVAILABLE_COLUMN,
        )

    if "volatility_proba" not in frame.columns:
        frame["volatility_proba"] = _volatility_proba(frame)
        frame[VOLATILITY_PROBA_PROVENANCE_COLUMN] = PROVENANCE_SDK_PROXY
        frame[VOLATILITY_OOF_AVAILABLE_COLUMN] = 0
    else:
        frame["volatility_proba"] = frame["volatility_proba"].clip(0.0, 1.0)
        _ensure_channel_provenance(
            frame,
            provenance_col=VOLATILITY_PROBA_PROVENANCE_COLUMN,
            oof_col=VOLATILITY_OOF_AVAILABLE_COLUMN,
        )

    if "ensemble_score" not in frame.columns:
        frame["ensemble_score"] = _ensemble_score(frame["direction_proba"], frame["volatility_proba"])
    else:
        frame["ensemble_score"] = frame["ensemble_score"].clip(0.0, 1.0)

    selected_columns: list[str] = list(_REQUIRED_BASE_COLUMNS)
    selected_columns.extend(_REQUIRED_PROBA_COLUMNS)
    selected_columns.extend(_PROVENANCE_COLUMNS.values())
    selected_columns.extend(_OOF_AVAILABLE_COLUMNS.values())
    if feature_columns:
        selected_columns.extend(feature_columns)
    # Keep the RL distilled-observation lib lanes if present: VDMC signals,
    # ATR price-path columns, and spectral columns. Harmless for the `full`
    # observation profile (the RL env excludes both lanes from generic
    # candidate selection); required so a `distilled` run sees them.
    _price_path = set(PRICE_PATH_FEATURE_COLUMNS)
    for col in frame.columns:
        if (
            col.startswith("vdmc_")
            or col in _price_path
            or str(col).startswith(SPECTRAL_FEATURE_PREFIXES)
            or str(col).startswith(CROSS_RELATION_FEATURE_PREFIXES)
        ):
            selected_columns.append(col)
    selected_columns.append("ret")
    selected_columns = _dedupe_preserve_order(selected_columns)
    available_columns = [col for col in selected_columns if col in frame.columns]
    missing = [col for col in _REQUIRED_BASE_COLUMNS + _REQUIRED_PROBA_COLUMNS if col not in available_columns]
    if missing:
        raise ConfigurationError(f"RL dataset missing required columns: {', '.join(missing)}")

    dataset = frame[available_columns].copy()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_parquet(path, index=False)

    if stats is not None:
        stats.update({
            "path": str(path),
            "rows": int(dataset.shape[0]),
            "columns": list(dataset.columns),
        })

    return str(path)


__all__ = [
    "DIRECTION_OOF_AVAILABLE_COLUMN",
    "DIRECTION_PROBA_PROVENANCE_COLUMN",
    "HONEST_PROBA_PROVENANCE",
    "PROVENANCE_HOLDOUT",
    "PROVENANCE_LEGACY_INFERRED",
    "PROVENANCE_MODEL_INFERENCE_FALLBACK",
    "PROVENANCE_NEUTRAL_FALLBACK",
    "PROVENANCE_OOF",
    "PROVENANCE_SDK_PROXY",
    "RLDatasetStats",
    "UNSAFE_DIRECTION_PROBA_PROVENANCE",
    "VOLATILITY_OOF_AVAILABLE_COLUMN",
    "VOLATILITY_PROBA_PROVENANCE_COLUMN",
    "materialize_rl_dataset",
    "oof_available_column",
    "proba_provenance_column",
    "summarize_probability_provenance",
]
