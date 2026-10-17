from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from src.core import config_promoter
from src.core.config_promoter import ConfigPromoter
from src.core.experiment_parser import parse_iteration_marker, parse_prepare_output
from src.core.results_store import ResultsStore


class FakePromotionStore:
    def __init__(self, best: Dict[str, Any]) -> None:
        self.best = best

    async def get_session(self, research_id: str) -> Dict[str, Any]:
        return {
            "id": research_id,
            "workspace_path": "/tmp/autoresearch-session",
            "model_type": "direction",
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
        }

    async def get_best_iteration(self, research_id, **kwargs) -> Dict[str, Any]:
        return self.best


def _prepare_block(*, training: str | None, legacy: str | None) -> str:
    lines = [
        "---",
        "status:             completed",
        "primary_metric:     0.640000",
        "metric_name:        composite_direction_score",
        "direction:          higher_is_better",
    ]
    if training is not None:
        lines.append(f"training_gates_passed: {training}")
    if legacy is not None:
        lines.append(f"all_gates_passed:   {legacy}")
    lines.extend(["training_time_s:    12.5", "---"])
    return "\n".join(lines)


def test_parse_prepare_output_accepts_training_gates_passed() -> None:
    metrics = parse_prepare_output(_prepare_block(training="true", legacy="true"))

    assert metrics.training_gates_passed is True
    assert metrics.all_gates_passed is True
    assert metrics.to_dict()["training_gates_passed"] is True
    assert metrics.to_dict()["all_gates_passed"] is True


def test_parse_prepare_output_preserves_legacy_all_gates_passed() -> None:
    metrics = parse_prepare_output(_prepare_block(training=None, legacy="true"))

    assert metrics.training_gates_passed is True
    assert metrics.all_gates_passed is True


def test_parse_prepare_output_prefers_training_gate_alias(
    caplog: pytest.LogCaptureFixture,
) -> None:
    metrics = parse_prepare_output(_prepare_block(training="false", legacy="true"))

    assert metrics.training_gates_passed is False
    assert metrics.all_gates_passed is False
    assert "Conflicting prepare.py gate aliases" in caplog.text


def test_iteration_marker_normalizes_gate_aliases() -> None:
    marker = parse_iteration_marker(
        'ITERATION_RESULT: {"training_gates_passed": false, '
        '"all_gates_passed": true, "primary_metric": 0.61}'
    )

    assert marker is not None
    assert marker["training_gates_passed"] is False
    assert marker["all_gates_passed"] is False


@pytest.mark.asyncio
async def test_results_store_normalizes_training_gate_aliases(
    tmp_path: Path,
) -> None:
    store = ResultsStore(str(tmp_path / "gate-status.sqlite"))
    await store.initialize()
    await store.create_session(
        session_id="res_gate_status",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="gate-status",
        quick_mode=False,
        max_iterations=4,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path=str(tmp_path),
    )

    await store.add_iteration(
        research_id="res_gate_status",
        iteration=1,
        primary_metric=0.61,
        metric_name="auc",
        all_gates_passed=True,
        decision="keep",
        description="conflicting aliases",
        config_snapshot="agent_strategy: BALA\n",
        metrics_json=json.dumps(
            {"training_gates_passed": False, "all_gates_passed": True}
        ),
        training_time_s=10.0,
        consistency_report_json=json.dumps({"passed": False}),
    )

    row = (await store.get_iterations("res_gate_status"))[0]
    payload = json.loads(row["metrics_json"])
    assert row["all_gates_passed"] == 0
    assert payload["training_gates_passed"] is False
    assert payload["all_gates_passed"] is False
    assert payload["consistency_report_passed"] is False


@pytest.mark.asyncio
async def test_preview_splits_training_bundle_consistency_statuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        config_promoter.settings,
        "host_configs_path",
        str(tmp_path / "configs"),
    )
    monkeypatch.setattr(
        ConfigPromoter,
        "_build_rollback_readiness",
        lambda *a, **kw: {"rollback_target": "direction-model:12"},
    )
    monkeypatch.setattr(
        ConfigPromoter,
        "_build_smoke_validation",
        lambda *a, **kw: {"passed": True},
    )
    monkeypatch.setattr(
        config_promoter,
        "build_development_signal_health",
        lambda *a, **kw: {"passed": True},
    )
    monkeypatch.setattr(
        config_promoter,
        "build_development_inference_validation",
        lambda *a, **kw: {"passed": True},
    )
    monkeypatch.setattr(
        config_promoter,
        "build_consistency_report",
        lambda *a, **kw: {
            "passed": True,
            "blockers": [],
            "checks": [],
        },
    )
    monkeypatch.setattr(
        ConfigPromoter,
        "_evaluate_gate_bundle",
        lambda *a, **kw: {
            "passed": False,
            "blockers": ["weak_calibration"],
            "checks": [],
        },
    )

    best = {
        "id": 10,
        "iteration": 3,
        "primary_metric": 0.64,
        "metric_name": "composite_direction_score",
        "all_gates_passed": 1,
        "config_snapshot": "agent_strategy: BALA\n",
        "metrics_json": json.dumps(
            {
                "training_gates_passed": True,
                "all_gates_passed": True,
                "mlflow_run_id": "run-123",
            }
        ),
    }

    preview = await ConfigPromoter(FakePromotionStore(best)).preview("res_gate")

    assert preview["training_gates_passed"] is True
    assert preview["gates_passed"] is True
    assert preview["development_gate_bundle_passed"] is False
    assert preview["consistency_report_passed"] is True
    assert preview["promotion_allowed"] is False
    metadata = preview["development_promotion_metadata"]
    assert metadata["training_gates_passed"] is True
    assert metadata["development_gate_bundle_passed"] is False
    assert metadata["consistency_report_passed"] is True
