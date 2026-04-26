from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from server.core import config_promoter
from server.core.config_promoter import ConfigPromoter
from server.core.development_gate_bundle import DEFAULT_GATE_BUNDLE_RELATIVE_PATH


class FakePromotionStore:
    def __init__(self, best: dict) -> None:
        self.best = best
        self.promotions: list[dict] = []

    async def get_session(self, research_id: str):
        return {
            "id": research_id,
            "workspace_path": "/tmp/autoresearch-session",
            "model_type": "direction",
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
        }

    async def get_best_iteration(self, research_id: str):
        return self.best

    async def record_promotion(self, **kwargs):
        self.promotions.append(kwargs)
        return {"id": 1, **kwargs}


def _write_gate_bundle(root: Path) -> None:
    path = root / DEFAULT_GATE_BUNDLE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
version: 1
gate_bundle_id: development_direction_prediction_v1
promotion_policy:
  auc_only_promotion_allowed: false
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
promotion_blockers:
  - weak_calibration
  - signal_saturation
  - unstable_fold_thresholds
  - missing_economic_replay
  - worsening_post_cost_replay
""",
        encoding="utf-8",
    )


def _write_gate_bundle_with_rl(root: Path) -> None:
    path = root / DEFAULT_GATE_BUNDLE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
version: 1
gate_bundle_id: development_direction_prediction_v1
promotion_policy:
  auc_only_promotion_allowed: false
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
  rl_oos:
    required_for_finalists: true
    checks:
      oof_direction_proba_required: true
      proxy_or_neutral_fallback_blocks_promotion: true
      nested_validation_required: true
      multi_seed_required: true
      metrics_required:
        - oos_sharpe
        - return
        - drawdown
        - trade_count
        - mean_absolute_position
        - flip_count
        - is_oos_ratio
        - folds_passed
promotion_blockers:
  - missing_oof_provenance
  - proxy_or_neutral_direction_proba_fallback
""",
        encoding="utf-8",
    )


def _passing_metrics() -> dict:
    return {
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
        "economic_replay": {"gates": {"all_gates_passed": True}},
        "rollback_target": "direction_model:12",
        "smoke_validation": {"passed": True},
    }


def _passing_rl_oos() -> dict:
    return {
        "direction_probability_provenance": {
            "honest_coverage": 1.0,
            "unsafe_count": 0,
            "unsafe_values": [],
        },
        "nested_validation_used": True,
        "n_seed_trials": 3,
        "aggregate": {
            "mean_oos_sharpe": 0.4,
            "mean_oos_return": 0.03,
            "mean_oos_drawdown": 0.08,
            "mean_oos_trades": 34,
            "mean_abs_position": 0.42,
            "mean_flip_count": 8,
            "is_oos_ratio": 1.2,
            "folds_passed": 3,
        },
        "artifact_uri": "mlflow://runs/rl-finalist",
    }


def _best_iteration(metrics: dict) -> dict:
    return {
        "iteration": 3,
        "primary_metric": 0.61,
        "all_gates_passed": 1,
        "config_snapshot": "agent_strategy: BALA\n",
        "metrics_json": json.dumps(metrics),
    }


@pytest.mark.asyncio
async def test_preview_includes_blocking_gate_bundle_result(tmp_path, monkeypatch):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics["config"].pop("calibration_full_validation")
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    gate_eval = preview["gate_bundle_evaluation"]
    assert preview["promotion_allowed"] is False
    assert gate_eval["passed"] is False
    assert "weak_calibration" in gate_eval["blockers"]
    assert "missing_reliability_diagram" in gate_eval["blockers"]
    assert preview["candidate_pool_record"] == {
        "source": "autoresearch.iterations",
        "research_id": "research_1",
        "iteration": 3,
        "status": "blocked",
        "blockers": gate_eval["blockers"],
        "inspectable": True,
        "promotion_record_created": False,
    }


@pytest.mark.asyncio
async def test_preview_blocks_weak_calibration_and_signal_saturation_exactly(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics["config"]["calibration_full_validation"]["selected"]["metrics"]["ece"] = 0.12
    metrics["gate_results"]["operating_signal_rate"] = 0.82
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    blockers = preview["gate_bundle_evaluation"]["blockers"]
    assert "weak_calibration" in blockers
    assert "signal_saturation" in blockers
    assert "signal_saturation_or_missing" not in blockers


@pytest.mark.asyncio
async def test_preview_blocks_unstable_fold_thresholds(tmp_path, monkeypatch):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics["config"]["calibration_full_validation"]["threshold_stability_by_fold"][
        "threshold_cv"
    ] = 0.31
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    gate_eval = preview["gate_bundle_evaluation"]
    assert "unstable_fold_thresholds" in gate_eval["blockers"]
    assert any(
        check["name"] == "max_threshold_cv"
        and check["status"] == "failed"
        and check["reason"] == "unstable_fold_thresholds"
        for check in gate_eval["checks"]
    )


@pytest.mark.asyncio
async def test_preview_blocks_worsening_post_cost_replay_even_if_replay_gates_pass(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics["economic_replay"] = {
        "gates": {
            "all_gates_passed": True,
            "metrics": {"post_cost_return_delta_vs_baseline": -0.01},
        }
    }
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    gate_eval = preview["gate_bundle_evaluation"]
    assert "worsening_post_cost_replay" in gate_eval["blockers"]
    assert preview["promotion_allowed"] is False


@pytest.mark.asyncio
async def test_confirm_requires_development_gate_bundle_pass(tmp_path, monkeypatch):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics["economic_replay"] = {}
    store = FakePromotionStore(_best_iteration(metrics))

    with pytest.raises(ValueError, match="development gate bundle failed"):
        await ConfigPromoter(store).confirm("research_1")


@pytest.mark.asyncio
async def test_confirm_records_promotion_when_bundle_passes(tmp_path, monkeypatch):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    store = FakePromotionStore(_best_iteration(_passing_metrics()))

    result = await ConfigPromoter(store).confirm("research_1")

    assert result["iteration"] == 3
    assert store.promotions
    target_path = Path(store.promotions[0]["target_path"])
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8") == "agent_strategy: BALA\n"


@pytest.mark.asyncio
async def test_preview_blocks_finalist_with_proxy_direction_rl_oos(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_rl(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics["finalist"] = True
    metrics["rl_oos"] = _passing_rl_oos()
    metrics["rl_oos"]["direction_probability_provenance"] = {
        "honest_coverage": 0.0,
        "unsafe_count": 100,
        "unsafe_values": ["sdk_proxy"],
    }
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    blockers = preview["gate_bundle_evaluation"]["blockers"]
    assert "missing_oof_provenance" in blockers
    assert "proxy_or_neutral_direction_proba_fallback" in blockers
    assert preview["candidate_pool_record"]["inspectable"] is True


@pytest.mark.asyncio
async def test_preview_accepts_finalist_with_honest_rl_oos(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_rl(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics["finalist"] = True
    metrics["rl_oos"] = _passing_rl_oos()
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    gate_eval = preview["gate_bundle_evaluation"]
    assert gate_eval["passed"] is True
    assert not gate_eval["blockers"]
