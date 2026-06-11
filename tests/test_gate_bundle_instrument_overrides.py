"""MQ-C1 — per-instrument gate-bundle threshold overrides.

Pins:
1. ``apply_instrument_gate_overrides`` deep-merges the instrument config's
   ``gates_overrides`` {tier: {check: value}} into a COPY of the bundle with
   from→to provenance; the original bundle is untouched.
2. Missing config / missing block / malformed YAML → bundle returned unchanged.
3. The overridden threshold is actually USED by the evaluator (a direction
   iteration failing the global min_direction_auc passes under a per-instrument
   floor), and the evaluation result records ``instrument_gate_overrides``.
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import yaml

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

try:  # the orchestrator imports Anthropic SDK at module load
    import anthropic  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover — slim test envs only
    _stub = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = _stub

from src.core.development_gate_bundle import (  # noqa: E402
    apply_instrument_gate_overrides,
    evaluate_development_gate_bundle,
)


def _write_instrument_config(root: Path, key: str, gates_overrides: dict) -> None:
    cfg_dir = root / "configs" / "instrument_configs"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / f"{key}.yaml").write_text(
        yaml.dump(
            {
                "instrument": key.rsplit("_", 1)[0],
                "timeframe": key.rsplit("_", 1)[1],
                "direction_overrides": {},
                "gates_overrides": gates_overrides,
            }
        )
    )


def _bundle() -> dict:
    return {
        "gate_bundle_id": "test_bundle",
        "version": 1,
        "scope": "development",
        "promotion_policy": {
            "auc_only_promotion_allowed": False,
            "live_production_promotion_allowed": False,
        },
        "gate_tiers": {
            "direction_quality": {"checks": {"min_direction_auc": 0.55}},
        },
    }


def test_overrides_merge_with_provenance(tmp_path: Path) -> None:
    _write_instrument_config(
        tmp_path, "NOISY_USDT_15m",
        {"direction_quality": {"min_direction_auc": 0.52}},
    )
    original = _bundle()
    patched = apply_instrument_gate_overrides(
        original, instrument="NOISY_USDT", timeframe="15m", workspace_root=tmp_path,
    )
    assert patched is not original
    assert patched["gate_tiers"]["direction_quality"]["checks"]["min_direction_auc"] == 0.52
    # Original untouched
    assert original["gate_tiers"]["direction_quality"]["checks"]["min_direction_auc"] == 0.55
    prov = patched["instrument_gate_overrides"]
    assert prov["instrument"] == "NOISY_USDT"
    assert prov["applied"]["direction_quality"]["min_direction_auc"] == {
        "from": 0.55, "to": 0.52,
    }


def test_missing_config_returns_bundle_unchanged(tmp_path: Path) -> None:
    bundle = _bundle()
    assert apply_instrument_gate_overrides(
        bundle, instrument="GHOST_USDT", timeframe="15m", workspace_root=tmp_path,
    ) is bundle


def test_config_without_block_returns_bundle_unchanged(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "configs" / "instrument_configs"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "PLAIN_USDT_15m.yaml").write_text(
        yaml.dump({"instrument": "PLAIN_USDT", "timeframe": "15m"})
    )
    bundle = _bundle()
    assert apply_instrument_gate_overrides(
        bundle, instrument="PLAIN_USDT", timeframe="15m", workspace_root=tmp_path,
    ) is bundle


def _direction_iteration(auc: float) -> dict:
    payload = {
        "gate_results": {
            "all_supported_gates_passed": True,
            "direction_auc": auc,
            "operating_signal_rate": 0.20,
        },
        "metrics": {"auc": auc},
        "config": {},
    }
    return {"metrics_json": json.dumps(payload)}


def _check_status(result: dict, name: str) -> str | None:
    for check in result["checks"]:
        if check["name"] == name:
            return check["status"]
    return None


def test_overridden_floor_changes_evaluation_outcome(tmp_path: Path) -> None:
    """AUC 0.53: fails the global 0.55 floor; passes a per-instrument 0.52."""
    _write_instrument_config(
        tmp_path, "NOISY_USDT_15m",
        {"direction_quality": {"min_direction_auc": 0.52}},
    )
    iteration = _direction_iteration(auc=0.53)

    global_result = evaluate_development_gate_bundle(
        bundle=_bundle(), model_type="direction", best_iteration=iteration,
    )
    assert _check_status(global_result, "min_direction_auc") == "failed"
    assert "direction_auc_below_gate_or_missing" in global_result["blockers"]
    assert global_result["instrument_gate_overrides"] is None

    patched = apply_instrument_gate_overrides(
        _bundle(), instrument="NOISY_USDT", timeframe="15m", workspace_root=tmp_path,
    )
    override_result = evaluate_development_gate_bundle(
        bundle=patched, model_type="direction", best_iteration=iteration,
    )
    assert _check_status(override_result, "min_direction_auc") == "passed"
    assert "direction_auc_below_gate_or_missing" not in override_result["blockers"]
    # Provenance: the promotion record shows which thresholds were in force.
    prov = override_result["instrument_gate_overrides"]
    assert prov and prov["applied"]["direction_quality"]["min_direction_auc"]["to"] == 0.52
