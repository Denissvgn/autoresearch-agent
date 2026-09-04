"""Causal market-regime detection shared by RL training and serving (MQ-D2).

The historic skew (backlog G-7): the RL training env labelled every bar with
``detect_regimes()`` whose volatility baseline was the median of the rolling
vol over the ENTIRE series — non-causal and impossible to reproduce at serve
time — while the inference observation builder approximated the labels with a
different statistic (median of absolute bar returns). A deployed agent would
therefore see silently wrong regime one-hots.

``detect_regimes_causal`` fixes both properties at once:

- **Causal** — the label at bar *t* uses only bars ``<= t`` (the volatility
  baseline becomes a TRAILING rolling median of the rolling vol).
- **Bounded** — the label at bar *t* depends on at most
  :func:`min_history_bars` trailing bars, so serving reproduces the training
  label exactly whenever it supplies at least that much close history.

Both the training env and the inference observation builder import this
module; the detector version + params are stamped into ``obs_spec.json``
(``regime_detector`` block) so serving fails closed on artifacts trained with
a detector it cannot reproduce.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

#: Bump when the detection algorithm changes incompatibly. Serving refuses to
#: reconstruct regime observations for unknown versions (fail-closed, rule R4).
REGIME_DETECTOR_VERSION = "causal_v1"

#: One-hot encoding order — must match TradingEnv._REGIME_INDEX and the
#: serving observation builder.
REGIME_ONEHOT_ORDER = ("BULL", "BEAR", "CHOP", "STRESS")

DEFAULT_REGIME_DETECTOR_PARAMS: Dict[str, Any] = {
    "lookback": 100,
    "baseline_window": 300,
    "trend_threshold": 0.02,
    "vol_multiplier": 1.5,
}


def resolve_params(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge user params over the defaults (unknown keys are ignored)."""
    resolved = dict(DEFAULT_REGIME_DETECTOR_PARAMS)
    if params:
        for key in resolved:
            if params.get(key) is not None:
                resolved[key] = params[key]
    return resolved


def min_history_bars(params: Optional[Dict[str, Any]] = None) -> int:
    """Trailing close bars needed for an exact (training-equal) last-bar label."""
    p = resolve_params(params)
    return int(p["lookback"]) + int(p["baseline_window"]) + 1


def detect_regimes_causal(
    close_prices: pd.Series,
    *,
    lookback: int = 100,
    baseline_window: int = 300,
    trend_threshold: float = 0.02,
    vol_multiplier: float = 1.5,
) -> pd.Series:
    """Label each bar with a market regime using only trailing data.

    Algorithm (causal variant of the ML-33 detector):
        1. Rolling return over *lookback* bars.
        2. Rolling volatility (std of 1-bar returns) over *lookback*.
        3. Volatility baseline = TRAILING rolling median of the rolling vol
           over *baseline_window* bars (the non-causal full-series median is
           what this replaces).
        4. Classify: STRESS if vol > baseline × *vol_multiplier* (overrides
           trend); BULL/BEAR if |return| > *trend_threshold*; else CHOP.

    Returns a Series of string labels from :data:`REGIME_ONEHOT_ORDER`, same
    index as *close_prices*. Bars with insufficient history default to CHOP.
    """
    n = len(close_prices)
    if n < 2:
        return pd.Series(["CHOP"] * n, index=close_prices.index)

    rolling_ret = close_prices.pct_change(periods=lookback)
    bar_returns = close_prices.pct_change()
    rolling_vol = bar_returns.rolling(
        window=lookback, min_periods=max(lookback // 2, 2)
    ).std()
    vol_baseline = rolling_vol.rolling(
        window=baseline_window, min_periods=max(baseline_window // 4, 10)
    ).median()

    regimes = pd.Series("CHOP", index=close_prices.index)
    bull_mask = rolling_ret > trend_threshold
    bear_mask = rolling_ret < -trend_threshold
    stress_mask = (rolling_vol > vol_baseline * vol_multiplier).fillna(False)

    regimes[bull_mask.fillna(False)] = "BULL"
    regimes[bear_mask.fillna(False)] = "BEAR"
    # STRESS overrides trend classification
    regimes[stress_mask] = "STRESS"
    return regimes


def regime_onehot(label: Any) -> List[float]:
    """4-element one-hot for a label (string or enum-like); unknown → CHOP."""
    name = str(getattr(label, "value", label)).upper()
    onehot = [0.0, 0.0, 0.0, 0.0]
    try:
        onehot[REGIME_ONEHOT_ORDER.index(name)] = 1.0
    except ValueError:
        onehot[REGIME_ONEHOT_ORDER.index("CHOP")] = 1.0
    return onehot


def last_bar_regime_onehot(
    close_values: Sequence[float],
    params: Optional[Dict[str, Any]] = None,
) -> List[float]:
    """One-hot regime of the LAST bar from a trailing close-price tail.

    Serving-side entry point: identical to the training env's per-bar label
    whenever ``len(close_values) >= min_history_bars(params)`` (the detector
    is bounded, so extra history beyond that cannot change the result —
    the tail is truncated to exactly that window).
    """
    p = resolve_params(params)
    values = np.asarray(list(close_values), dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 2:
        return regime_onehot("CHOP")
    values = values[-min_history_bars(p):]
    labels = detect_regimes_causal(
        pd.Series(values),
        lookback=int(p["lookback"]),
        baseline_window=int(p["baseline_window"]),
        trend_threshold=float(p["trend_threshold"]),
        vol_multiplier=float(p["vol_multiplier"]),
    )
    return regime_onehot(labels.iloc[-1])
