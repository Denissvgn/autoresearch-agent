from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.core import config_promoter, pipeline_controller
from src.core.config_promoter import ConfigPromoter
from src.core.development_gate_bundle import DEFAULT_GATE_BUNDLE_RELATIVE_PATH
from src.core.pipeline_controller import PipelineConfig, PipelineController
from src.core.results_store import ResultsStore


class FakeSessionManager:
    def __init__(
        self,
        *,
        store: ResultsStore,
        root: Path,
        metrics_by_phase: dict[str, dict[str, Any]],
    ) -> None:
        self.store = store
        self.root = root
        self.metrics_by_phase = metrics_by_phase

    async def start_phase_session(self, **kwargs):
        phase = kwargs["model_type"]
        session_id = f"res_{phase}"
        workspace = self.root / "runs" / "autotuner" / (
            f"{kwargs['instrument']}_{kwargs['timeframe']}"
        ) / phase
        workspace.mkdir(parents=True, exist_ok=True)
        await self.store.create_session(
            session_id=session_id,
            instrument=kwargs["instrument"],
            timeframe=kwargs["timeframe"],
            model_type=phase,
            tag=kwargs["tag"],
            quick_mode=kwargs["quick_mode"],
            max_iterations=kwargs["max_iterations"],
            max_budget_usd=kwargs["max_budget_usd"],
            focus_hint=kwargs.get("focus_hint"),
            workspace_path=str(workspace),
        )
        await self.store.update_session(
            session_id, pipeline_id=kwargs.get("pipeline_id")
        )
        await self.store.add_iteration(
            research_id=session_id,
            iteration=1,
            primary_metric=0.61,
            metric_name="auc" if phase != "rl" else "mean_oos_sharpe",
            all_gates_passed=True,
            decision="keep",
            description="passing candidate",
            config_snapshot="agent_strategy: BALA\n",
            metrics_json=json.dumps(self.metrics_by_phase[phase]),
            training_time_s=1.0,
        )
        return await self.store.get_session(session_id)

    def is_running(self, session_id: str) -> bool:
        return False


def _write_gate_bundle(root: Path) -> None:
    path = root / DEFAULT_GATE_BUNDLE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
version: 1
gate_bundle_id: development_direction_prediction_v1
scope: development
promotion_policy:
  auc_only_promotion_allowed: false
  live_production_promotion_allowed: false
gate_tiers:
  direction_quality:
    checks:
      min_direction_auc: 0.55
      max_signal_rate: 0.35
  calibration:
    checks:
      max_ece_calibrated: 0.05
      max_threshold_cv: 0.20
  economic_replay:
    checks:
      worsening_vs_baseline_blocks_promotion: true
  inference_parity:
    required: true
    checks:
      feature_name_alignment_required: true
      feature_count_alignment_required: true
      model_roster_parity_required: true
promotion_blockers:
  - missing_economic_replay
  - weak_calibration
  - signal_saturation
  - unstable_fold_thresholds
  - inference_feature_schema_mismatch
