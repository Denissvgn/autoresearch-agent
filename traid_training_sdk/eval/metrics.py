from __future__ import annotations

from math import sqrt
from typing import Iterable, Optional

import numpy as np


def rmse(y_true, y_pred) -> float:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((yt - yp) ** 2)))


def mae(y_true, y_pred) -> float:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(yt - yp)))


def mape(y_true, y_pred) -> float:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    denom = np.clip(np.abs(yt), 1e-12, None)
    return float(np.mean(np.abs((yt - yp) / denom)))


def r2(y_true, y_pred) -> float:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    ss_res = np.sum((yt - yp) ** 2)
    ss_tot = np.sum((yt - yt.mean()) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0


def accuracy(y_true, y_pred) -> float:
    yt = np.asarray(y_true)
    yp = np.asarray(y_pred)
    return float(np.mean(yt == yp))


def f1_score(y_true, y_pred) -> float:
    # Macro-F1 for binary or multiclass
    yt = np.asarray(y_true)
    yp = np.asarray(y_pred)
    classes = np.unique(yt)
    f1s = []
    for c in classes:
        tp = np.sum((yp == c) & (yt == c))
        fp = np.sum((yp == c) & (yt != c))
        fn = np.sum((yp != c) & (yt == c))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        f1s.append(f1)
    return float(np.mean(f1s))


def roc_auc(y_true, y_score) -> Optional[float]:
    try:
        from sklearn.metrics import roc_auc_score  # type: ignore
    except Exception:  # pragma: no cover
        return None
    try:
        return float(roc_auc_score(y_true, y_score, multi_class="ovr"))
    except Exception:
        return None


def compute_regression_metrics(y_true, y_pred, metrics: Optional[Iterable[str]] = None) -> dict[str, float]:
    selected = list(metrics) if metrics is not None else ["rmse", "mae", "r2"]
    out: dict[str, float] = {}
    for m in selected:
        if m == "rmse":
            out[m] = rmse(y_true, y_pred)
        elif m == "mae":
            out[m] = mae(y_true, y_pred)
        elif m == "mape":
            out[m] = mape(y_true, y_pred)
        elif m == "r2":
            out[m] = r2(y_true, y_pred)
    return out


def compute_classification_metrics(
    *,
    y_true,
    y_pred,
    y_proba=None,
    metrics: Optional[Iterable[str]] = None,
) -> dict[str, float]:
    selected = list(metrics) if metrics is not None else ["accuracy", "f1", "roc_auc"]
    out: dict[str, float] = {}
    for m in selected:
        if m == "accuracy":
            out[m] = accuracy(y_true, y_pred)
        elif m == "f1":
            out[m] = f1_score(y_true, y_pred)
        elif m == "roc_auc" and y_proba is not None:
            val = roc_auc(y_true, y_proba)
            if val is not None:
                out[m] = val
    return out


# --- Trading metrics ---

def sharpe(returns, *, risk_free: float = 0.0) -> float:
    r = np.asarray(returns, dtype=float)
    ex = r - risk_free
    std = ex.std(ddof=0)
    if std == 0.0:
        return 0.0
    return float(ex.mean() / std)


def sortino(returns, *, risk_free: float = 0.0) -> float:
    r = np.asarray(returns, dtype=float)
    ex = r - risk_free
    downside = ex[ex < 0]
    denom = downside.std(ddof=0) if downside.size > 0 else 0.0
    if denom == 0.0:
        return 0.0
    return float(ex.mean() / denom)


def equity_curve(returns) -> np.ndarray:
    r = np.asarray(returns, dtype=float)
    return np.cumprod(1.0 + r)


def max_drawdown(returns) -> float:
    eq = equity_curve(returns)
    peak = np.maximum.accumulate(eq)
    dd = (eq / peak) - 1.0
    return float(dd.min())


def pnl(returns) -> float:
    r = np.asarray(returns, dtype=float)
    return float(r.sum())


def hit_rate(returns) -> float:
    r = np.asarray(returns, dtype=float)
    if r.size == 0:
        return 0.0
    return float((r > 0).mean())


def realized_returns_from_signals(
    *,
    y_true_returns,
    y_pred_returns,
    threshold: float = 0.0,
    fees_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> np.ndarray:
    """
    Build realized returns from predicted returns by taking the sign as position
    and applying transaction costs when position changes.
    """
    yt = np.asarray(y_true_returns, dtype=float)
    yp = np.asarray(y_pred_returns, dtype=float)
    # Positions in {-1, 0, +1}
    pos = np.where(yp > threshold, 1.0, np.where(yp < -threshold, -1.0, 0.0))
    # Trades when position changes
    trades = np.abs(np.diff(pos, prepend=0.0))
    cost_per_trade = (fees_bps + slippage_bps) / 10_000.0
    costs = trades * cost_per_trade
    realized = pos * yt - costs
    return realized


def compute_trading_metrics(
    *,
    y_true_returns,
    y_pred_returns,
    risk_free: float = 0.0,
    fees_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> dict[str, float]:
    rr = realized_returns_from_signals(
        y_true_returns=y_true_returns,
        y_pred_returns=y_pred_returns,
        fees_bps=fees_bps,
        slippage_bps=slippage_bps,
    )
    return {
        "sharpe": sharpe(rr, risk_free=risk_free),
        "sortino": sortino(rr, risk_free=risk_free),
        "max_drawdown": max_drawdown(rr),
        "pnl": pnl(rr),
        "hit_rate": hit_rate(rr),
    }
