"""Canonical VDMC wave-function feature generation.

This module is the shared train/serve integration point for ``vdmc_core``.
It intentionally does not implement the legacy MACD-style proxy named VDMC in
older services.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import numpy as np
import pandas as pd


VDMC_FEATURE_COLUMNS = (
    "vdmc_buy_proba",
    "vdmc_sell_proba",
    "vdmc_momentum",
    "vdmc_amplitude",
    "vdmc_signal_strength",
    "vdmc_trend_signal",
    "vdmc_reversal_signal",
    "vdmc_neutral_signal",
    "vdmc_has_warning",
)

VDMC_PARAMS_HASH_VARIANT = "vdmc_core_wave.serving_params.v1"

_VDMC_PARAM_ALIASES: dict[str, tuple[str, ...]] = {
    "lookback_period": ("vdmc_lookback_period", "lookback_period", "lookback"),
    "alpha": ("vdmc_alpha", "alpha"),
    "beta": ("vdmc_beta", "beta"),
    "kernel_sigma": ("vdmc_kernel_sigma", "kernel_sigma"),
    "smoothing_factor": ("vdmc_smoothing_factor", "smoothing_factor"),
    "amplitude_scaling": ("vdmc_amplitude_scaling", "amplitude_scaling"),
}

_VDMC_ALIAS_TO_CANONICAL = {
    alias: canonical
    for canonical, aliases in _VDMC_PARAM_ALIASES.items()
    for alias in aliases
}


def canonical_vdmc_params(config: Any | None = None, **overrides: Any) -> dict[str, Any]:
    """Return the canonical, hashable VDMC serving-parameter payload.

    Accepts both feature-service ``FeatureConfig`` keys (``vdmc_alpha``) and
    trainer ``VDMCConfig`` keys (``alpha``). ``signal_type`` is intentionally
    omitted because feature-service emits both buy and sell VDMC feature lanes.
    """
    params = {
        "variant": "vdmc_core_wave",
        "lookback_period": int(_get_any(config, "lookback_period", 120)),
        "alpha": float(_get_any(config, "alpha", 1.2)),
        "beta": float(_get_any(config, "beta", 0.8)),
        "kernel_sigma": int(_get_any(config, "kernel_sigma", 5)),
        "smoothing_factor": float(_get_any(config, "smoothing_factor", 0.3)),
        "amplitude_scaling": float(_get_any(config, "amplitude_scaling", 1.0)),
    }
    for key, value in overrides.items():
        if value is not None:
            canonical_key = _VDMC_ALIAS_TO_CANONICAL.get(key, key)
            if canonical_key in ("signal_type", "vdmc_signal_type"):
                continue
            if canonical_key in ("lookback_period", "kernel_sigma"):
                params[canonical_key] = int(value)
            elif canonical_key in ("alpha", "beta", "smoothing_factor", "amplitude_scaling"):
                params[canonical_key] = float(value)
            else:
                params[canonical_key] = value
    return params


def compute_vdmc_params_hash(params: Mapping[str, Any] | None) -> str | None:
    """Compute the stable SHA-256 hash used by model metadata checks."""
    if not params:
        return None
    canonical = json.dumps(
        dict(params),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def calculate_vdmc_indicators(
    data: pd.DataFrame | pd.Series | np.ndarray | list[float],
    *,
    lookback_period: int = 120,
    alpha: float = 1.2,
    beta: float = 0.8,
    kernel_sigma: int = 5,
    smoothing_factor: float = 0.3,
    amplitude_scaling: float = 1.0,
    close_col: str = "close",
) -> dict[str, np.ndarray]:
    """Calculate canonical rolling VDMC feature arrays.

    The rolling behavior matches the ensemble-trainer enrichment path:
    rows before ``lookback_period`` are neutral short-history rows, and each
    computed row uses the trailing ``lookback_period`` bars plus the current
    row.
    """
    close_prices = _as_close_array(data, close_col=close_col)
    n_rows = len(close_prices)

    buy_proba = np.full(n_rows, 0.5, dtype=np.float64)
    sell_proba = np.full(n_rows, 0.5, dtype=np.float64)
    momentum = np.zeros(n_rows, dtype=np.float64)
    amplitude = np.zeros(n_rows, dtype=np.float64)
    warning = np.full(n_rows, 1002, dtype=np.int64)

    if n_rows == 0:
        return _derive_arrays(buy_proba, sell_proba, momentum, amplitude, warning)

    try:
        from vdmc_core import SignalType
        from vdmc_core.factored import apply_sigmoid, compute_intermediates, derive_vdmc_features
    except ImportError as exc:  # pragma: no cover - exercised in service import checks
        raise ImportError(
            "vdmc_core is required for canonical VDMC features. "
            "Install libs/vdmc_core or disable vdmc_enabled."
        ) from exc

    for idx in range(lookback_period, n_rows):
        window = close_prices[max(0, idx - lookback_period): idx + 1]
        try:
            intermediates = compute_intermediates(
                window,
                kernel_sigma=kernel_sigma,
                lookback_period=lookback_period,
                smoothing_factor=smoothing_factor,
                amplitude_scaling=amplitude_scaling,
            )
            buy_output = apply_sigmoid(
                intermediates,
                alpha=alpha,
                beta=beta,
                signal_type=SignalType.BUY,
            )
            sell_output = apply_sigmoid(
                intermediates,
                alpha=alpha,
                beta=beta,
                signal_type=SignalType.SELL,
            )
            row_features = derive_vdmc_features(buy_output, sell_output)
            buy_proba[idx] = row_features["vdmc_buy_proba"]
            sell_proba[idx] = row_features["vdmc_sell_proba"]
            momentum[idx] = row_features["vdmc_momentum"]
            amplitude[idx] = row_features["vdmc_amplitude"]
            warning[idx] = buy_output.warning_code or sell_output.warning_code or 0
        except Exception:
            buy_proba[idx] = 0.5
            sell_proba[idx] = 0.5
            momentum[idx] = 0.0
            amplitude[idx] = 0.0
            warning[idx] = 1001

    return _derive_arrays(buy_proba, sell_proba, momentum, amplitude, warning)


def _derive_arrays(
    buy_proba: np.ndarray,
    sell_proba: np.ndarray,
    momentum: np.ndarray,
    amplitude: np.ndarray,
    warning: np.ndarray,
) -> dict[str, np.ndarray]:
    return {
        "vdmc_buy_proba": buy_proba,
        "vdmc_sell_proba": sell_proba,
        "vdmc_momentum": momentum,
        "vdmc_amplitude": amplitude,
        "vdmc_signal_strength": np.abs(buy_proba - 0.5) * 2.0,
        "vdmc_trend_signal": (buy_proba > 0.6).astype(np.int64),
        "vdmc_reversal_signal": (sell_proba > 0.6).astype(np.int64),
        "vdmc_neutral_signal": ((buy_proba >= 0.4) & (buy_proba <= 0.6)).astype(np.int64),
        "vdmc_has_warning": (warning > 0).astype(np.int64),
    }


def _as_close_array(
    data: pd.DataFrame | pd.Series | np.ndarray | list[float],
    *,
    close_col: str,
) -> np.ndarray:
    if isinstance(data, pd.DataFrame):
        if close_col not in data.columns:
            raise ValueError(f"DataFrame must contain close column {close_col!r}")
        values = data[close_col]
    elif isinstance(data, pd.Series):
        values = data
    else:
        values = data
    return np.asarray(values, dtype=np.float64)


def _get(config: Any | None, key: str, default: Any) -> Any:
    if config is None:
        return default
    if isinstance(config, Mapping):
        return config.get(key, default)
    return getattr(config, key, default)


def _get_any(config: Any | None, canonical_key: str, default: Any) -> Any:
    for alias in _VDMC_PARAM_ALIASES[canonical_key]:
        value = _get(config, alias, None)
        if value is not None:
            return value
    return default
