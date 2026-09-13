from __future__ import annotations

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
from src.core.config_promoter import ConfigPromoter
from src.core.consistency_validator import build_consistency_report
from src.core.experiment_parser import parse_prepare_output
from src.core.iteration_snapshot import build_iteration_attempt_snapshot
from src.core.research_state import build_research_state
from src.core.result_artifact import merge_result_payload
from src.core.results_store import ResultsStore

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_prepare_module(relative_path: str, module_name: str):
    path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prepare_block(mlflow_value: str) -> str:
    return "\n".join(
        [
            "---",
            "status:             completed",
            "primary_metric:     0.640000",
            "metric_name:        composite_direction_score",
            "direction:          higher_is_better",
            "training_gates_passed: true",
            "all_gates_passed:   true",
            f"mlflow_run_id:      {mlflow_value}",
            "training_time_s:    12.5",
            "---",
        ]
    )


async def _create_session(store: ResultsStore, *, session_id: str, workspace: Path) -> None:
    await store.create_session(
        session_id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag=session_id,
        quick_mode=True,
        max_iterations=4,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path=str(workspace),
    )


def test_parse_prepare_output_normalizes_mlflow_sentinels() -> None:
    for value in ("None", "none", "null", "N/A", "na", ""):
        parsed = parse_prepare_output(_prepare_block(value)).to_dict()
        assert parsed["mlflow_run_id"] is None

    parsed = parse_prepare_output(_prepare_block("run-valid-123")).to_dict()
    assert parsed["mlflow_run_id"] == "run-valid-123"


def test_prepare_summaries_do_not_emit_literal_none(capsys: pytest.CaptureFixture[str]) -> None:
    if not (REPO_ROOT / "scripts" / "autotuner").is_dir():
        pytest.skip(
            "platform workspace scripts (scripts/autotuner) not present in this checkout"
        )
    direction_prepare = _load_prepare_module(
        "scripts/autotuner/direction/prepare.py",
        "direction_prepare_for_mlflow_contract_test",
    )
    volatility_prepare = _load_prepare_module(
        "scripts/autotuner/volatility/prepare.py",
        "volatility_prepare_for_mlflow_contract_test",
    )
    rl_prepare = _load_prepare_module(
        "scripts/autotuner/rl/prepare.py",
        "rl_prepare_for_mlflow_contract_test",
    )

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
            "mlflow_run_id": None,
        },
        12.0,
    )
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
            "mlflow_run_id": None,
        },
        13.0,
    )
    rl_prepare.print_summary(
        {
            "primary_metric": 0.4,
            "metric_name": "composite_rl_score",
            "direction": "higher_is_better",
            "all_gates_passed": True,
            "mean_oos_sharpe": 0.2,
            "mean_oos_return": 0.1,
            "mean_oos_drawdown": 0.05,
            "std_oos_sharpe": 0.01,
            "sharpe_cv": 0.2,
            "mean_oos_trades": 12,
            "mean_oos_trades_per_day": 2.0,
            "mean_abs_position": 0.3,
            "mean_flip_count": 1.0,
            "mean_oos_trading_score": 0.4,
            "rl_profit_score": 0.4,
            "folds_passed": 3,
            "n_folds": 3,
            "mlflow_run_id": None,
        },
        14.0,
    )

    output = capsys.readouterr().out
    assert "mlflow_run_id:      None" not in output


@pytest.mark.asyncio
async def test_results_store_normalizes_mlflow_sentinel_values(tmp_path: Path) -> None:
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_mlflow_contract", workspace=tmp_path)

    await store.add_iteration(
        research_id="res_mlflow_contract",
        iteration=1,
        primary_metric=0.64,
        metric_name="auc",
        all_gates_passed=True,
        decision="keep",
        description="sentinel run id",
        config_snapshot="instrument: DOGE_USDT\n",
        metrics_json=json.dumps(
            {"mlflow_run_id": "None", "artifact_hash": "null"}
        ),
        training_time_s=10.0,
        mlflow_run_id="None",
    )

    row = await store.get_iteration("res_mlflow_contract", 1)
    payload = json.loads(row["metrics_json"])
    assert row["mlflow_run_id"] is None
    assert payload["mlflow_run_id"] is None
    assert payload["artifact_hash"] is None


def test_snapshots_and_result_artifact_merge_drop_sentinel_references(
    tmp_path: Path,
) -> None:
    snapshot = build_iteration_attempt_snapshot(
        research_id="res_snapshot",
        iteration=1,
        turn=1,
        command="prepare.py",
        config_snapshot="instrument: DOGE_USDT\n",
        workspace=str(tmp_path),
        marker={
            "mlflow_run_id": "None",
            "artifact_hash": "null",
            "result_artifact_path": "N/A",
            "result_artifact_sha256": "na",
        },
    )
    assert snapshot["mlflow_run_id"] is None
    assert snapshot["artifact_hash"] is None
    assert snapshot["result_artifact_path"] is None
    assert snapshot["result_artifact_sha256"] is None

    marker: Dict[str, Any] = {}
    merge_result_payload(
        marker,
        {
            "mlflow_run_id": "None",
            "artifact_hash": "null",
            "model_artifact_hash": "N/A",
        },
    )
    assert marker["mlflow_run_id"] is None
    assert marker["artifact_hash"] is None
    assert marker["model_artifact_hash"] is None


def test_consistency_report_blocks_mlflow_sentinel_artifact_reference() -> None:
    report = build_consistency_report(
        research_id="res_consistency",
        iteration=1,
        model_type="direction",
        config_snapshot="instrument: DOGE_USDT\n",
        metrics_payload={
            "finalist": True,
            "training_gates_passed": True,
            "mlflow_run_id": "None",
        },
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["mlflow_run_id_valid"]["status"] == "failed"
    assert checks["artifact_reference_present"]["status"] == "failed"
    assert "invalid_mlflow_run_id_sentinel" in report["blockers"]
    assert "missing_artifact_reference" in report["blockers"]


def test_consistency_report_accepts_immutable_result_artifact_reference() -> None:
    report = build_consistency_report(
        research_id="res_consistency",
        iteration=2,
        model_type="direction",
        config_snapshot="instrument: DOGE_USDT\n",
        metrics_payload={
            "finalist": True,
            "training_gates_passed": True,
            "mlflow_run_id": None,
            "result_artifact_path": "/tmp/iteration_0002_results.json",
            "result_artifact_sha256": "abc123",
        },
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["mlflow_run_id_valid"]["status"] == "passed"
    assert checks["artifact_reference_present"]["status"] == "passed"
    assert "missing_artifact_reference" not in report["blockers"]


