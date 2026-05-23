from __future__ import annotations

import importlib.util
import json
import sys
import types
import urllib.request
from pathlib import Path

import joblib
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


def test_direction_prepare_maps_platt_alias_to_sigmoid_for_stacking_schema():
    direction = _load_module(
        "autoresearch_direction_prepare_calibration_contract",
        REPO_ROOT / "scripts" / "autotuner" / "direction" / "prepare.py",
    )

    cfg = direction.build_phase1c_config(
        {
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "stacking_calibration_method": "platt",
            "stacking_calibration_fallback_method": "platt",
        }
    )

    assert cfg["stacking_calibration_method"] == "sigmoid"
    assert cfg["stacking_calibration_fallback_method"] == "sigmoid"


def test_direction_prepare_passes_adaptive_and_spectral_keys_to_phase1c():
    direction = _load_module(
        "autoresearch_direction_prepare_adaptive_contract",
        REPO_ROOT / "scripts" / "autotuner" / "direction" / "prepare.py",
    )

    cfg = direction.build_phase1c_config(
        {
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "adaptive_levels_enabled": True,
            "adaptive_levels_version": "adaptive_levels.v1",
            "spectral_features_enabled": True,
            "spectral_features_version": "spectral_features.v1",
            "spectral_evidence_report_path": "reports/spectral.md",
        }
    )

    assert cfg["adaptive_levels_enabled"] is True
    assert cfg["adaptive_levels_version"] == "adaptive_levels.v1"
    assert cfg["spectral_features_enabled"] is True
    assert cfg["spectral_features_version"] == "spectral_features.v1"
    assert cfg["spectral_evidence_report_path"] == "reports/spectral.md"


def test_direction_prepare_passes_tsfm_fields_to_phase1c():
    direction = _load_module(
        "autoresearch_direction_prepare_tsfm_config_contract",
        REPO_ROOT / "scripts" / "autotuner" / "direction" / "prepare.py",
    )

    cfg = direction.build_phase1c_config(
        {
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "candidate_family": "tsfm",
            "model_family": "timesfm",
            "tsfm_adapter_configs": {"timesfm_adapter": {"forecast_type": "quantile"}},
            "tsfm_adapter_artifact_paths": {"timesfm_adapter": "adapters/timesfm.joblib"},
        }
    )

    assert cfg["candidate_family"] == "tsfm"
    assert cfg["model_family"] == "timesfm"
    assert cfg["tsfm_adapter_configs"] == {
        "timesfm_adapter": {"forecast_type": "quantile"}
    }
    assert cfg["tsfm_adapter_artifact_paths"] == {
        "timesfm_adapter": "adapters/timesfm.joblib"
    }


def test_direction_prepare_extracts_structured_tsfm_fallback_evidence(tmp_path):
    direction = _load_module(
        "autoresearch_direction_prepare_tsfm_fallback_contract",
        REPO_ROOT / "scripts" / "autotuner" / "direction" / "prepare.py",
    )

    extracted = direction.extract_metrics(
        {
            "metrics": {"auc": 0.64, "precision": 0.6, "recall": 0.7, "f1": 0.65},
            "walkforward": {"walkforward_mean_auc": 0.61, "walkforward_auc_cv": 0.08},
            "gate_results": {"all_supported_gates_passed": True},
            "config": {
                "candidate_family": "tabular",
                "training_mode": "stacking",
                "base_models": ["lgb", "xgb"],
                "operating_signal_rate": 0.42,
            },
        }
    )

    fallback = extracted["tsfm_fallback_validation"]
    assert fallback["passed"] is True
    assert fallback["reason"] == "tabular_candidate_family"
    assert fallback["candidate_family"] == "tabular"
    assert fallback["is_tsfm_candidate"] is False
    assert fallback["base_models"] == ["lgb", "xgb"]

    direction.print_summary(extracted, 12.3, marker_dir=tmp_path)
    marker = (tmp_path / "last_metrics.txt").read_text()
    assert "tsfm_fallback_validation_json:" in marker
    assert '"reason":"tabular_candidate_family"' in marker


