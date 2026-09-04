from __future__ import annotations

from typing import Any, Dict, Protocol, Union

import numpy as np
import pandas as pd
import pandas_ta as ta

from ..data.sources import enrich_with_vdmc


IndicatorResult = Union[pd.Series, Dict[str, pd.Series]]


class IndicatorFunction(Protocol):
    """Protocol for indicator calculation functions."""

    def __call__(self, df: pd.DataFrame, *args: Any, **kwargs: Any) -> IndicatorResult:
        ...


def build_indicator_features(
    df: pd.DataFrame,
    *,
    include: dict[str, bool] | None = None,
    vdmc_params: dict[str, float | int] | None = None,
    dropna: bool = True,
) -> pd.DataFrame:
    """
    Compute a compact set of indicator features and VDMC-like signals.

    include flags: {"ma": True, "vdmc": True}
    """
    flags = {"ma": True, "vdmc": True}
    if include:
        flags.update(include)

    out = df.copy()
    if flags["ma"]:
        out["ma_5"] = out["close"].rolling(5, min_periods=1).mean()
        out["ma_10"] = out["close"].rolling(10, min_periods=1).mean()
        out["ma_ratio"] = out["ma_5"] / out["ma_10"].replace(0, np.nan)
        out["ret"] = out["close"] / out["open"] - 1.0
    if flags["vdmc"]:
        kwargs = vdmc_params or {}
        out = enrich_with_vdmc(out, **kwargs)
    if dropna:
        out = out.dropna()
    return out


def build_direction_feature_set(
    df: pd.DataFrame,
    *,
    include: dict[str, bool] | None = None,
    dropna: bool = True,
    **vdmc_params: float | int,
) -> pd.DataFrame:
    """Helper for direction models that removes target column after feature engineering."""
    features = build_indicator_features(
        df,
        include=include,
        vdmc_params=vdmc_params or None,
        dropna=dropna,
    )
    return features.drop(columns=["ret"], errors="ignore")


def compare_feature_parity(
    offline: pd.DataFrame,
    online: pd.DataFrame,
    *,
    columns: list[str] | None = None,
    tolerance: float = 1e-6,
) -> dict[str, float]:
    """Compare offline vs online features and return absolute mean diffs per column."""
    if not len(offline) or not len(online):
        raise ValueError("Both offline and online frames must be non-empty")
    cols = columns or sorted(set(offline.columns).intersection(online.columns))
    if not cols:
        raise ValueError("No overlapping columns to compare")

    diffs: dict[str, float] = {}
    for col in cols:
        if col not in offline.columns or col not in online.columns:
            continue
        off = offline[col].astype(float).to_numpy()
        onl = online[col].astype(float).to_numpy()
        length = min(len(off), len(onl))
        if length == 0:
            raise ValueError(f"Column {col} has no comparable rows")
        diff = float(np.abs(off[:length] - onl[:length]).mean())
        if diff <= max(tolerance, 0.0):
            diff = 0.0
        diffs[col] = diff
    return diffs


def calculate_sma(df: pd.DataFrame, timeperiod: int = 14) -> pd.Series:
    """Calculates Simple Moving Average."""
    if "close" not in df.columns:
        raise ValueError("DataFrame must contain 'close' column for SMA calculation")
    if df.empty:
        raise ValueError("DataFrame cannot be empty for SMA calculation")
    if timeperiod <= 0:
        raise ValueError("Time period must be positive for SMA calculation")
    result = df["close"].rolling(window=timeperiod, min_periods=1).mean()
    return result.rename(f"sma_{timeperiod}")


def calculate_ema(df: pd.DataFrame, timeperiod: int = 14) -> pd.Series:
    """Calculates Exponential Moving Average."""
    if "close" not in df.columns:
        raise ValueError("DataFrame must contain 'close' column for EMA calculation")
    if df.empty:
        raise ValueError("DataFrame cannot be empty for EMA calculation")
    if timeperiod <= 0:
        raise ValueError("Time period must be positive for EMA calculation")
    result = ta.ema(df["close"], length=timeperiod)
    if result is None:
        result = df["close"].ewm(span=timeperiod, min_periods=1, adjust=False).mean()
    return result.rename(f"ema_{timeperiod}")


