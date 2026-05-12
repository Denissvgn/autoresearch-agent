from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    _stub = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = _stub

from src.core import config_promoter
from src.core import orchestrator as orchestrator_module
from src.core.config_promoter import ConfigPromoter
from src.core.development_gate_bundle import evaluate_development_gate_bundle
from src.core.experiment_parser import parse_prepare_output
from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.results_store import ResultsStore


def _load_prepare_module(relative_path: str, module_name: str):
    path = Path(__file__).resolve().parents[3] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _create_session(
    store: ResultsStore,
    *,
    session_id: str,
    workspace: Path,
    model_type: str = "direction",
) -> None:
    await store.create_session(
        session_id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type=model_type,
        tag=session_id,
        quick_mode=True,
        max_iterations=5,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path=str(workspace),
    )


def _rich_results_payload(model_path: str = "runs/model.pkl") -> Dict[str, Any]:
    feature_names = ["return_1", "close_fib_bucket_24"] + [
        f"feature_{idx:02d}" for idx in range(40)
    ]
    feature_schema_flags = {
        "adaptive_levels": {
            "enabled": True,
            "version": "adaptive_levels.v1",
            "selected_feature_names": feature_names,
        }
    }
    feature_schema_hash = "schema-rich"
    selected_feature_names_hash = "selected-rich"
    return {
        "metrics": {
            "auc": 0.64,
            "meta_auc_oof": 0.63,
            "precision": 0.58,
            "recall": 0.52,
            "f1": 0.55,
        },
        "walkforward": {
            "walkforward_mean_auc": 0.62,
            "walkforward_auc_cv": 0.08,
        },
        "gate_results": {
            "all_supported_gates_passed": True,
            "direction_auc": 0.64,
            "operating_signal_rate": 0.12,
        },
        "config": {
            "operating_signal_rate": 0.12,
            "optimal_threshold": 0.47,
            "prediction_horizon": 3,
            "calibration_full_validation": {
                "selected": {
                    "metrics": {"ece": 0.02, "brier_score": 0.18},
                    "reliability_diagram": [{"bin": 0, "predicted": 0.1}],
                },
                "threshold_stability_by_fold": {
                    "folds": [{"fold": 1, "threshold": 0.47}],
                    "threshold_cv": 0.04,
                },
                "signal_rate_distribution": {"max": 0.18, "mean": 0.12},
                "per_regime_calibration": {
                    "available": False,
                    "reason": "regime_labels_absent",
                },
            },
        },
        "requested_base_models": ["lgbm", "xgb"],
        "surviving_base_models": ["lgbm", "xgb"],
        "pruned_base_models": [],
        "model_path": model_path,
        "mlflow_run_id": "run-rich",
        "feature_schema_hash": feature_schema_hash,
        "selected_feature_names_hash": selected_feature_names_hash,
        "feature_schema_flags": feature_schema_flags,
        "parity_metadata": {
            "feature_schema_hash": feature_schema_hash,
            "selected_feature_names_hash": selected_feature_names_hash,
            "feature_schema_flags": feature_schema_flags,
            "feature_count": len(feature_names),
        },
        "feature_schema": {
            "n_features": len(feature_names),
            "feature_schema_hash": feature_schema_hash,
            "selected_feature_names_hash": selected_feature_names_hash,
            "feature_schema_flags": feature_schema_flags,
            "adaptive_levels": {
                "requested": True,
                "enabled": True,
                "version": "adaptive_levels.v1",
                "selected_count": 1,
                "selected_feature_names": ["close_fib_bucket_24"],
                "feature_schema_hash": feature_schema_hash,
                "selected_feature_names_hash": selected_feature_names_hash,
            },
        },
        "adaptive_features": {
            "requested": True,
            "enabled": True,
            "version": "adaptive_levels.v1",
            "selected_count": 1,
            "selected_feature_names": ["close_fib_bucket_24"],
            "n_features": len(feature_names),
            "feature_schema_hash": feature_schema_hash,
            "selected_feature_names_hash": selected_feature_names_hash,
        },
        "n_features": len(feature_names),
    }


