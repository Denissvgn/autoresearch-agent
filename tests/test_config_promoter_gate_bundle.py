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
promotion_blockers:
  - weak_calibration
  - missing_economic_replay
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
                },
                "signal_rate_distribution": {"mean": 0.2, "by_fold": [0.2]},
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