def test_direction_prepare_extracts_tsfm_adapter_evidence_from_metadata():
    direction = _load_module(
        "autoresearch_direction_prepare_tsfm_adapter_contract",
        REPO_ROOT / "scripts" / "autotuner" / "direction" / "prepare.py",
    )

    extracted = direction.extract_metrics(
        {
            "metrics": {"auc": 0.64, "precision": 0.6, "recall": 0.7, "f1": 0.65},
            "walkforward": {"walkforward_mean_auc": 0.61, "walkforward_auc_cv": 0.08},
            "gate_results": {"all_supported_gates_passed": True},
            "candidate_family": "tsfm",
            "tsfm_adapter_metadata": {
                "timesfm_adapter": {
                    "model_family": "timesfm",
                    "forecast_type": "probability",
                    "direction_output_name": "direction_proba",
                }
            },
            "config": {
                "tsfm_adapter_configs": {"timesfm_adapter": {"temperature": 1.0}},
                "tsfm_adapter_artifact_paths": {
                    "timesfm_adapter": "adapters/timesfm.joblib"
                },
            },
        }
    )

    evidence = extracted["tsfm_adapter"]
    assert evidence["passed"] is True
    assert evidence["candidate_family"] == "tsfm"
    assert evidence["base_key"] == "timesfm_adapter"
    assert evidence["model_family"] == "timesfm"
    assert evidence["forecast_type"] == "probability"
    assert evidence["artifact_paths"] == {
        "timesfm_adapter": "adapters/timesfm.joblib"
    }
    assert "tsfm_fallback_validation" not in extracted


def test_run_phase1c_loads_tsfm_adapter_artifact_paths(tmp_path):
    runner = _load_module(
        "autoresearch_run_phase1c_direction_tsfm_loader_contract",
        REPO_ROOT / "scripts" / "training" / "run_phase1c_direction.py",
    )
    artifact_path = tmp_path / "timesfm.joblib"
    joblib.dump({"artifact_type": "tsfm_probability_adapter"}, artifact_path)

    loaded = runner.load_tsfm_adapter_artifacts(
        {"tsfm_adapter_artifact_paths": {"timesfm_adapter": artifact_path.name}},
        config_dir=tmp_path,
    )

    assert loaded == {"timesfm_adapter": {"artifact_type": "tsfm_probability_adapter"}}


def test_direction_prepare_extracts_and_marks_adaptive_feature_evidence(tmp_path):
    direction = _load_module(
        "autoresearch_direction_prepare_adaptive_metrics_contract",
        REPO_ROOT / "scripts" / "autotuner" / "direction" / "prepare.py",
    )

    extracted = direction.extract_metrics(
        {
            "metrics": {"auc": 0.64, "precision": 0.6, "recall": 0.7, "f1": 0.65},
            "walkforward": {"walkforward_mean_auc": 0.61, "walkforward_auc_cv": 0.08},
            "gate_results": {"all_supported_gates_passed": True},
            "config": {
                "adaptive_levels_version": "adaptive_levels.v1",
                "operating_signal_rate": 0.42,
            },
            "feature_schema": {
                "n_features": 97,
                "feature_schema_hash": "schema-adaptive",
                "adaptive_levels": {
                    "requested": True,
                    "enabled": True,
                    "version": "adaptive_levels.v1",
                    "selected_count": 7,
                    "selected_feature_names": ["dist_to_support_24"],
                },
            },
        }
    )

    assert extracted["n_features"] == 97
    assert extracted["feature_schema_hash"] == "schema-adaptive"
    assert extracted["adaptive_feature_version"] == "adaptive_levels.v1"
    assert extracted["adaptive_features"]["selected_count"] == 7

    direction.print_summary(extracted, 12.3, marker_dir=tmp_path)
    marker = (tmp_path / "last_metrics.txt").read_text()
    assert "adaptive_feature_version: adaptive_levels.v1" in marker
    assert '"selected_count": 7' in marker
    assert "feature_schema_hash: schema-adaptive" in marker


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