def calculate_rsi(df: pd.DataFrame, timeperiod: int = 14) -> pd.Series:
    """Calculates Relative Strength Index."""
    if "close" not in df.columns:
        raise ValueError("DataFrame must contain 'close' column for RSI calculation")
    if df.empty:
        raise ValueError("DataFrame cannot be empty for RSI calculation")
    if timeperiod <= 0:
        raise ValueError("Time period must be positive for RSI calculation")
    result = ta.rsi(df["close"], length=timeperiod)
    if result is None:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(span=timeperiod, min_periods=1, adjust=False).mean()
        avg_loss = loss.ewm(span=timeperiod, min_periods=1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        result = 100 - (100 / (1 + rs))
    return result.rename(f"rsi_{timeperiod}")


def calculate_atr(df: pd.DataFrame, timeperiod: int = 14) -> pd.Series:
    """Calculates Average True Range."""
    required_columns = ["high", "low", "close"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"DataFrame must contain {required_columns} columns for ATR calculation. Missing: {missing_columns}"
        )
    if df.empty:
        raise ValueError("DataFrame cannot be empty for ATR calculation")
    if timeperiod <= 0:
        raise ValueError("Time period must be positive for ATR calculation")
    result = ta.atr(df["high"], df["low"], df["close"], length=timeperiod)
    if result is None:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        result = tr.ewm(span=timeperiod, min_periods=1, adjust=False).mean()
    return result.rename(f"atr_{timeperiod}")


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculates Volume Weighted Average Price."""
    required_columns = ["high", "low", "close", "volume"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"DataFrame must contain {required_columns} columns for VWAP calculation. Missing: {missing_columns}"
        )
    if df.empty:
        raise ValueError("DataFrame cannot be empty for VWAP calculation")
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_pv = (typical_price * df["volume"]).cumsum()
    cumulative_volume = df["volume"].cumsum()
    cumulative_volume_safe = cumulative_volume.replace(0, 1e-10)
    result = cumulative_pv / cumulative_volume_safe
    return result.rename("vwap")


def calculate_bollinger(
    df: pd.DataFrame,
    timeperiod: int = 20,
    nbdevup: float = 2.0,
    nbdevdn: float = 2.0,
) -> Dict[str, pd.Series]:
    """Calculates Bollinger Bands."""
    if "close" not in df.columns:
        raise ValueError("DataFrame must contain 'close' column for Bollinger Bands calculation")
    if df.empty:
        raise ValueError("DataFrame cannot be empty for Bollinger Bands calculation")
    if timeperiod <= 0:
        raise ValueError("Time period must be positive for Bollinger Bands calculation")
    middle = ta.sma(df["close"], length=timeperiod)
    if middle is None:
        middle = df["close"].rolling(window=timeperiod, min_periods=1).mean()
    std = ta.stdev(df["close"], length=timeperiod)
    if std is None:
        std = df["close"].rolling(window=timeperiod, min_periods=1).std()
    upper = middle + (std * nbdevup)
    lower = middle - (std * nbdevdn)
    return {
        f"bollinger_upper_{timeperiod}": upper,
        f"bollinger_middle_{timeperiod}": middle,
        f"bollinger_lower_{timeperiod}": lower,
    }


def calculate_macd(
    df: pd.DataFrame,
    fastperiod: int = 12,
    slowperiod: int = 26,
    signalperiod: int = 9,
) -> Dict[str, pd.Series]:
    """Calculates Moving Average Convergence Divergence."""
    if "close" not in df.columns:
        raise ValueError("DataFrame must contain 'close' column for MACD calculation")
    if df.empty:
        raise ValueError("DataFrame cannot be empty for MACD calculation")
    if fastperiod <= 0 or slowperiod <= 0 or signalperiod <= 0:
        raise ValueError("All periods must be positive for MACD calculation")
    if fastperiod >= slowperiod:
        raise ValueError("Fast period must be less than slow period for MACD calculation")
    macd_df = ta.macd(df["close"], fast=fastperiod, slow=slowperiod, signal=signalperiod)
    if macd_df is None:
        ema_fast = df["close"].ewm(span=fastperiod, min_periods=1, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slowperiod, min_periods=1, adjust=False).mean()
        macd = ema_fast - ema_slow
        macdsignal = macd.ewm(span=signalperiod, min_periods=1, adjust=False).mean()
        macdhist = macd - macdsignal
    else:
        macd = macd_df.iloc[:, 0]
        macdhist = macd_df.iloc[:, 1]
        macdsignal = macd_df.iloc[:, 2]
    return {
        f"macd_{fastperiod}_{slowperiod}_{signalperiod}": macd,
        f"macdsignal_{fastperiod}_{slowperiod}_{signalperiod}": macdsignal,
        f"macdhist_{fastperiod}_{slowperiod}_{signalperiod}": macdhist,
    }


def calculate_vdmc_macd_proxy(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.Series:
    """Calculates the legacy MACD-style VDMC proxy.

    This is not canonical VDMC. Canonical train/serve VDMC is the
    ``vdmc_core`` wave-function implementation exposed through
    ``feature_engineering.advanced.vdmc``.

    Args:
        df: DataFrame with OHLC+V columns
        fast: Fast period for VDMC calculation (default: 12)
        slow: Slow period for VDMC calculation (default: 26)
        signal: Signal period for VDMC calculation (default: 9)

    Returns:
        pd.Series: VDMC histogram values

    Raises:
        ValueError: If input validation fails
    """
    required_columns = ["high", "low", "close", "volume"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"DataFrame must contain {required_columns} columns for VDMC calculation. Missing: {missing_columns}"
        )
    if df.empty:
        raise ValueError("DataFrame cannot be empty for VDMC calculation")
    if fast <= 0 or slow <= 0 or signal <= 0:
        raise ValueError("All periods must be positive for VDMC calculation")
    if fast >= slow:
        raise ValueError("Fast period must be less than slow period for VDMC calculation")
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    volume_weighted_price = typical_price * df["volume"]
    cumulative_vwp = volume_weighted_price.cumsum()
    cumulative_volume = df["volume"].cumsum()
    cumulative_volume_safe = cumulative_volume.replace(0, 1e-10)
    vwp_ratio = cumulative_vwp / cumulative_volume_safe
    ema_fast = vwp_ratio.ewm(span=fast, min_periods=1, adjust=False).mean()
    ema_slow = vwp_ratio.ewm(span=slow, min_periods=1, adjust=False).mean()
    vdmc_line = ema_fast - ema_slow
    vdmc_signal = vdmc_line.ewm(span=signal, min_periods=1, adjust=False).mean()
    vdmc_histogram = vdmc_line - vdmc_signal
    return vdmc_histogram.rename(f"vdmc_macd_proxy_{fast}_{slow}_{signal}")


def calculate_vdmc(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """Deprecated alias for the legacy MACD-style VDMC proxy."""
    return calculate_vdmc_macd_proxy(df, fast=fast, slow=slow, signal=signal)
