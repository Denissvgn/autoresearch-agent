"""Hierarchical, ATR-scaled Directional-Change (DC) decomposition.

The Directional-Change (intrinsic-time) framework segments a price series into
alternating up/down *legs* separated by confirmed reversals. A reversal at
threshold ``theta`` is confirmed only once price retraces by ``theta`` from the
running extreme — so the *confirmed* state at bar ``t`` uses no future
information (causal), suitable for features. The *forward* leg direction (which
way the next confirmed pivot lies) is future-looking and is used only as a
supervised label.

Used two ways:
  * **Labels** (``dc_forward_direction``): at the finest threshold, mark each bar
    by the direction toward its next confirmed pivot. Because the finest
    threshold is small, almost every bar is inside *some* leg — this avoids the
    fixed-pct dead-zone that drops ~89% of bars to FLAT and starves training /
    calibration.
  * **Features** (``dc_confirmed_state`` over a ladder of thresholds): per-scale
    causal trend direction, overshoot since the last extreme, and bars since the
    last reversal — multi-resolution directional context.

All thresholds are expressed as ATR multiples; the per-bar fractional threshold
is ``mult * ATR[t] / close[t]`` (regime-adaptive: wider in volatile periods).
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

__all__ = [
    "wilder_atr",
    "theta_from_atr",
    "dc_pivots",
    "dc_confirmed_state",
    "dc_forward_direction",
]


def wilder_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """Wilder ATR (rolling mean of true range). Mirrors the ATR used by the
    vol-scaled label builder so the DC thresholds share one definition."""
    high = high.astype(float)
    low = low.astype(float)
    close = close.astype(float)
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window=int(period), min_periods=int(period)).mean()


def theta_from_atr(
    close: np.ndarray, atr: np.ndarray, mult: float
) -> np.ndarray:
    """Per-bar fractional DC threshold ``mult * ATR / close`` (NaN where unusable)."""
    close = np.asarray(close, dtype=np.float64)
    atr = np.asarray(atr, dtype=np.float64)
    theta = np.full(close.shape, np.nan, dtype=np.float64)
    valid = np.isfinite(close) & np.isfinite(atr) & (close > 0.0) & (atr > 0.0)
    theta[valid] = float(mult) * atr[valid] / close[valid]
    return theta


def dc_pivots(
    close: np.ndarray, theta: np.ndarray
) -> Tuple[List[Tuple[int, float, int]], np.ndarray]:
    """Causal Directional-Change scan.

    Returns ``(pivots, confirmed_mode)`` where:
      * ``pivots`` is the chronological list of confirmed extrema
        ``(index, price, kind)`` with ``kind=+1`` for a peak (an up-leg ended) and
        ``kind=-1`` for a trough (a down-leg ended);
      * ``confirmed_mode[t]`` is the leg direction known *as of* bar ``t``
        (+1 up / -1 down / 0 before the first confirmation) — causal.

    ``theta`` is the per-bar fractional reversal threshold; NaN thresholds fall
    back to the last finite value (so warm-up bars don't spuriously reverse).
    """
    n = len(close)
    confirmed_mode = np.zeros(n, dtype=np.int8)
    pivots: List[Tuple[int, float, int]] = []
    if n == 0:
        return pivots, confirmed_mode

    mode = 1  # start tracking an up-move (extreme = running max)
    ext_idx = 0
    ext_price = float(close[0])
    cm = 0
    last_theta = np.nan
    for t in range(1, n):
        th = theta[t]
        if not np.isfinite(th):
            th = last_theta
        else:
            last_theta = th
        p = float(close[t])
        if not np.isfinite(p) or not np.isfinite(th) or ext_price <= 0.0:
            confirmed_mode[t] = cm
            continue
        if mode == 1:
            if p > ext_price:
                ext_price, ext_idx = p, t
            elif (ext_price - p) / ext_price >= th:
                pivots.append((ext_idx, ext_price, +1))  # peak confirmed
                mode, ext_price, ext_idx, cm = -1, p, t, -1
        else:
            if p < ext_price:
                ext_price, ext_idx = p, t
            elif (p - ext_price) / ext_price >= th:
                pivots.append((ext_idx, ext_price, -1))  # trough confirmed
                mode, ext_price, ext_idx, cm = 1, p, t, +1
        confirmed_mode[t] = cm
    return pivots, confirmed_mode


def dc_confirmed_state(
    close: np.ndarray, theta: np.ndarray
) -> Dict[str, np.ndarray]:
    """Causal per-bar DC state for features (no look-ahead).

    Returns dict of arrays:
      * ``dir``: confirmed leg direction (+1/-1/0).
      * ``overshoot``: signed fractional move from the last confirmed extreme to
        the current close (how far the current leg has run).
      * ``bars_since``: bars since the last confirmed reversal.
    """
    n = len(close)
    pivots, confirmed_mode = dc_pivots(close, theta)
    overshoot = np.zeros(n, dtype=np.float64)
    bars_since = np.zeros(n, dtype=np.float64)
    # Confirmation bars: the bar at which each reversal becomes known. A pivot at
    # extreme index e is confirmed at the first later bar that breaches theta; we
    # reconstruct confirmation bars by re-walking via confirmed_mode changes.
    last_event_bar = 0
    last_ext_price = float(close[0]) if n else 0.0
    prev_cm = 0
    # Map extreme prices by their confirmation (mode-change) bar.
    piv_iter = iter(pivots)
    next_piv = next(piv_iter, None)
    for t in range(n):
        cm = int(confirmed_mode[t])
        if cm != prev_cm and cm != 0:
            # a reversal just became confirmed at bar t
            last_event_bar = t
            if next_piv is not None:
                last_ext_price = float(next_piv[1])
                next_piv = next(piv_iter, None)
            prev_cm = cm
        bars_since[t] = float(t - last_event_bar)
        c = float(close[t])
        if np.isfinite(c) and last_ext_price > 0.0:
            overshoot[t] = (c - last_ext_price) / last_ext_price
    return {
        "dir": confirmed_mode.astype(np.float64),
        "overshoot": overshoot,
        "bars_since": bars_since,
    }


def dc_forward_direction(close: np.ndarray, theta: np.ndarray) -> np.ndarray:
    """Forward leg direction for LABELS (uses future pivots — target only).

    ``+1`` if the next confirmed pivot after ``t`` is a peak (bar is in an up-leg),
    ``-1`` if a trough (down-leg), ``0`` for the unresolved tail after the last
    pivot. Because the threshold is small at the finest scale, very few bars land
    in the ``0`` tail — which is the point (dense directional labels).
    """
    n = len(close)
    out = np.zeros(n, dtype=np.float64)
    pivots, _ = dc_pivots(close, theta)
    if not pivots:
        return out
    pidx = [p[0] for p in pivots]
    ptype = [p[2] for p in pivots]
    j = 0
    for t in range(n):
        while j < len(pidx) and pidx[j] <= t:
            j += 1
        out[t] = float(ptype[j]) if j < len(pidx) else 0.0
    return out
