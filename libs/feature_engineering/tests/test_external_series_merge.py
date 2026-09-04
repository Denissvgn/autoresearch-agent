"""Phase 4 parity backbone: causal alignment of external series.

The same merge runs in training and serving, so its correctness IS parity
correctness. Critical properties pinned here: no look-ahead (backward as-of),
frequency-mismatch handling (sparse funding → dense bars), determinism, and
graceful skip of absent series.
"""
import numpy as np
import pandas as pd

from feature_engineering.external_series import merge_external_series


def _bars(n=8, start="2025-01-01 00:00", freq="15min"):
    idx = pd.date_range(start, periods=n, freq=freq)
    return pd.DataFrame({"close": np.arange(100.0, 100.0 + n)}, index=idx)


def test_backward_asof_no_lookahead():
    bars = _bars(8)  # 00:00..01:45 at 15m
    # Funding known only at 00:30 and 01:15 (sparse, mid-window).
    funding = pd.DataFrame({
        "timestamp": pd.to_datetime(["2025-01-01 00:30", "2025-01-01 01:15"]),
        "funding_rate": [0.001, 0.002],
    })
    out = merge_external_series(bars, funding=funding)
    fr = out["funding_rate"]
    # Bars before the first funding obs have no prior value → NaN (never a future one).
    assert pd.isna(fr.iloc[0]) and pd.isna(fr.iloc[1])  # 00:00, 00:15
    # 00:30, 00:45, 01:00 use the 00:30 value (most recent ≤ bar).
    assert (fr.iloc[2:5] == 0.001).all()
    # 01:15 onward use the 01:15 value — and NOT before it (no look-ahead).
    assert (fr.iloc[5:] == 0.002).all()


def test_frequency_mismatch_forward_fills():
    bars = _bars(12, freq="15min")
    # One funding obs at the start → all later bars carry it forward.
    funding = pd.DataFrame({"timestamp": [bars.index[0]], "funding_rate": [0.0005]})
    out = merge_external_series(bars, funding=funding)
    assert (out["funding_rate"] == 0.0005).all()


def test_ms_epoch_timestamps_supported():
    bars = _bars(4)
    ts_ms = int(bars.index[1].value // 1_000_000)  # ns → ms
    oi = pd.DataFrame({"timestamp": [ts_ms], "open_interest": [1.0e9]})
    out = merge_external_series(bars, open_interest=oi)
    assert pd.isna(out["open_interest"].iloc[0])      # before the obs
    assert (out["open_interest"].iloc[1:] == 1.0e9).all()


def test_iso_string_timestamps_supported():
    """The S3-cache endpoint serves timestamps as ISO datetime STRINGS (object
    dtype, e.g. '2025-01-01T00:15:00'); applying unit='ms' to those raises, so
    they must be parsed directly. Regression for the live funding-merge failure."""
    bars = _bars(4)  # 00:00, 00:15, 00:30, 00:45
    # MIXED sub-second precision, as the cache actually serves it: one whole-second
    # ISO string (no fraction) and one with microseconds. A bare to_datetime infers
    # a format from the first value and raises on the other — this pins ISO8601.
    ts0 = bars.index[0].isoformat()                              # "...T00:00:00"
    ts2 = (bars.index[2] + pd.Timedelta("0.002s")).isoformat()  # "...T00:30:00.002000"
    funding = pd.DataFrame({"timestamp": [ts0, ts2], "funding_rate": [0.0007, 0.0009]})
    assert funding["timestamp"].dtype == object
    out = merge_external_series(bars, funding=funding)
    # 00:00–00:30 carry the first obs; 00:45 (after 00:30.002) carries the second.
    assert (out["funding_rate"].iloc[0:3] == 0.0007).all()
    assert out["funding_rate"].iloc[3] == 0.0009


def test_cross_asset_close_aligned():
    bars = _bars(5)
    btc = pd.DataFrame({"timestamp": [bars.index[0], bars.index[2]], "close": [30000.0, 31000.0]})
    out = merge_external_series(bars, btc=btc)
    assert out["btc_close"].iloc[0] == 30000.0
    assert out["btc_close"].iloc[1] == 30000.0  # carried forward
    assert (out["btc_close"].iloc[2:] == 31000.0).all()


def test_absent_series_skipped():
    bars = _bars(4)
    out = merge_external_series(bars, funding=None, open_interest=pd.DataFrame())
    assert "funding_rate" not in out.columns
    assert "open_interest" not in out.columns
    # OHLCV preserved unchanged.
    assert list(out.columns) == ["close"]


def test_deterministic_and_order_independent():
    bars = _bars(6)
    funding = pd.DataFrame({
        "timestamp": [bars.index[3], bars.index[1]],  # deliberately unsorted
        "funding_rate": [0.002, 0.001],
    })
    out1 = merge_external_series(bars, funding=funding)
    out2 = merge_external_series(bars, funding=funding.sort_values("timestamp"))
    pd.testing.assert_series_equal(out1["funding_rate"], out2["funding_rate"])
    # determinism on repeat
    out3 = merge_external_series(bars, funding=funding)
    pd.testing.assert_series_equal(out1["funding_rate"], out3["funding_rate"])


def test_timestamp_column_frame_supported():
    # OHLCV with a 'timestamp' column instead of a DatetimeIndex.
    idx = pd.date_range("2025-01-01", periods=4, freq="15min")
    bars = pd.DataFrame({"timestamp": idx, "close": [1.0, 2.0, 3.0, 4.0]})
    funding = pd.DataFrame({"timestamp": [idx[1]], "funding_rate": [0.01]})
    out = merge_external_series(bars, funding=funding)
    assert pd.isna(out["funding_rate"].iloc[0])
    assert (out["funding_rate"].iloc[1:] == 0.01).all()
