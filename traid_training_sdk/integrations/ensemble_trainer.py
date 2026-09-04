from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping, cast

from typing import TYPE_CHECKING

from ..core.errors import ConfigurationError, NotAvailableSDK

if TYPE_CHECKING:  # pragma: no cover - import hints only
    from services.ml.ensemble_trainer.src.config.training_config import DirectionModelConfig  # type: ignore[import]


def _ensure_mapping(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if config is None:
        raise ConfigurationError("ensemble config must be provided")
    if not isinstance(config, Mapping):
        raise ConfigurationError("ensemble config must be a mapping")
    return config


def _metrics_to_dict(metrics: Any) -> dict[str, float]:
    if metrics is None:
        return {}
    raw: dict[str, Any]
    if hasattr(metrics, "model_dump") and callable(metrics.model_dump):  # pydantic v2 models
        raw = cast(dict[str, Any], metrics.model_dump())
    elif hasattr(metrics, "dict") and callable(metrics.dict):  # pydantic v1 compatibility
        raw = cast(dict[str, Any], metrics.dict())
    elif is_dataclass(metrics):
        raw = cast(dict[str, Any], asdict(metrics))  # type: ignore[arg-type]
    elif isinstance(metrics, Mapping):
        raw = dict(metrics)
    else:
        return {}
    result: dict[str, float] = {}
    for key, value in raw.items():
        if isinstance(value, (int, float)):
            result[str(key)] = float(value)
    return result


def _normalize_path_fields(config: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in config.items():
        if key.endswith("_path") or key.endswith("_dir"):
            if value is None:
                normalized[key] = value
            else:
                normalized[key] = str(Path(value).expanduser())
        else:
            normalized[key] = value
    return normalized


def train_direction(config: Mapping[str, Any]) -> dict[str, Any]:
    prepared_cfg = _normalize_path_fields(dict(_ensure_mapping(config)))
    try:
        from services.ml.ensemble_trainer.src.config.training_config import DirectionModelConfig  # type: ignore[import]
        from services.ml.ensemble_trainer.src.training.main import train_direction_model_with_mlflow_tracking  # type: ignore[import]
    except Exception as exc:  # pragma: no cover - optional dependency guard
        raise NotAvailableSDK(
            "ensemble-trainer service is not available. Install traid-training-sdk[ensemble] or add services/ml/ensemble-trainer to PYTHONPATH."
        ) from exc

    direction_cfg = DirectionModelConfig.model_validate(prepared_cfg)
    artifacts, run_id = train_direction_model_with_mlflow_tracking(direction_cfg)

    model_path = getattr(artifacts, "model_path", None)
    if not model_path:
        raise ConfigurationError("ensemble trainer returned empty model_path")

    feature_names = list(getattr(artifacts, "feature_names", []) or [])
    metrics = _metrics_to_dict(getattr(artifacts, "metrics", None))

    config_dump: dict[str, Any]
    raw_config = getattr(artifacts, "config", None)
    if raw_config is None:
        if hasattr(direction_cfg, "model_dump"):
            config_dump = direction_cfg.model_dump()
        else:  # pragma: no cover - fallback for unexpected versions
            config_dump = dict(prepared_cfg)
    elif isinstance(raw_config, Mapping):
        config_dump = dict(raw_config)
    else:
        try:
            config_dump = dict(raw_config)
        except Exception:  # pragma: no cover - defensive
            config_dump = {}

    return {
        "model_path": str(model_path),
        "feature_names": feature_names,
        "metrics": metrics,
        "config": config_dump,
        "training_time": getattr(artifacts, "training_time", None),
        "mlflow_run_id": run_id,
    }


__all__ = ["train_direction"]
