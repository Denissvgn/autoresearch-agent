from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..core.errors import ConfigurationError, NotAvailableSDK

_REQUIRED_PATH_KEYS = {"enriched_data_path"}
_REQUIRED_STRING_KEYS = {"strategy"}
_OPTIONAL_PATH_KEYS = {"warm_start_path"}


def _ensure_mapping(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(config, Mapping):
        raise ConfigurationError("rl_config must be a mapping")
    return config


def _normalize_path(value: Any, *, key: str, must_exist: bool) -> str:
    if not value:
        raise ConfigurationError(f"rl_config.{key} cannot be empty")
    path = Path(value).expanduser()
    if must_exist and not path.exists():
        raise ConfigurationError(f"rl_config.{key} does not exist: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def _validated_config(config: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = dict(config)

    missing = [key for key in _REQUIRED_PATH_KEYS if not normalized.get(key)]
    missing += [key for key in _REQUIRED_STRING_KEYS if not normalized.get(key)]
    if missing:
        raise ConfigurationError(f"rl_config missing required fields: {', '.join(sorted(missing))}")

    for key in _REQUIRED_PATH_KEYS:
        normalized[key] = _normalize_path(normalized[key], key=key, must_exist=True)

    output_dir = normalized.get("output_dir")
    if not output_dir:
        raise ConfigurationError("rl_config.output_dir is required")
    normalized["output_dir"] = _normalize_path(output_dir, key="output_dir", must_exist=False)

    for key in _OPTIONAL_PATH_KEYS:
        if key in normalized and normalized[key]:
            normalized[key] = _normalize_path(normalized[key], key=key, must_exist=True)

    return normalized


def train_rl_agent(config: Mapping[str, Any]) -> dict[str, Any]:
    prepared = _validated_config(_ensure_mapping(config))
    try:
        from services.ml.rl_trainer.src.config.rl_config import RLTrainingConfig
        from services.ml.rl_trainer.src.training.train_rl_agent import RLTrainer
    except Exception as exc:  # pragma: no cover - optional dependency guard
        raise NotAvailableSDK(
            "rl-trainer service is not available. Install traid-training-sdk[rl] or add services/ml/rl-trainer to PYTHONPATH."
        ) from exc

    rl_config = RLTrainingConfig(**prepared)
    trainer = RLTrainer(rl_config)
    artifacts = trainer.train()
    model_path = Path(artifacts.model_path)
    if not model_path.exists():  # pragma: no cover - defensive guard
        raise ConfigurationError(f"RL trainer returned missing model artifact: {model_path}")
    return {
        "model_path": str(model_path),
        "evaluation_results": artifacts.evaluation_results,
        "training_time": getattr(artifacts, "training_time", None),
        "config": prepared,
    }


__all__ = ["train_rl_agent"]