""",
        encoding="utf-8",
    )


def _supervised_metrics(*, include_replay: bool = True) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "all_gates_passed": True,
        "metrics": {"auc": 0.61},
        "gate_results": {
            "all_supported_gates_passed": True,
            "direction_auc": 0.61,
            "operating_signal_rate": 0.21,
        },
        "config": {
            "calibration_full_validation": {
                "selected": {
                    "metrics": {"ece": 0.02, "brier_score": 0.21},
                    "reliability_diagram": [{"count": 10}],
                },
                "threshold_stability_by_fold": {
                    "folds": [{"fold": 1, "threshold": 0.52}],
                    "threshold_cv": 0.04,
                },
                "signal_rate_distribution": {
                    "mean": 0.2,
                    "max": 0.22,
                    "by_fold": [0.18, 0.22],
                },
                "per_regime_calibration": {
                    "available": False,
                    "reason": "regime_labels_absent",
                },
            }
        },
        "inference_parity": {
            "feature_name_alignment_passed": True,
            "feature_count_alignment_passed": True,
            "model_roster_parity_passed": True,
        },
        "mlflow_run_id": "run-supervised-1",
        "artifact_uri": "mlflow://runs/run-supervised-1/model",
        "rollback_target": "feature_model:1",
        "smoke_validation": {"passed": True},
    }
    if include_replay:
        metrics["economic_replay"] = {"gates": {"all_gates_passed": True}}
    return metrics


def _rl_metrics_missing_replay() -> dict[str, Any]:
    return {
        "all_gates_passed": True,
        "finalist": True,
        "mlflow_run_id": "run-rl-1",
        "artifact_uri": "mlflow://runs/run-rl-1/model",
        "obs_spec_hash": "obs-sha",
        "inference_parity": {
            "feature_name_alignment_passed": True,
            "feature_count_alignment_passed": True,
            "model_roster_parity_passed": True,
        },
        "rollback_target": "rl_policy:1",
        "smoke_validation": {"passed": True},
    }


async def _create_pipeline(store: ResultsStore, pipeline_id: str) -> None:
    await store.create_pipeline(
        pipeline_id=pipeline_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        tag="arp005",
        max_iterations=3,
        max_budget_usd=3.0,
        quick_mode=True,
        timeout_s=0,
        focus_hint=None,
        phase_budgets=json.dumps({"direction": 1, "volatility": 1, "rl": 1}),
        trading_mode=None,
        agent_strategy=None,
        initial_balance=None,
        enable_hpo=False,
        hpo_trials=None,
        hpo_timesteps=None,
    )


@pytest.mark.asyncio
async def test_pipeline_phase_promotes_through_config_promoter_and_records_metadata(
    tmp_path: Path,
    monkeypatch,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    monkeypatch.setattr(pipeline_controller, "PHASES", ["direction"])

    async def _forbid_direct_subprocess(*args, **kwargs):
        raise AssertionError("PipelineController must not invoke promote.py directly")

    monkeypatch.setattr(
        pipeline_controller.asyncio,
        "create_subprocess_exec",
        _forbid_direct_subprocess,
    )

    store = ResultsStore(str(tmp_path / "db" / "experiments.sqlite"))
    await store.initialize()
    await _create_pipeline(store, "pipe_ok")
    session_manager = FakeSessionManager(
        store=store,
        root=tmp_path,
        metrics_by_phase={"direction": _supervised_metrics()},
    )

    await PipelineController(store, session_manager).run(
        PipelineConfig(
            id="pipe_ok",
            instrument="DOGE_USDT",
            timeframe="15m",
            phase_budgets={"direction": 1},
        )
    )

    pipeline = await store.get_pipeline("pipe_ok")
    promotions = await store.list_promotions()

    assert pipeline["status"] == "completed"
    assert json.loads(pipeline["completed_phases"]) == ["direction"]
    assert pipeline.get("promotion_blockers") in (None, [])
    assert len(promotions) == 1
    assert promotions[0]["promotion_metadata"]["schema_version"] == (
        "development_promotion_metadata.v1"
    )
    assert Path(promotions[0]["metadata_path"]).exists()


@pytest.mark.asyncio
async def test_pipeline_rl_phase_missing_replay_is_promotion_blocked(
    tmp_path: Path,
    monkeypatch,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    monkeypatch.setattr(pipeline_controller, "PHASES", ["rl"])

    async def _skip_enrichment(self, config):
        return None

    monkeypatch.setattr(PipelineController, "_run_enrichment", _skip_enrichment)

    async def _forbid_direct_subprocess(*args, **kwargs):
        raise AssertionError("PipelineController must not invoke promote.py directly")

    monkeypatch.setattr(
        pipeline_controller.asyncio,
        "create_subprocess_exec",
        _forbid_direct_subprocess,
    )

    store = ResultsStore(str(tmp_path / "db" / "experiments.sqlite"))
    await store.initialize()
    await _create_pipeline(store, "pipe_blocked")
    session_manager = FakeSessionManager(
        store=store,
        root=tmp_path,
        metrics_by_phase={"rl": _rl_metrics_missing_replay()},
    )

    await PipelineController(store, session_manager).run(
        PipelineConfig(
            id="pipe_blocked",
            instrument="DOGE_USDT",
            timeframe="15m",
            phase_budgets={"rl": 1},
        )
    )

    pipeline = await store.get_pipeline("pipe_blocked")
    promotions = await store.list_promotions()

    assert pipeline["status"] == "promotion_blocked"
    assert pipeline["promotion_blocked_phase"] == "rl"
    assert json.loads(pipeline["completed_phases"]) == []
    assert "missing_rl_oos_gates" in pipeline["promotion_blockers"]
    assert pipeline["promotion_preview"]["phase"] == "rl"
    assert promotions == []


@pytest.mark.asyncio
@pytest.mark.parametrize("model_type", ["direction", "volatility"])
async def test_pipeline_feature_phase_not_blocked_only_for_missing_economic_replay(
    tmp_path: Path,
    monkeypatch,
    model_type: str,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    store = ResultsStore(str(tmp_path / "db" / "experiments.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "autotuner" / "DOGE_USDT_15m" / model_type
    workspace.mkdir(parents=True)
    await store.create_session(
        session_id=f"res_{model_type}",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type=model_type,
        tag="arp005",
        quick_mode=True,
        max_iterations=1,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path=str(workspace),
    )
    await store.update_session(f"res_{model_type}", pipeline_id="pipe_features")
    await store.add_iteration(
        research_id=f"res_{model_type}",
        iteration=1,
        primary_metric=0.61,
        metric_name="auc",
        all_gates_passed=True,
        decision="keep",
        description="supervised feature candidate",
        config_snapshot="agent_strategy: BALA\n",
        metrics_json=json.dumps(_supervised_metrics(include_replay=False)),
        training_time_s=1.0,
    )

    preview = await ConfigPromoter(store).preview(f"res_{model_type}")

    assert preview["promotion_allowed"] is True
    assert "missing_economic_replay" not in preview["candidate_pool_record"][
        "blockers"
    ]
