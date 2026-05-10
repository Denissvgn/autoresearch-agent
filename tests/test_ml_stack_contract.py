from __future__ import annotations

import importlib.util
import json
import sys
import types
import urllib.request
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_predictive_prepare_defaults_and_serving_versions_align_with_stack():
    direction = _load_module(
        "autoresearch_direction_prepare_contract",
        REPO_ROOT / "scripts" / "autotuner" / "direction" / "prepare.py",
    )
    volatility = _load_module(
        "autoresearch_volatility_prepare_contract",
        REPO_ROOT / "scripts" / "autotuner" / "volatility" / "prepare.py",
    )

    direction_cfg = direction.build_phase1c_config(
        {"instrument": "DOGE_USDT", "timeframe": "15m"}
    )
    volatility_cfg = volatility.build_phase1c_config(
        {"instrument": "DOGE_USDT", "timeframe": "15m"}
    )

    assert direction_cfg["feature_library_version"] == "2.3.0"
    assert volatility_cfg["feature_library_version"] == "2.3.0"

    direction_metrics = direction.extract_metrics(
        {
            "metrics": {"auc": 0.62},
            "walkforward": {"walkforward_mean_auc": 0.60},
            "gate_results": {"all_supported_gates_passed": True},
            "config": {},
            "model_registry_name": "direction_model_DOGEUSDT",
            "model_version": "12",
            "ensemble_model_version": "21",
        }
    )
    volatility_metrics = volatility.extract_metrics(
        {
            "metrics": {"auc": 0.64},
            "walkforward": {"walkforward_mean_auc": 0.61},
            "gate_results": {"all_supported_gates_passed": True},
            "config": {},
            "model_registry_name": "volatility_model_DOGEUSDT",
            "model_version": "7",
            "ensemble_model_version": "9",
        }
    )

    assert direction_metrics["serving_model_registry_name"] == (
        "direction_model_DOGEUSDT_ensemble"
    )
    assert direction_metrics["serving_model_version"] == "21"
    assert volatility_metrics["serving_model_registry_name"] == (
        "volatility_model_DOGEUSDT_ensemble"
    )
    assert volatility_metrics["serving_model_version"] == "9"


def test_rl_trainer_requests_include_service_auth(monkeypatch):
    rl_prepare = _load_module(
        "autoresearch_rl_prepare_contract",
        REPO_ROOT / "scripts" / "autotuner" / "rl" / "prepare.py",
    )
    monkeypatch.setattr(rl_prepare, "_RL_TRAINER_SERVICE_TOKEN", "svc-token")
    monkeypatch.setattr(rl_prepare, "POLL_INTERVAL_S", 0)

    calls: list[dict] = []

    class Response:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(req, timeout=0):
        calls.append(
            {
                "url": req.full_url,
                "method": req.get_method(),
                "headers": dict(req.header_items()),
            }
        )
        if req.full_url.endswith("/api/v1/train/jobs"):
            return Response({"jobs": [{"job_id": "old-job", "status": "running"}]})
        if req.full_url.endswith("/api/v1/train/cancel/old-job"):
            return Response({"status": "cancelled"})
        if req.full_url.endswith("/api/v1/train"):
            return Response(
                {
                    "job_id": "job-1",
                    "status_url": "/api/v1/train/status/job-1",
                }
            )
        if req.full_url.endswith("/api/v1/train/status/job-1"):
            return Response(
                {
                    "status": "completed",
                    "result": {
                        "run_id": "run-1",
                        "metrics": {
                            "mean_oos_sharpe": 0.2,
                            "n_folds": 1,
                            "folds_passed": 1,
                        },
                    },
                }
            )
        raise AssertionError(f"unexpected URL {req.full_url}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(rl_prepare.time, "sleep", lambda *_args, **_kwargs: None)

    status, metrics = rl_prepare._submit_and_poll(
        {"instrument_id": "DOGE_USDT", "timeframe": "15m"},
        timeout=30,
        marker_dir=None,
    )

    assert status == "completed"
    assert metrics["_api_run_id"] == "run-1"
    assert {call["method"] for call in calls} == {"GET", "POST"}
    assert all(
        call["headers"].get("Authorization") == "Bearer svc-token"
        for call in calls
    )


def test_rl_trainer_auth_failure_does_not_return_auto_fallback_code(monkeypatch, tmp_path):
    rl_prepare = _load_module(
        "autoresearch_rl_prepare_auth_contract",
        REPO_ROOT / "scripts" / "autotuner" / "rl" / "prepare.py",
    )

    def fail_auth(*_args, **_kwargs):
        raise rl_prepare.RlTrainerAuthError("rejected")

    monkeypatch.setattr(rl_prepare, "_submit_and_poll", fail_auth)

    rc = rl_prepare.run_gpu(
        {"instrument": "DOGE_USDT", "timeframe": "15m"},
        {},
        tmp_path / "train.yaml",
        quick=True,
        timeout=30,
    )

    assert rc == 3


def test_production_replay_posts_api_v1_with_sample_path(monkeypatch):
    production = _load_module(
        "autoresearch_production_training_contract",
        REPO_ROOT / "scripts" / "training" / "run_production_training.py",
    )
    calls: list[dict] = []

    class Response:
        status_code = 200
        text = "{}"

        def __init__(self, payload: dict | None = None) -> None:
            self._payload = payload or {}

        def json(self):
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str):
            calls.append({"method": "GET", "url": url})
            return Response({"status": "ready"})

        def post(self, url: str, *, json: dict, timeout: float):
            calls.append({"method": "POST", "url": url, "json": json})
            return Response(
                {
                    "hold_rate": 0.5,
                    "trade_expression_rate": 0.4,
                    "buy_count": 10,
                    "sell_count": 8,
                    "total_bars": 96,
                    "passed": True,
                }
            )

    monkeypatch.setitem(sys.modules, "httpx", types.SimpleNamespace(Client=Client))
    monkeypatch.setenv("INFERENCE_SERVICE_URL", "http://inference-service:8000")
    monkeypatch.delenv("INFERENCE_REPLAY_SAMPLE_PATH", raising=False)

    result = production.stage_replay_gate(
        {"instrument": "DOGE_USDT", "timeframe": "15m"},
        "DOGE_USDT",
    )

    assert result.status == "passed"
    post = [call for call in calls if call["method"] == "POST"][0]
    assert post["url"] == "http://inference-service:8000/api/v1/replay/run"
    assert post["json"]["sample_path"] == "/data/samples/DOGE_USDT_15m.parquet"
