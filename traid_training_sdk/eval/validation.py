from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .metrics import (
    compute_regression_metrics,
    max_drawdown,
    pnl,
    sharpe,
)


@dataclass(frozen=True)
class WindowSummary:
    metrics_mean: dict[str, float]
    metrics_std: dict[str, float]
    windows: list[dict[str, float]]


def rolling_validate_predictions(
    *,
    y_true,
    y_pred,
    window_size: int,
    step: Optional[int] = None,
    metrics: Optional[list[str]] = None,
) -> WindowSummary:
    yt = np.asarray(y_true)
    yp = np.asarray(y_pred)
    n = len(yt)
    step = step or window_size
    windows: list[dict[str, float]] = []
    for start in range(0, max(n - window_size + 1, 1), step):
        end = min(start + window_size, n)
        m = compute_regression_metrics(yt[start:end], yp[start:end], metrics=metrics)
        windows.append(m)
    # Aggregate
    keys = windows[0].keys() if windows else []
    metrics_mean = {k: float(np.mean([w[k] for w in windows])) for k in keys}
    metrics_std = {k: float(np.std([w[k] for w in windows], ddof=0)) for k in keys}
    return WindowSummary(metrics_mean=metrics_mean, metrics_std=metrics_std, windows=windows)


def rolling_backtest(
    returns,
    *,
    window_size: int,
    step: Optional[int] = None,
) -> WindowSummary:
    arr = np.asarray(returns, dtype=float)
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    if arr.size < window_size:
        raise ValueError("returns length must be >= window_size")
    if step is None:
        step = window_size
    if step <= 0:
        raise ValueError("step must be positive")
    windows: list[dict[str, float]] = []
    for start in range(0, arr.size - window_size + 1, step):
        end = start + window_size
        segment = arr[start:end]
        metrics = {
            "pnl": pnl(segment),
            "sharpe": sharpe(segment),
            "max_drawdown": max_drawdown(segment),
        }
        windows.append(metrics)
    if not windows:
        raise ValueError("step/window combination produced no windows")
    metrics_mean = {k: float(np.mean([w[k] for w in windows])) for k in windows[0].keys()}
    metrics_std = {k: float(np.std([w[k] for w in windows], ddof=0)) for k in windows[0].keys()}
    return WindowSummary(metrics_mean=metrics_mean, metrics_std=metrics_std, windows=windows)
