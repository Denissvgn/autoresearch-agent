from __future__ import annotations

from typing import Any, Dict


def derive_models_uri(name: str, version: int) -> str:
    return f"models:/{name}/{int(version)}"


def validate_composite_manifest(payload: Dict[str, Any]) -> None:
    required_top = ["instrument", "timeframe", "initial_balance", "components"]
    for key in required_top:
        if key not in payload:
            raise ValueError(f"Missing required key: {key}")
    comps = payload["components"]
    if not isinstance(comps, dict) or not comps:
        raise ValueError("components must be a non-empty dict")
    for name, comp in comps.items():
        if "model_name" not in comp or "version" not in comp:
            raise ValueError(f"Component {name} missing model_name/version")
        model_name = comp["model_name"]
        version = comp["version"]
        if not isinstance(model_name, str) or not model_name:
            raise ValueError(f"Component {name} has invalid model_name")
        if not isinstance(version, int) or version <= 0:
            raise ValueError(f"Component {name} has invalid version")
        _ = derive_models_uri(model_name, version)  # build to validate
        if "model_uri" in comp:
            uri = comp["model_uri"]
            if not isinstance(uri, str) or not uri:
                raise ValueError(f"Component {name} has invalid model_uri")


def validate_unified_model(model: Any) -> None:
    pipeline_model = hasattr(model, "model") and hasattr(getattr(model, "model"), "feature_gen")
    if not pipeline_model:
        if not hasattr(model, "features") or not isinstance(model.features, list) or not model.features:
            raise ValueError("Unified model must define a non-empty list of features")
        if not all(isinstance(item, str) and item for item in model.features):
            raise ValueError("Unified model features must be non-empty strings")
    else:
        # Pipelines encapsulate feature generation; feature list optional for metadata
        if hasattr(model, "features") and model.features:
            if not all(isinstance(item, str) and item for item in model.features):
                raise ValueError("Unified model features must be non-empty strings when provided")
    if not hasattr(model, "instrument") or not isinstance(model.instrument, str) or not model.instrument:
        raise ValueError("Unified model must define instrument string")
    if not hasattr(model, "timeframe") or not isinstance(model.timeframe, str) or not model.timeframe:
        raise ValueError("Unified model must define timeframe string")
    if not hasattr(model, "metrics") or not isinstance(model.metrics, dict):
        raise ValueError("Unified model must expose metrics dict")
    for key, value in model.metrics.items():
        if not isinstance(key, str):
            raise ValueError("Unified model metric names must be strings")
        if not isinstance(value, (int, float)):
            raise ValueError("Unified model metric values must be numeric")
    if not hasattr(model, "model"):
        raise ValueError("Unified model must carry underlying model instance")
    underlying = getattr(model, "model")
    if not hasattr(underlying, "predict"):
        raise ValueError("Underlying model must implement predict()")
