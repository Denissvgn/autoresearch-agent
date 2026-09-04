"""Phase 4: causal alignment of external series into the OHLCV frame.

This is the **parity backbone**: training (ensemble-trainer) and serving
(feature-service) both call ``merge_external_series`` on the OHLCV frame BEFORE
``FeatureEngineer.calculate_all_features``. Sharing one alignment primitive
guarantees the cross-asset / derivatives feature columns are produced
identically on both paths (``inference_parity``).

Alignment is a **backward as-of join**: each bar takes the most recent external
value at or before the bar's close timestamp. This is leakage-safe (never uses a
future value) and naturally handles frequency mismatch (e.g. 8h funding → 15m
bars behaves like a forward-fill of the last known value).
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

# external arg name -> (output column on the OHLCV frame, value column in the source)
_SERIES_MAP = (
    ("btc", "btc_close", "close"),
    ("eth", "eth_close", "close"),
    ("funding", "funding_rate", "funding_rate"),
    ("open_interest", "open_interest", "open_interest"),
)


def _to_datetime_index(ts: pd.Series) -> pd.Series:
    """Coerce a timestamp Series to tz-naive datetime.

    Accepts the three shapes the loaders/endpoints produce: datetime64, integer/
    float ms-epoch (binance/ccxt, live fetch), and ISO datetime strings (object
    dtype — e.g. served from the S3 cache via to_dict). Only numeric epochs use
    ``unit='ms'``; strings are parsed directly (applying 'ms' to them raises).
    """
    if pd.api.types.is_datetime64_any_dtype(ts):
        out = pd.to_datetime(ts)
    elif pd.api.types.is_numeric_dtype(ts):
        out = pd.to_datetime(ts, unit="ms")
    else:
        # ISO strings with MIXED sub-second precision (…00 vs …00.002000) — the
        # cache serializes datetimes that way. format="ISO8601" parses each
        # element independently; a bare to_datetime infers one format from the
        # first value and then raises on the others.
        out = pd.to_datetime(ts, format="ISO8601")
    try:
        out = out.dt.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    return out


def _base_timestamps(ohlcv: pd.DataFrame) -> pd.Series:
    if isinstance(ohlcv.index, pd.DatetimeIndex):
        return pd.Series(ohlcv.index, index=ohlcv.index).pipe(
            lambda s: pd.Series(_to_datetime_index(s).values, index=ohlcv.index)
        )
    if "timestamp" in ohlcv.columns:
        return pd.Series(_to_datetime_index(ohlcv["timestamp"]).values, index=ohlcv.index)
    raise ValueError("ohlcv must have a DatetimeIndex or a 'timestamp' column")


def _asof_align(base_ts: pd.Series, source: pd.DataFrame, value_col: str) -> pd.Series:
    """Backward as-of: most recent ``value_col`` at or before each base timestamp.

    Returns a Series indexed like ``base_ts`` (NaN where no prior value exists).
    """
    src = source[["timestamp", value_col]].copy()
    src["timestamp"] = _to_datetime_index(src["timestamp"])
    src = src.dropna(subset=["timestamp"]).sort_values("timestamp")

    left = pd.DataFrame({"_ts": pd.to_datetime(base_ts.values)})
    left["_orig_pos"] = range(len(left))
    left_sorted = left.sort_values("_ts")

    merged = pd.merge_asof(
        left_sorted, src.rename(columns={"timestamp": "_ts"}),
        on="_ts", direction="backward",
    )
    # Restore original order, then re-index to the OHLCV frame.
    merged = merged.sort_values("_orig_pos")
    return pd.Series(merged[value_col].to_numpy(), index=base_ts.index)


def merge_external_series(
    ohlcv: pd.DataFrame,
    *,
    btc: Optional[pd.DataFrame] = None,
    eth: Optional[pd.DataFrame] = None,
    funding: Optional[pd.DataFrame] = None,
    open_interest: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Return ``ohlcv`` with available external columns aligned causally.

    Each source is a DataFrame with a ``timestamp`` column (datetime or ms-epoch)
    plus its value column. A source that is None/empty/missing its value column
    is skipped — the feature builder then zero-fills and flags it unavailable, so
    the produced feature SCHEMA is identical whether or not the data is present.
    """
    out = ohlcv.copy()
    base_ts = _base_timestamps(out)
    provided = {"btc": btc, "eth": eth, "funding": funding, "open_interest": open_interest}

    for arg_name, out_col, value_col in _SERIES_MAP:
        src = provided.get(arg_name)
        if src is None or len(src) == 0 or value_col not in getattr(src, "columns", []):
            continue
        out[out_col] = _asof_align(base_ts, src, value_col)
    return out
