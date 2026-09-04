"""TS-FM probability adapters for direction prediction candidates.

The adapter lane is intentionally separate from tabular base learners: TS-FM
models consume raw time-series context windows and emit forecasts, while the
stacking trainer only consumes the resulting ``P(direction_up)`` column.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import numpy as np

TSFM_ADAPTER_ARTIFACT_TYPE = "tsfm_probability_adapter"
TSFM_ADAPTER_CONFIG_VERSION = "tsfm_probability_adapter.v1"
TSFM_DIRECTION_OUTPUT_NAME = "direction_proba"

_FORECAST_TYPES = {"point", "quantile"}
_NORMALIZATION_MODES = {"none", "zscore", "minmax", "model_native"}


class UnsupportedTsfmAdapterArtifactError(ValueError):
    """Raised when a TS-FM artifact cannot be loaded as a probability adapter."""


@dataclass
class TsfmAdapterConfig:
    """Serializable configuration for TS-FM direction probability conversion."""

    model_family: str
    forecast_type: str
    context_length: int
    horizon: int
    execution_lag: int = 0
    pct_threshold: Optional[float] = None
    quantile_levels: Optional[tuple[float, ...]] = None
    target_column: str = "close"
    target_feature_index: int = -1
    normalization_mode: str = "none"
    normalization_params: dict[str, float] = field(default_factory=dict)
    point_probability_scale: float = 0.01
    fallback_probability: float = 0.5
    clip_epsilon: float = 1e-6
    enforce_monotonic_quantiles: bool = True
    adapter_version: str = TSFM_ADAPTER_CONFIG_VERSION
    direction_output_name: str = TSFM_DIRECTION_OUTPUT_NAME
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.forecast_type = str(self.forecast_type).lower()
        self.normalization_mode = str(self.normalization_mode).lower()
        if self.adapter_version != TSFM_ADAPTER_CONFIG_VERSION:
            raise UnsupportedTsfmAdapterArtifactError(
                f"Unsupported TS-FM adapter config version {self.adapter_version!r}; "
                f"expected {TSFM_ADAPTER_CONFIG_VERSION!r}"
            )
        if self.forecast_type not in _FORECAST_TYPES:
            raise ValueError(f"forecast_type must be one of {sorted(_FORECAST_TYPES)}")
        if int(self.context_length) < 1:
            raise ValueError("context_length must be >= 1")
        if int(self.horizon) < 1:
            raise ValueError("horizon must be >= 1")
        if int(self.execution_lag) < 0:
            raise ValueError("execution_lag must be >= 0")
        if self.pct_threshold is not None and float(self.pct_threshold) < 0:
            raise ValueError("pct_threshold must be >= 0 when provided")
        if self.normalization_mode not in _NORMALIZATION_MODES:
            raise ValueError(
                f"normalization_mode must be one of {sorted(_NORMALIZATION_MODES)}"
            )
        if not (0.0 < float(self.point_probability_scale)):
            raise ValueError("point_probability_scale must be positive")
        if not (0.0 <= float(self.fallback_probability) <= 1.0):
            raise ValueError("fallback_probability must be within [0, 1]")
        if not (0.0 <= float(self.clip_epsilon) < 0.5):
            raise ValueError("clip_epsilon must be in [0, 0.5)")
        if self.direction_output_name != TSFM_DIRECTION_OUTPUT_NAME:
            raise ValueError(
                f"direction_output_name must remain {TSFM_DIRECTION_OUTPUT_NAME!r}"
            )
        if self.quantile_levels is not None:
            self.quantile_levels = _normalize_quantile_levels(self.quantile_levels)
        if self.forecast_type == "quantile" and not self.quantile_levels:
            raise ValueError("quantile_levels are required for quantile TS-FM adapters")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.quantile_levels is not None:
            data["quantile_levels"] = list(self.quantile_levels)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TsfmAdapterConfig":
        payload = dict(data)
        if payload.get("quantile_levels") is not None:
            payload["quantile_levels"] = tuple(float(q) for q in payload["quantile_levels"])
        return cls(**payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, raw: str) -> "TsfmAdapterConfig":
        return cls.from_dict(json.loads(raw))

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def read_json(cls, path: str | Path) -> "TsfmAdapterConfig":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def _normalize_quantile_levels(levels: Sequence[float]) -> tuple[float, ...]:
    normalized = tuple(float(level) for level in levels)
    if len(normalized) == 0:
        raise ValueError("quantile_levels must not be empty")
    if any(not np.isfinite(level) or level <= 0.0 or level >= 1.0 for level in normalized):
        raise ValueError("quantile levels must be finite values in (0, 1)")
    if tuple(sorted(normalized)) != normalized:
        raise ValueError("quantile levels must be sorted ascending")
    if len(set(normalized)) != len(normalized):
        raise ValueError("quantile levels must be unique")
    return normalized


def _clip_probability(values: np.ndarray | float, config: TsfmAdapterConfig) -> np.ndarray:
    return np.clip(
        np.asarray(values, dtype=np.float64),
        float(config.clip_epsilon),
        1.0 - float(config.clip_epsilon),
    )


def _fallback_array(size: int, config: TsfmAdapterConfig) -> np.ndarray:
    return _clip_probability(np.full(size, float(config.fallback_probability)), config)


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _threshold_return(config: TsfmAdapterConfig) -> float:
    return 0.0 if config.pct_threshold is None else float(config.pct_threshold)


def _as_1d(name: str, values: Any) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D array")
    return arr


def point_forecast_to_direction_probability(
    *,
    entry_price: Any,
    point_forecast: Any,
    config: TsfmAdapterConfig,
    calibrator: Any = None,
) -> np.ndarray:
    """Convert point forecasts to calibrated ``P(direction_up)`` values.

    The comparison mirrors ``build_direction_label``: the future forecast is
    compared with the execution entry price, then ``pct_threshold`` is applied
    to the forward return. Invalid rows fall back to ``fallback_probability``.
    """

    entries = _as_1d("entry_price", entry_price)
    forecasts = _as_1d("point_forecast", point_forecast)
    if len(entries) != len(forecasts):
        raise ValueError("entry_price and point_forecast must have the same length")

    out = _fallback_array(len(entries), config)
    valid = np.isfinite(entries) & np.isfinite(forecasts) & (entries != 0.0)
    if np.any(valid):
        forward_return = (forecasts[valid] - entries[valid]) / np.abs(entries[valid])
        margin = forward_return - _threshold_return(config)
        raw = _sigmoid(margin / float(config.point_probability_scale))
        out[valid] = raw

    out = _apply_probability_calibrator(out, calibrator)
    return _clip_probability(out, config)


def _apply_probability_calibrator(probabilities: np.ndarray, calibrator: Any) -> np.ndarray:
    if calibrator is None:
        return probabilities
    try:
        if hasattr(calibrator, "transform"):
            calibrated = calibrator.transform(probabilities)
        elif hasattr(calibrator, "predict_proba"):
            calibrated = calibrator.predict_proba(probabilities.reshape(-1, 1))[:, 1]
        else:
            return probabilities
        calibrated = np.asarray(calibrated, dtype=np.float64)
        if calibrated.shape != probabilities.shape or not np.all(np.isfinite(calibrated)):
            return probabilities
        return calibrated
    except Exception:
        return probabilities


def _quantile_probability_one(
    *,
    entry_price: float,
    quantile_values: np.ndarray,
    quantile_levels: tuple[float, ...],
    config: TsfmAdapterConfig,
) -> float:
    if not np.isfinite(entry_price) or entry_price == 0.0:
        return float(config.fallback_probability)
    if quantile_values.shape != (len(quantile_levels),):
        raise ValueError("quantile forecast row length must match quantile levels")
    if not np.all(np.isfinite(quantile_values)):
        return float(config.fallback_probability)

    values = np.asarray(quantile_values, dtype=np.float64)
    if np.any(np.diff(values) < 0.0):
        if not config.enforce_monotonic_quantiles:
            raise ValueError("quantile forecasts must be monotonic")
        values = np.maximum.accumulate(values)

    threshold_price = float(entry_price) * (1.0 + _threshold_return(config))
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    sorted_levels = np.asarray(quantile_levels, dtype=np.float64)[order]

    collapsed_values: list[float] = []
    collapsed_levels: list[float] = []
    for value, level in zip(sorted_values, sorted_levels, strict=False):
        if collapsed_values and np.isclose(value, collapsed_values[-1], rtol=0.0, atol=1e-12):
            collapsed_levels[-1] = max(collapsed_levels[-1], float(level))
        else:
            collapsed_values.append(float(value))
            collapsed_levels.append(float(level))

    x = np.asarray(collapsed_values, dtype=np.float64)
    y = np.asarray(collapsed_levels, dtype=np.float64)
    if len(x) == 1:
        cdf = y[0]
    elif threshold_price <= x[0]:
        cdf = y[0]
    elif threshold_price >= x[-1]:
        cdf = y[-1]
    else:
        cdf = float(np.interp(threshold_price, x, y))
    return 1.0 - cdf


def quantile_forecast_to_direction_probability(
    *,
    entry_price: Any,
    quantile_forecasts: Any,
    config: TsfmAdapterConfig,
    quantile_levels: Optional[Sequence[float]] = None,
    calibrator: Any = None,
) -> np.ndarray:
    """Convert quantile forecasts to ``P(direction_up)`` values."""

    entries = _as_1d("entry_price", entry_price)
    levels = (
        _normalize_quantile_levels(quantile_levels)
        if quantile_levels is not None
        else config.quantile_levels
    )
    if not levels:
        raise ValueError("quantile_levels are required")
    q_matrix = np.asarray(quantile_forecasts, dtype=np.float64)
    if q_matrix.ndim == 1:
        q_matrix = q_matrix.reshape(1, -1)
    if q_matrix.ndim != 2:
        raise ValueError("quantile_forecasts must be a 2D array")
    if q_matrix.shape != (len(entries), len(levels)):
        raise ValueError(
            "quantile_forecasts shape must be (n_samples, n_quantiles); "
            f"got {q_matrix.shape}, expected {(len(entries), len(levels))}"
        )

    out = np.array(
        [
            _quantile_probability_one(
                entry_price=float(entry),
                quantile_values=q_row,
                quantile_levels=levels,
                config=config,
            )
            for entry, q_row in zip(entries, q_matrix, strict=True)
        ],
        dtype=np.float64,
    )
    out = _apply_probability_calibrator(out, calibrator)
    return _clip_probability(out, config)


def _target_values(context: Any, config: TsfmAdapterConfig) -> np.ndarray:
    if hasattr(context, "columns"):
        if config.target_column in context.columns:
            return np.asarray(context[config.target_column], dtype=np.float64)
        return np.asarray(context.iloc[:, config.target_feature_index], dtype=np.float64)

    arr = np.asarray(context, dtype=np.float64)
    if arr.ndim == 3:
        if arr.shape[1] != int(config.context_length):
            raise ValueError(
                f"TS-FM context length {arr.shape[1]} does not match "
                f"config context_length {config.context_length}"
            )
        return arr[:, -1, config.target_feature_index]
    if arr.ndim == 2:
        return arr[:, config.target_feature_index]
    if arr.ndim == 1:
        return arr.reshape(1, -1)[:, config.target_feature_index]
    raise ValueError(f"Unsupported TS-FM context shape {arr.shape}")


def _normalize_context(context: Any, config: TsfmAdapterConfig) -> Any:
    if config.normalization_mode in {"none", "model_native"}:
        return context
    arr = np.asarray(context, dtype=np.float64)
    if config.normalization_mode == "zscore":
        mean = float(config.normalization_params.get("mean", np.nanmean(arr)))
        std = float(config.normalization_params.get("std", np.nanstd(arr) or 1.0))
        std = std if std != 0.0 else 1.0
        return (arr - mean) / std
    if config.normalization_mode == "minmax":
        min_value = float(config.normalization_params.get("min", np.nanmin(arr)))
        max_value = float(config.normalization_params.get("max", np.nanmax(arr)))
        span = max(max_value - min_value, 1e-12)
        return (arr - min_value) / span
    return context


def _call_forecast_model(model: Any, context: Any, config: TsfmAdapterConfig) -> Any:
    method_names = (
        ("predict_quantiles", "forecast_quantiles", "predict")
        if config.forecast_type == "quantile"
        else ("predict_point", "forecast", "predict")
    )
    for method_name in method_names:
        method = getattr(model, method_name, None)
        if callable(method):
            if config.forecast_type == "quantile" and method_name != "predict":
                try:
                    return method(context, quantile_levels=config.quantile_levels)
                except TypeError:
                    return method(context)
            return method(context)
    if callable(model):
        return model(context)
    raise UnsupportedTsfmAdapterArtifactError(
        f"TS-FM forecast model {type(model).__name__!r} does not expose a "
        f"{config.forecast_type} forecast method"
    )


def _select_point_forecast_path(
    forecasts: Any,
    config: TsfmAdapterConfig,
) -> tuple[np.ndarray, Optional[np.ndarray]]:
    arr = np.asarray(forecasts, dtype=np.float64)
    future_step = int(config.execution_lag) + int(config.horizon) - 1
    entry_step = int(config.execution_lag) - 1
    if arr.ndim == 1:
        return arr, None
    if arr.ndim != 2:
        raise ValueError("point forecasts must be a 1D array or 2D forecast path")
    if arr.shape[1] <= future_step:
        raise ValueError(
            f"point forecast path has {arr.shape[1]} steps; needs step {future_step}"
        )
    future = arr[:, future_step]
    entry = arr[:, entry_step] if entry_step >= 0 else None
    return future, entry


def _select_quantile_forecast_path(
    forecasts: Any,
    config: TsfmAdapterConfig,
) -> tuple[np.ndarray, Optional[np.ndarray]]:
    arr = np.asarray(forecasts, dtype=np.float64)
    future_step = int(config.execution_lag) + int(config.horizon) - 1
    entry_step = int(config.execution_lag) - 1
    if arr.ndim == 2:
        return arr, None
    if arr.ndim != 3:
        raise ValueError("quantile forecasts must be a 2D matrix or 3D forecast path")
    if arr.shape[1] <= future_step:
        raise ValueError(
            f"quantile forecast path has {arr.shape[1]} steps; needs step {future_step}"
        )
    future = arr[:, future_step, :]
    entry = None
    if entry_step >= 0:
        levels = config.quantile_levels or ()
        median_idx = int(np.argmin(np.abs(np.asarray(levels, dtype=np.float64) - 0.5)))
        entry = arr[:, entry_step, median_idx]
    return future, entry


class TsfmProbabilityAdapter:
    """Sklearn-like wrapper that exposes TS-FM forecasts as ``predict_proba``."""

    def __init__(
        self,
        forecast_model: Any,
        config: TsfmAdapterConfig | Mapping[str, Any],
        calibrator: Any = None,
    ) -> None:
        self.forecast_model = forecast_model
        self.config = (
            config
            if isinstance(config, TsfmAdapterConfig)
            else TsfmAdapterConfig.from_dict(config)
        )
        self.calibrator = calibrator
        self.classes_ = np.array([0, 1], dtype=int)
        self._fitted = False

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        return {
            "forecast_model": self.forecast_model,
            "config": self.config,
            "calibrator": self.calibrator,
        }

    def set_params(self, **params: Any) -> "TsfmProbabilityAdapter":
        for key, value in params.items():
            setattr(self, key, value)
        return self

    def fit(
        self,
        X: Any,
        y: Any = None,
        sample_weight: Optional[np.ndarray] = None,
    ) -> "TsfmProbabilityAdapter":
        if hasattr(self.forecast_model, "fit"):
            try:
                self.forecast_model.fit(X, y, sample_weight=sample_weight)
            except TypeError:
                self.forecast_model.fit(X, y)
        self._fitted = True
        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        context = _normalize_context(X, self.config)
        observed_entry = _target_values(X, self.config)
        forecasts = _call_forecast_model(self.forecast_model, context, self.config)

        if self.config.forecast_type == "point":
            future, forecast_entry = _select_point_forecast_path(forecasts, self.config)
            entry = forecast_entry if forecast_entry is not None else observed_entry
            proba = point_forecast_to_direction_probability(
                entry_price=entry,
                point_forecast=future,
                config=self.config,
                calibrator=self.calibrator,
            )
        else:
            future_quantiles, forecast_entry = _select_quantile_forecast_path(
                forecasts,
                self.config,
            )
            entry = forecast_entry if forecast_entry is not None else observed_entry
            proba = quantile_forecast_to_direction_probability(
                entry_price=entry,
                quantile_forecasts=future_quantiles,
                config=self.config,
                calibrator=self.calibrator,
            )
        return np.column_stack([1.0 - proba, proba])

    def predict(self, X: Any) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)

    def get_tsfm_metadata(self) -> dict[str, Any]:
        return {
            "artifact_type": TSFM_ADAPTER_ARTIFACT_TYPE,
            "adapter_config": self.config.to_dict(),
            "model_family": self.config.model_family,
            "forecast_type": self.config.forecast_type,
            "direction_output_name": self.config.direction_output_name,
            "normalization_mode": self.config.normalization_mode,
        }

    def to_artifact(self) -> dict[str, Any]:
        return {
            "artifact_type": TSFM_ADAPTER_ARTIFACT_TYPE,
            "adapter_config": self.config.to_dict(),
            "forecast_model": self.forecast_model,
            "calibrator": self.calibrator,
        }

    @classmethod
    def from_artifact(cls, artifact: Any) -> "TsfmProbabilityAdapter":
        return build_tsfm_adapter_from_artifact(artifact)


def is_tsfm_adapter_artifact(obj: Any) -> bool:
    if isinstance(obj, TsfmProbabilityAdapter):
        return True
    if isinstance(obj, Mapping):
        return obj.get("artifact_type") == TSFM_ADAPTER_ARTIFACT_TYPE
    get_metadata = getattr(obj, "get_tsfm_metadata", None)
    if not callable(get_metadata) or not hasattr(obj, "predict_proba"):
        return False
    try:
        metadata = get_metadata()
    except Exception:
        return False
    return (
        isinstance(metadata, Mapping)
        and metadata.get("artifact_type") == TSFM_ADAPTER_ARTIFACT_TYPE
    )


def build_tsfm_adapter_from_artifact(artifact: Any) -> TsfmProbabilityAdapter:
    """Load a TS-FM probability adapter from a supported artifact object."""

    if isinstance(artifact, TsfmProbabilityAdapter):
        return artifact
    if hasattr(artifact, "predict_proba") and hasattr(artifact, "get_tsfm_metadata"):
        return artifact
    if not isinstance(artifact, Mapping):
        raise UnsupportedTsfmAdapterArtifactError(
            f"Unsupported TS-FM adapter artifact type {type(artifact).__name__!r}"
        )
    if artifact.get("artifact_type") != TSFM_ADAPTER_ARTIFACT_TYPE:
        raise UnsupportedTsfmAdapterArtifactError(
            "Unsupported TS-FM adapter artifact: expected artifact_type "
            f"{TSFM_ADAPTER_ARTIFACT_TYPE!r}"
        )
    config_payload = artifact.get("adapter_config") or artifact.get("config")
    if not isinstance(config_payload, Mapping):
        raise UnsupportedTsfmAdapterArtifactError(
            "TS-FM adapter artifact is missing serializable adapter_config"
        )
    forecast_model = (
        artifact["forecast_model"]
        if "forecast_model" in artifact
        else artifact.get("model")
    )
    if forecast_model is None:
        raise UnsupportedTsfmAdapterArtifactError(
            "TS-FM adapter artifact is missing forecast_model"
        )
    return TsfmProbabilityAdapter(
        forecast_model=forecast_model,
        config=TsfmAdapterConfig.from_dict(config_payload),
        calibrator=artifact.get("calibrator"),
    )


__all__ = [
    "TSFM_ADAPTER_ARTIFACT_TYPE",
    "TSFM_ADAPTER_CONFIG_VERSION",
    "TSFM_DIRECTION_OUTPUT_NAME",
    "TsfmAdapterConfig",
    "TsfmProbabilityAdapter",
    "UnsupportedTsfmAdapterArtifactError",
    "build_tsfm_adapter_from_artifact",
    "is_tsfm_adapter_artifact",
    "point_forecast_to_direction_probability",
    "quantile_forecast_to_direction_probability",
]