def _base_marker(results_path: Path) -> Dict[str, Any]:
    return {
        "status": "completed",
        "primary_metric": 0.632,
        "metric_name": "composite_direction_score",
        "training_gates_passed": True,
        "all_gates_passed": True,
        "decision": "keep",
        "description": "rich artifact run",
        "config_snapshot": "instrument: DOGE_USDT\ntimeframe: 15m\n",
        "results_json_path": str(results_path),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_direction_and_volatility_marker_emit_results_json_path(tmp_path: Path) -> None:
    direction_prepare = _load_prepare_module(
        "scripts/autotuner/direction/prepare.py",
        "direction_prepare_for_result_artifact_test",
    )
    volatility_prepare = _load_prepare_module(
        "scripts/autotuner/volatility/prepare.py",
        "volatility_prepare_for_result_artifact_test",
    )

    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    results_path = tmp_path / "results.json"

    direction_prepare.print_summary(
        {
            "primary_metric": 0.63,
            "metric_name": "composite_direction_score",
            "direction": "higher_is_better",
            "training_gates_passed": True,
            "all_gates_passed": True,
            "walkforward_auc": 0.62,
            "auc": 0.64,
            "meta_auc_oof": 0.63,
            "walkforward_cv": 0.08,
            "precision": 0.58,
            "recall": 0.52,
            "f1": 0.55,
            "signal_rate": 0.12,
            "optimal_threshold": 0.47,
            "prediction_horizon": 3,
        },
        12.0,
        marker_dir=marker_dir,
        results_json_path=results_path,
    )
    assert f"results_json_path:  {results_path}" in (
        marker_dir / "last_metrics.txt"
    ).read_text(encoding="utf-8")

    volatility_prepare.print_summary(
        {
            "primary_metric": 0.61,
            "metric_name": "auc",
            "direction": "higher_is_better",
            "training_gates_passed": True,
            "all_gates_passed": True,
            "auc": 0.61,
            "walkforward_auc": 0.59,
            "walkforward_cv": 0.06,
            "precision": 0.57,
            "recall": 0.51,
            "f1": 0.54,
            "positive_rate": 0.21,
            "atr_mult": 1.5,
            "signal_rate": 0.22,
            "optimal_threshold": 0.49,
        },
        13.0,
        marker_dir=marker_dir,
        results_json_path=results_path,
    )
    assert f"results_json_path:  {results_path}" in (
        marker_dir / "last_metrics.txt"
    ).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_record_iteration_copies_results_and_merges_nested_evidence(
    tmp_path: Path,
) -> None:
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "autotuner" / "DOGE_USDT_15m" / "direction"
    workspace.mkdir(parents=True)
    await _create_session(store, session_id="res_rich", workspace=workspace)

    results_path = workspace / "results.json"
    results_path.write_text(
        json.dumps(_rich_results_payload()) + "\n",
        encoding="utf-8",
    )
    source_hash = _sha256(results_path)

    await AgentOrchestrator(store)._record_iteration(
        "res_rich",
        1,
        _base_marker(results_path),
        0.0,
        workspace=str(workspace),
        turn=2,
        command=".venv/bin/python scripts/autotuner/direction/prepare.py --quick",
    )

    row = await store.get_iteration("res_rich", 1)
    metrics = json.loads(row["metrics_json"])
    snapshot = json.loads(row["attempt_snapshot_json"])
    artifact_path = Path(metrics["result_artifact_path"])

    assert artifact_path == workspace / "server_snapshots" / "iteration_0001_results.json"
    assert artifact_path.exists()
    assert metrics["result_artifact_sha256"] == source_hash
    assert snapshot["result_artifact_sha256"] == source_hash
    assert metrics["metrics"]["auc"] == 0.64
    assert metrics["gate_results"]["direction_auc"] == 0.64
    assert (
        metrics["config"]["calibration_full_validation"]["selected"]["metrics"][
            "brier_score"
        ]
        == 0.18
    )
    assert metrics["requested_base_models"] == ["lgbm", "xgb"]
    assert metrics["feature_schema_hash"] == "schema-rich"
    assert metrics["feature_schema_flags"]["adaptive_levels"][
        "selected_feature_names"
    ][1] == "close_fib_bucket_24"
    assert metrics["feature_schema"]["selected_feature_names_hash"] == "selected-rich"
    assert metrics["parity_metadata"]["feature_schema_hash"] == "schema-rich"
    assert metrics["parity_metadata"]["feature_count"] == 42
    assert metrics["adaptive_features"]["selected_feature_names"] == [
        "close_fib_bucket_24"
    ]
    assert snapshot["feature_schema_hash"] == "schema-rich"
    assert snapshot["selected_feature_names_hash"] == "selected-rich"
    assert snapshot["feature_schema_flags"] == metrics["feature_schema_flags"]
    assert snapshot["n_features"] == 42
    assert metrics["auc"] == 0.64
    assert metrics["walkforward_auc"] == 0.62
    assert metrics["signal_rate"] == 0.12
    assert not results_path.exists()


@pytest.mark.asyncio
async def test_fallback_results_json_is_claimed_preserved_and_consumed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "workspace-root"
    workspace = root / "runs" / "autotuner" / "DOGE_USDT_15m" / "direction"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(orchestrator_module.settings, "workspace_root", str(root))

    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_fallback", workspace=workspace)

    results_path = workspace / "results.json"
    results_path.write_text(
        json.dumps(_rich_results_payload()) + "\n",
        encoding="utf-8",
    )

    orchestrator = AgentOrchestrator(store)
    marker_text = orchestrator._read_marker_file(
        ResearchConfig(
            id="res_fallback",
            instrument="DOGE_USDT",
            timeframe="15m",
            model_type="direction",
        )
    )

    assert marker_text is not None
    assert not results_path.exists()
    marker = parse_prepare_output(marker_text).to_dict()
    claimed_path = Path(marker["results_json_path"])
    assert claimed_path.exists()
    marker["decision"] = "keep"
    marker["description"] = "fallback rich artifact"
    marker["config_snapshot"] = "instrument: DOGE_USDT\n"

    await orchestrator._record_iteration(
        "res_fallback",
        1,
        marker,
        0.0,
        workspace=str(workspace),
        turn=1,
        command=".venv/bin/python scripts/training/run_phase1c_direction.py",
    )

    row = await store.get_iteration("res_fallback", 1)
    metrics = json.loads(row["metrics_json"])
    assert not claimed_path.exists()
    assert Path(metrics["result_artifact_path"]).exists()
    assert metrics["config"]["calibration_full_validation"]["signal_rate_distribution"][
        "max"
    ] == 0.18
    assert metrics["feature_schema_flags"]["adaptive_levels"]["enabled"] is True


@pytest.mark.asyncio
async def test_invalid_result_artifact_path_is_ignored(tmp_path: Path) -> None:
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    await _create_session(store, session_id="res_invalid_path", workspace=workspace)

    outside = tmp_path / "outside-results.json"
    outside.write_text(json.dumps(_rich_results_payload()), encoding="utf-8")
    marker = _base_marker(outside)

    await AgentOrchestrator(store)._record_iteration(
        "res_invalid_path",
        1,
        marker,
        0.0,
        workspace=str(workspace),
        turn=1,
        command="prepare.py",
    )

    row = await store.get_iteration("res_invalid_path", 1)
    metrics = json.loads(row["metrics_json"])
    assert "result_artifact_path" not in metrics
    assert "results_json_path" not in metrics
    assert outside.exists()


def test_prepare_output_parses_feature_schema_flags_json() -> None:
    marker = parse_prepare_output(
        """
---
status: completed
primary_metric: 0.63
metric_name: composite_direction_score
training_gates_passed: true
all_gates_passed: true
feature_schema_hash: schema-rich
selected_feature_names_hash: selected-rich
feature_schema_flags_json: {"adaptive_levels":{"enabled":true,"selected_feature_names":["return_1","close_fib_bucket_24"]}}
n_features: 42
---
"""
    ).to_dict()

    assert marker["feature_schema_hash"] == "schema-rich"
    assert marker["selected_feature_names_hash"] == "selected-rich"
    assert marker["feature_schema_flags"]["adaptive_levels"]["enabled"] is True
    assert marker["feature_schema_flags_json"] == marker["feature_schema_flags"]


def test_development_gate_bundle_uses_nested_result_evidence() -> None:
    payload = _rich_results_payload()
    payload.update(
        {
            "training_gates_passed": True,
            "all_gates_passed": True,
            "rollback_target": "/tmp/previous.yaml",
            "smoke_validation": {"passed": True},
        }
    )
    bundle = {
        "gate_bundle_id": "development_direction_prediction_v1",
        "version": 1,
        "promotion_policy": {
            "auc_only_promotion_allowed": False,
            "live_production_promotion_allowed": False,
        },
        "gate_tiers": {
            "direction_quality": {
                "checks": {"min_direction_auc": 0.55, "max_signal_rate": 0.35}
            },
            "calibration": {
                "checks": {"max_ece_calibrated": 0.05, "max_threshold_cv": 0.20}
            },
        },
    }

    result = evaluate_development_gate_bundle(
        bundle=bundle,
        model_type="direction",
        best_iteration={
            "iteration": 1,
            "all_gates_passed": 1,
            "metrics_json": json.dumps(payload),
        },
    )

    assert "direction_auc_below_gate_or_missing" not in result["blockers"]
    assert "weak_calibration" not in result["blockers"]
    assert "missing_brier_score" not in result["blockers"]
    assert "missing_reliability_diagram" not in result["blockers"]
    assert "missing_threshold_stability_by_fold" not in result["blockers"]
    assert "missing_signal_rate_distribution" not in result["blockers"]
    assert "missing_per_regime_calibration_status" not in result["blockers"]


def test_development_gate_bundle_keeps_structural_evidence_required_for_legacy_rows() -> None:
    payload = {
        "training_gates_passed": True,
        "all_gates_passed": True,
        "auc": 0.64,
        "signal_rate": 0.12,
        "ece": 0.02,
        "brier_score": 0.18,
        "threshold_cv": 0.04,
        "rollback_target": "/tmp/previous.yaml",
        "smoke_validation": {"passed": True},
    }
    bundle = {
        "gate_bundle_id": "development_direction_prediction_v1",
        "version": 1,
        "promotion_policy": {
            "auc_only_promotion_allowed": False,
            "live_production_promotion_allowed": False,
        },
        "gate_tiers": {
            "direction_quality": {
                "checks": {"min_direction_auc": 0.55, "max_signal_rate": 0.35}
            },
            "calibration": {
                "checks": {"max_ece_calibrated": 0.05, "max_threshold_cv": 0.20}
            },
        },
    }

    result = evaluate_development_gate_bundle(
        bundle=bundle,
        model_type="direction",
        best_iteration={
            "iteration": 1,
            "all_gates_passed": 1,
            "metrics_json": json.dumps(payload),
        },
    )

    assert "direction_auc_below_gate_or_missing" not in result["blockers"]
    assert "signal_saturation" not in result["blockers"]
    assert "weak_calibration" not in result["blockers"]
    assert "missing_brier_score" not in result["blockers"]
    assert "missing_reliability_diagram" in result["blockers"]
    assert "missing_threshold_stability_by_fold" in result["blockers"]
    assert "missing_signal_rate_distribution" in result["blockers"]
    assert "missing_per_regime_calibration_status" in result["blockers"]


def test_artifact_resolver_prefers_stored_model_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    model_path = (
        tmp_path
        / "runs"
        / "autotuner"
        / "DOGE_USDT_15m"
        / "direction"
        / "models"
        / "model.pkl"
    )
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"model")

    resolved = ConfigPromoter(object())._resolve_artifacts_dir(  # type: ignore[arg-type]
        str(tmp_path / "runs" / "autotuner" / "DOGE_USDT_15m" / "direction"),
        "direction",
        "DOGE_USDT",
        "15m",
        metrics_payload={
            "model_path": "runs/autotuner/DOGE_USDT_15m/direction/models/model.pkl"
        },
    )

    assert resolved == str(model_path.parent)
