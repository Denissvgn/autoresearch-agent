from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple


ObjectiveMode = Literal["min", "max"]


_OBJECTIVES: dict[str, tuple[str, ObjectiveMode]] = {
    "rmse": ("rmse", "min"),
    "mae": ("mae", "min"),
    "r2": ("r2", "max"),
    "accuracy": ("accuracy", "max"),
    "f1": ("f1", "max"),
    "auc": ("roc_auc", "max"),
    # Trading metrics
    "sharpe": ("sharpe", "max"),
    "sortino": ("sortino", "max"),
    "max_drawdown": ("max_drawdown", "min"),
    "pnl": ("pnl", "max"),
}


def resolve_objective(name: str | None) -> tuple[str, ObjectiveMode]:
    if not name:
        return _OBJECTIVES["rmse"]
    key = name.strip().lower()
    if key in _OBJECTIVES:
        return _OBJECTIVES[key]
    # Allow aliases
    aliases = {"auc": "auc", "roc_auc": "auc", "f-1": "f1"}
    if key in aliases:
        return _OBJECTIVES[aliases[key]]
    # Fallback
    return _OBJECTIVES["rmse"]
