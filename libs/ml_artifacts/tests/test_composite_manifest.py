from __future__ import annotations

from ml_artifacts.composite import normalize_component_refs


def test_normalize_component_refs_accepts_nested_trainer_manifest():
    manifest = {
        "components": {
            "direction": {"model_name": "dir_model", "version": "12"},
            "volatility": {"model_name": "vol_model", "version": "3"},
            "rl": {"model_name": "rl_agent", "version": "Production"},
        }
    }

    assert normalize_component_refs(manifest) == {
        "direction": "dir_model:12",
        "volatility": "vol_model:3",
        "rl_agent": "rl_agent:Production",
    }


def test_normalize_component_refs_accepts_flat_inference_manifest():
    manifest = {
        "direction_model_version": "dir_model:12",
        "volatility_model_version": "vol_model:3",
        "rl_model_version": "rl_agent:Production",
    }

    assert normalize_component_refs(manifest) == {
        "direction": "dir_model:12",
        "volatility": "vol_model:3",
        "rl_agent": "rl_agent:Production",
    }
