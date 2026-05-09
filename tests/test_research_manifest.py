from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from src.core.research_manifest import build_research_manifest, manifest_pretty_json


def _build_manifest(**overrides):
    return build_research_manifest(
        research_id="res_manifest",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="m8",
        quick_mode=False,
        max_iterations=5,
        max_budget_usd=2.5,
        timeout_s=3600,
        focus_hint="calibration",
        trading_mode=None,
        agent_strategy=None,
        initial_balance=None,
        enable_hpo=False,
        hpo_trials=20,
        hpo_timesteps=50000,
        overrides=overrides or None,
    )


def test_build_research_manifest_has_required_runtime_sections():
    manifest = _build_manifest(
        data_window={"start": "2026-03-01", "end": "2026-03-31"},
    )
    payload = json.loads(manifest_pretty_json(manifest))

    assert payload["schema_version"] == "research_session_manifest.v1"
    assert payload["manifest_hash"]
    assert payload["research_id"] == "res_manifest"
    assert payload["data_window"]["instrument"] == "DOGE_USDT"
    assert payload["data_window"]["start"] == "2026-03-01"
    assert payload["service_urls"]["feature_service"].startswith("http://")
    assert payload["service_urls"]["vdmc_indicator"].startswith("http://")
    assert payload["service_urls"]["admin_service"].startswith("http://")
    assert payload["service_urls"]["mlflow_external"].startswith("http://")
    assert payload["preflight"]["schema_version"] == "autoresearch_service_preflight.v1"
    assert payload["preflight"]["status"] == "not_run"
    assert "mlflow_tracking" in payload["preflight"]["services"]
    assert "vdmc_indicator" in payload["preflight"]["services"]
    assert payload["preflight"]["services"]["vdmc_indicator"]["required"] is False
    assert payload["runtime"]["runs_dir"].endswith("/runs/autotuner")
    assert payload["runtime"]["db_path"].endswith("/db/experiments.db")


def test_manifest_identity_overrides_must_match_request():
    with pytest.raises(ValueError, match="instrument must match"):
        _build_manifest(instrument="BTC_USDT")
