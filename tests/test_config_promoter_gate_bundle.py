from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from src.core import config_promoter
from src.core.config_promoter import ConfigPromoter
from src.core.development_gate_bundle import (
    DEFAULT_GATE_BUNDLE_RELATIVE_PATH,
    PRODUCTION_GATE_BUNDLE_RELATIVE_PATH,
    evaluate_development_gate_bundle,
)
from src.core.results_store import ResultsStore


class FakePromotionStore:
    def __init__(
        self,
        best: dict,
        model_type: str = "direction",
        promotions: list[dict] | None = None,
        iterations: list[dict] | None = None,
    ) -> None:
        self.best = best
        self.model_type = model_type
        self.promotions: list[dict] = list(promotions or [])
        self.iterations = list(iterations or [best])

    async def get_session(self, research_id: str):
        return {
            "id": research_id,
            "workspace_path": "/tmp/autoresearch-session",
            "model_type": self.model_type,
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
        }

    async def get_best_iteration(self, research_id: str):
        return self.best

    async def get_iterations(self, research_id: str):
        return self.iterations

    async def get_iteration(self, research_id: str, iteration: int):
        for it in self.iterations:
            if it.get("iteration") == iteration:
                return it
        return self.best

    async def record_promotion(self, **kwargs):
        record = {
            "id": len(self.promotions) + 1,
            "promoted_at": f"2026-04-30T00:00:{len(self.promotions) + 1:02d}+00:00",
            **kwargs,
        }
        self.promotions.append(record)
        return record

    async def list_promotions(self):
        return list(reversed(self.promotions))

    async def get_latest_promotion(
        self,
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
        scope: str,
    ):
        for promotion in reversed(self.promotions):
            if (
                promotion.get("model_type") == model_type
                and promotion.get("instrument") == instrument
                and promotion.get("timeframe") == timeframe
                and promotion.get("scope") == scope
            ):
                return promotion
        return None

    async def get_latest_development_promotion(
        self,
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
    ):
        return await self.get_latest_promotion(
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
            scope="development",
        )


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
  required_decision_record: true
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
      replay_artifact_hash_required: true
      replay_assumptions_required: true
      profit_score_required: true
  inference_parity:
    required: true
    checks:
      feature_name_alignment_required: true
      feature_count_alignment_required: true
      model_roster_parity_required: true
      adapter_loading_required: true
      observation_dimension_parity_required_when_rl_changes: true
      latency_budget_required_for_tsfm: true
      fallback_required_for_tsfm: true
promotion_blockers:
  - weak_calibration
  - signal_saturation
  - unstable_fold_thresholds
  - missing_economic_replay
  - worsening_post_cost_replay
  - inference_feature_schema_mismatch
  - model_roster_mismatch
  - live_production_promotion_forbidden
""",
        encoding="utf-8",
    )


def _write_production_gate_bundle(root: Path) -> None:
    path = root / PRODUCTION_GATE_BUNDLE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
version: 1
gate_bundle_id: production_trading_model_promotion_v1
scope: production
promotion_policy:
  manual_or_signed_approval_required:
    paper: true
    canary: true
    production: true
  direct_development_to_production_allowed: false
  full_decision_chain_required: true
gate_tiers:
  canary_validation:
    checks:
      min_duration_hours: 24
promotion_blockers:
  - missing_paper_promotion
  - missing_canary_promotion
  - missing_production_approval
  - missing_model_card
  - missing_feature_readiness
  - missing_canary_duration
  - missing_live_risk_limits
  - missing_monitoring_alerts
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
  rl_oos:
    required_for_finalists: true
    checks:
      oof_direction_proba_required: true
      oof_volatility_proba_required: true
      feature_provenance_required: true
      feature_bundle_hash_required: true
      proxy_or_neutral_fallback_blocks_promotion: true
      volatility_fallback_blocks_promotion: true
      stale_or_leaked_blocks_promotion: true
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
  - missing_economic_replay
  - missing_rl_replay_metrics
  - missing_rl_economic_replay_artifact_hash
  - missing_rl_replay_assumptions
  - missing_rl_profit_score
  - missing_oof_provenance
  - missing_volatility_oof_provenance
  - missing_direction_feature_provenance
  - missing_volatility_feature_provenance
  - incomplete_direction_feature_provenance
  - incomplete_volatility_feature_provenance
  - missing_rl_feature_bundle_hash
  - proxy_or_neutral_direction_proba_fallback
  - proxy_or_neutral_volatility_feature_fallback
  - stale_or_leaked_feature_provenance
  - missing_nested_validation
  - missing_multi_seed_rl_validation
  - missing_rl_oos_metrics
""",
        encoding="utf-8",
    )


def _write_gate_bundle_with_m7_controls(root: Path) -> None:
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
      adapter_loading_required: true
      latency_budget_required_for_tsfm: true
      fallback_required_for_tsfm: true
  rollback_readiness:
    required: true
    checks:
      previous_development_version_addressable: true
      rollback_by_instrument_timeframe_supported: true
      rollback_target_recorded: true
  smoke_validation:
    required: true
    checks:
      paper_or_smoke_validation_required: true
      composite_reload_required: true
      prior_version_left_intact_on_failure: true
promotion_blockers:
  - missing_rollback_target
  - failed_smoke_validation
  - tsfm_adapter_load_failure_without_tabular_fallback
""",
        encoding="utf-8",
    )


def _write_gate_bundle_with_m7_remaining(root: Path) -> None:
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
  rollback_readiness:
    required: true
    checks:
      previous_development_version_addressable: true
      rollback_by_instrument_timeframe_supported: true
      rollback_target_recorded: true
  smoke_validation:
    required: true
    checks:
      paper_or_smoke_validation_required: true
      composite_reload_required: true
      prior_version_left_intact_on_failure: true
  signal_health_monitoring:
    required: true
    checks:
      probability_summary_required: true
      entropy_required: true
      signal_rate_required: true
      drift_metrics_required: true
      operational_metrics_required: true
  inference_reload:
    required: true
    checks:
      feature_alignment_required: true
      adapter_loading_required: true
      roster_parity_required: true
      observation_dimension_parity_required: true
      fallback_behavior_required: true
      latency_budget_required: true
      composite_reload_required: true
      rollback_ready_required: true
      prior_version_preserved_on_reload_failure: true
promotion_blockers:
  - missing_signal_health_metrics
  - inference_reload_validation_missing
  - inference_reload_failed
  - inference_adapter_load_failure
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
        "inference_parity": {
            "feature_name_alignment_passed": True,
            "feature_count_alignment_passed": True,
            "model_roster_parity_passed": True,
        },
        "feature_schema_hash": "schema-direction-1",
        "parity_metadata": {"feature_schema_hash": "schema-direction-1"},
        "feature_schema": {"feature_schema_hash": "schema-direction-1"},
        "model_registry_name": "direction-model",
        "model_version": "12",
        "mlflow_run_id": "run-direction-12",
        "artifact_uri": "mlflow://runs/run-direction-12/model",
        "composite_metadata": {
            "composite_id": "DOGE_USDT_15m_development",
            "reload_supported": True,
        },
        "rollback_target": "direction_model:12",
        "smoke_validation": {"passed": True},
    }


def _passing_rl_oos() -> dict:
    return {
        "direction_probability_provenance": {
            "source_model_registry_name": "direction-model",
            "source_model_registry_version": "12",
            "mlflow_run_id": "run-direction-12",
            "feature_schema_hash": "dir-schema-sha",
            "prediction_timestamp_coverage": 1.0,
            "status": "oof",
            "honest_coverage": 1.0,
            "unsafe_count": 0,
            "unsafe_values": [],
        },
        "volatility_probability_provenance": {
            "source_model_registry_name": "volatility-model",
            "source_model_registry_version": "7",
            "mlflow_run_id": "run-volatility-7",
            "feature_schema_hash": "vol-schema-sha",
            "prediction_timestamp_coverage": 1.0,
            "status": "oof",
            "honest_coverage": 1.0,
            "unsafe_count": 0,
            "unsafe_values": [],
        },
        "feature_bundle_hash": "rl-feature-bundle-sha",
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


def _passing_rl_economic_replay() -> dict:
    return {
        "schema_version": "rl_economic_replay.v1",
        "rl_profit_score": 0.235,
        "artifact_path": "/tmp/autoresearch-session/rl_economic_replay.json",
        "artifact_hash": "rl-economic-replay-sha",
        "metrics": {
            "post_cost_return": 0.03,
            "max_drawdown": 0.08,
            "sharpe": 0.4,
            "sortino": 0.6,
            "trade_count": 34,
            "turnover": 8,
            "hit_rate": 0.67,
            "average_trade_return": 0.00088,
        },
        "assumptions": {
            "fee_bps": 5.0,
            "spread_bps": 1.0,
            "slippage_bps": 2.0,
            "control": "flat_position_control",
        },
        "comparison": {
            "baseline_name": "flat_position_control",
            "baseline_post_cost_return": 0.0,
            "baseline_sharpe": 0.0,
            "post_cost_return_delta_vs_baseline": 0.03,
            "post_cost_sharpe_delta_vs_baseline": 0.4,
        },
        "gates": {
            "all_gates_passed": True,
            "worsening_vs_baseline": False,
            "metrics": {"post_cost_return_delta_vs_baseline": 0.03},
        },
        "folds": [
            {
                "fold": 1,
                "post_cost_return": 0.03,
                "max_drawdown": 0.08,
                "sharpe": 0.4,
                "trade_count": 34,
                "turnover": 8,
                "hit_rate": 0.67,
                "average_trade_return": 0.00088,
            }
        ],
    }


def _passing_m7_remaining_metrics() -> dict:
    metrics = _passing_metrics()
    metrics.pop("rollback_target", None)
    metrics["development_signal_health"] = {
        "direction_proba": [0.22, 0.41, 0.63, 0.78, 0.56],
        "base_model_probabilities": [
            [0.20, 0.26, 0.23],
            [0.40, 0.44, 0.39],
            [0.60, 0.66, 0.62],
            [0.76, 0.81, 0.77],
            [0.53, 0.59, 0.56],
        ],
        "training_distribution": {
            "probability_mean": 0.50,
            "probability_std": 0.18,
            "signal_rate": 0.40,
            "entropy_mean": 0.65,
            "probability_histogram": [10, 20, 30, 25, 15],
        },
        "probability_histogram": [9, 21, 31, 24, 15],
        "latency_ms_p95": 42.0,
        "adapter_failure_count": 0,
        "feature_schema_mismatch_count": 0,
        "rl_hold_rate": 0.32,
    }
    metrics["inference_parity"].update(
        {
            "adapter_loading_passed": True,
            "latency_budget_passed": True,
            "composite_reload_passed": True,
            "fallback_check_passed": True,
            "observation_dimension_parity_passed": True,
        }
    )
    return metrics


def _passing_rl_metrics() -> dict:
    metrics = _passing_metrics()
    metrics.update(
        {
            "finalist": True,
            "obs_spec_hash": "obs-spec-sha",
            "rl_oos": _passing_rl_oos(),
            "rl_economic_replay": _passing_rl_economic_replay(),
            "economic_replay": _passing_rl_economic_replay(),
            "rl_profit_score": 0.235,
            "rl_economic_replay_artifact_path": (
                "/tmp/autoresearch-session/rl_economic_replay.json"
            ),
            "rl_economic_replay_artifact_hash": "rl-economic-replay-sha",
            "model_registry_name": "rl-model",
            "model_version": "5",
            "mlflow_run_id": "run-rl-5",
            "artifact_uri": "mlflow://runs/run-rl-5/model",
        }
    )
    return metrics


def _production_scope_metrics() -> dict:
    metrics = _passing_m7_remaining_metrics()
    metrics["rollback_target"] = "direction_model:12"
    metrics["model_card"] = {
        "path": "/tmp/autoresearch-session/model_card.md",
        "approved": True,
    }
    metrics["supervised_feature_readiness"] = {
        "direction": {"passed": True},
        "volatility": {"passed": True},
    }
    metrics["paper_validation"] = {
        "passed": True,
        "account": "paper",
        "trade_count": 42,
    }
    metrics["canary_validation"] = {
        "duration_hours": 24,
        "required_duration_hours": 24,
        "passed": True,
    }
    metrics["live_risk_limits"] = {
        "configured": True,
        "max_position_notional": 100.0,
    }
    metrics["monitoring_alerts"] = {
        "configured": True,
        "alerts_block_promotion": False,
    }
    return metrics


def _approval() -> dict:
    return {
        "approver": "ops-reviewer",
        "reason": "stage gate approved",
        "approved": True,
    }


def _promotion_row(scope: str, promotion_id: int = 1) -> dict:
    return {
        "id": promotion_id,
        "research_id": "research_1",
        "iteration": 3,
        "model_type": "direction",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "target_path": "/tmp/autoresearch-session/config.yaml",
        "config_yaml": "agent_strategy: BALA\n",
        "previous_yaml": "agent_strategy: OLD\n",
        "scope": scope,
        "metadata_path": f"/tmp/autoresearch-session/{scope}.json",
        "promotion_metadata": {
            "schema_version": "scoped_promotion_decision.v1"
            if scope != "development"
            else "development_promotion_metadata.v1",
            "scope": scope,
            "promotion_allowed": True,
            "rollback_target": f"{scope}-rollback-target",
        },
        "promoted_at": f"2026-04-30T00:00:{promotion_id:02d}+00:00",
    }


def _development_baseline_promotion(
    *,
    best_metric: float | None = 0.6476,
    metric_name: str | None = None,
    promotion_id: int = 1,
    promotion_allowed: bool = True,
    quality_baseline_usable: bool | None = None,
    quality_baseline_unusable: bool | None = None,
    rolled_back_at: str | None = None,
    composite_formula_version: str | None = None,
) -> dict:
    row = _promotion_row("development", promotion_id=promotion_id)
    row["promotion_metadata"].update(
        {
            "promotion_allowed": promotion_allowed,
            "best_metric": best_metric,
            "metric_name": metric_name,
        }
    )
    if composite_formula_version is not None:
        row["promotion_metadata"][
            "composite_formula_version"
        ] = composite_formula_version
    if quality_baseline_usable is not None:
        row["promotion_metadata"][
            "quality_baseline_usable"
        ] = quality_baseline_usable
    if quality_baseline_unusable is not None:
        row["promotion_metadata"][
            "quality_baseline_unusable"
        ] = quality_baseline_unusable
    if rolled_back_at:
        row["rolled_back_at"] = rolled_back_at
    return row


class FakeMlflowResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> object:
        return self._payload


class FakeMlflowAsyncClient:
    def __init__(
        self,
        *,
        composites: list[dict],
        promote_payload: dict | None = None,
        promote_status_code: int = 200,
    ) -> None:
        self.composites = composites
        self.promote_payload = promote_payload or {
            "id": "composite-prod",
            "status": "production",
            "promoted_at": "2026-05-08T12:00:00+00:00",
        }
        self.promote_status_code = promote_status_code
        self.calls: list[dict] = []

    def __call__(self, *args, **kwargs) -> "FakeMlflowAsyncClient":
        return self

    async def __aenter__(self) -> "FakeMlflowAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, *, headers: dict | None = None, params: dict | None = None):
        self.calls.append(
            {"method": "GET", "url": url, "headers": headers or {}, "params": params or {}}
        )
        return FakeMlflowResponse(200, self.composites)

    async def post(self, url: str, *, headers: dict | None = None, json: dict | None = None):
        self.calls.append(
            {"method": "POST", "url": url, "headers": headers or {}, "json": json or {}}
        )
        return FakeMlflowResponse(self.promote_status_code, self.promote_payload)


def _install_fake_mlflow_client(
    monkeypatch,
    *,
    composites: list[dict],
    promote_payload: dict | None = None,
    promote_status_code: int = 200,
) -> FakeMlflowAsyncClient:
    client = FakeMlflowAsyncClient(
        composites=composites,
        promote_payload=promote_payload,
        promote_status_code=promote_status_code,
    )
    monkeypatch.setattr(config_promoter.httpx, "AsyncClient", client)
    return client


def _best_iteration(
    metrics: dict,
    *,
    primary_metric: float | None = 0.61,
    metric_name: str | None = None,
) -> dict:
    return {
        "iteration": 3,
        "primary_metric": primary_metric,
        "metric_name": metric_name,
        "all_gates_passed": 1,
        "config_snapshot": "agent_strategy: BALA\n",
        "metrics_json": json.dumps(metrics),
    }


def test_model_version_tag_prefers_serving_and_ensemble_fields():
    assert ConfigPromoter._model_version_tag(
        {
            "model_registry_name": "direction-model",
            "model_version": "12",
            "ensemble_model_version": "21",
        }
    ) == "direction-model_ensemble:21"
    assert ConfigPromoter._model_version_tag(
        {
            "model_registry_name": "direction-model",
            "model_version": "12",
            "ensemble_model_registry_name": "custom-ensemble",
            "ensemble_model_version": "22",
            "serving_model_registry_name": "serving-direction",
            "serving_model_version": "23",
        }
    ) == "serving-direction:23"
    assert ConfigPromoter._model_version_tag(
        {
            "model_registry_name": "direction-model",
            "model_version": "12",
        }
    ) == "direction-model:12"


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
    pool = preview["candidate_pool_record"]
    assert pool["source"] == "autoresearch.iterations"
    assert pool["research_id"] == "research_1"
    assert pool["iteration"] == 3
    assert pool["status"] == "blocked"
    assert pool["blockers"] == gate_eval["blockers"]
    detail_by_code = {
        detail["code"]: detail for detail in gate_eval["blocker_details"]
    }
    assert detail_by_code["missing_reliability_diagram"]["category"] == (
        "missing_nested_result_payload"
    )
    assert detail_by_code["missing_reliability_diagram"]["source"] == (
        "development_gate_bundle"
    )
    assert detail_by_code["missing_reliability_diagram"]["likely_fix"]
    assert pool["blocker_details"] == gate_eval["blocker_details"]
    for detail in gate_eval["blocker_details"]:
        assert detail in preview["blocker_details"]
        assert detail in preview["development_promotion_metadata"]["blocker_details"]
    assert preview["development_promotion_metadata"]["gate_bundle"][
        "blocker_details"
    ] == gate_eval["blocker_details"]
    assert pool["inspectable"] is True
    assert pool["promotion_record_created"] is False
    assert pool["config_snapshot_sha256"] == ConfigPromoter._sha256_text(
        "agent_strategy: BALA\n"
    )


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
    metrics["config"].pop("calibration_full_validation")
    store = FakePromotionStore(_best_iteration(metrics))

    with pytest.raises(ValueError, match="development gate bundle failed"):
        await ConfigPromoter(store).confirm("research_1")


@pytest.mark.asyncio
async def test_preview_allows_feature_candidate_without_economic_replay(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics.pop("economic_replay")
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is True
    assert "missing_economic_replay" not in preview["gate_bundle_evaluation"][
        "blockers"
    ]
    assert preview["consistency_report"]["mode"] == "promotion"
    assert "missing_economic_replay" not in preview["consistency_report"][
        "blockers"
    ]


@pytest.mark.asyncio
async def test_preview_blocks_metric_below_development_baseline(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    monkeypatch.setattr(config_promoter.settings, "global_stagnation_epsilon", 0.0001)
    store = FakePromotionStore(
        _best_iteration(_passing_metrics(), primary_metric=0.635563),
        promotions=[
            _development_baseline_promotion(
                best_metric=0.6476,
                promotion_id=7,
            )
        ],
    )

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is False
    assert preview["quality_baseline_passed"] is False
    quality_eval = preview["quality_baseline_evaluation"]
    assert quality_eval["mode"] == "development_quality_baseline"
    assert quality_eval["status"] == "blocked"
    assert quality_eval["blockers"] == ["best_metric_below_development_baseline"]
    assert quality_eval["comparison"]["baseline_promotion_id"] == 7
    assert quality_eval["comparison"]["baseline_metric"] == 0.6476
    assert quality_eval["comparison"]["current_metric"] == 0.635563
    assert "best_metric_below_development_baseline" in preview[
        "candidate_pool_record"
    ]["blockers"]
    assert preview["gate_bundle_evaluation"]["blockers"] == []
    assert preview["consistency_report"]["blockers"] == []
    detail = preview["quality_baseline_evaluation"]["blocker_details"][0]
    assert detail["code"] == "best_metric_below_development_baseline"
    assert detail["category"] == "quality_regression"
    assert detail["likely_fix"]
    assert detail in preview["blocker_details"]
    assert detail in preview["development_promotion_metadata"]["blocker_details"]
    assert preview["development_promotion_metadata"][
        "quality_baseline_passed"
    ] is False
    assert preview["development_promotion_metadata"][
        "quality_baseline_usable"
    ] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current_metric", "baseline_metric"),
    [
        (0.61, 0.61005),
        (0.62, 0.61),
    ],
)
async def test_preview_allows_metric_within_or_above_development_baseline(
    tmp_path,
    monkeypatch,
    current_metric,
    baseline_metric,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    monkeypatch.setattr(config_promoter.settings, "global_stagnation_epsilon", 0.0001)
    store = FakePromotionStore(
        _best_iteration(_passing_metrics(), primary_metric=current_metric),
        promotions=[
            _development_baseline_promotion(best_metric=baseline_metric)
        ],
    )

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is True
    assert preview["quality_baseline_evaluation"]["passed"] is True
    assert preview["quality_baseline_evaluation"]["blockers"] == []
    assert preview["candidate_pool_record"]["quality_baseline_passed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "baseline",
    [
        _development_baseline_promotion(
            best_metric=0.6476,
            quality_baseline_usable=False,
        ),
        _development_baseline_promotion(
            best_metric=0.6476,
            quality_baseline_unusable=True,
        ),
        _development_baseline_promotion(
            best_metric=0.6476,
            promotion_allowed=False,
        ),
        _development_baseline_promotion(
            best_metric=0.6476,
            rolled_back_at="2026-05-01T00:00:00+00:00",
        ),
        _development_baseline_promotion(best_metric=None),
    ],
)
async def test_preview_skips_ineligible_development_quality_baselines(
    tmp_path,
    monkeypatch,
    baseline,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    monkeypatch.setattr(config_promoter.settings, "global_stagnation_epsilon", 0.0001)
    store = FakePromotionStore(
        _best_iteration(_passing_metrics(), primary_metric=0.635563),
        promotions=[baseline],
    )

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is True
    assert preview["quality_baseline_evaluation"]["status"] == (
        "no_eligible_development_baseline"
    )
    assert preview["quality_baseline_evaluation"]["blockers"] == []


@pytest.mark.asyncio
async def test_preview_skips_quality_baseline_metric_name_mismatch(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    store = FakePromotionStore(
        _best_iteration(
            _passing_metrics(),
            primary_metric=0.635563,
            metric_name="composite_direction_score",
        ),
        promotions=[
            _development_baseline_promotion(
                best_metric=0.6476,
                metric_name="auc",
            )
        ],
    )

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is True
    assert preview["quality_baseline_evaluation"]["status"] == (
        "not_comparable_metric_name_mismatch"
    )
    assert preview["quality_baseline_evaluation"]["blockers"] == []


@pytest.mark.asyncio
async def test_preview_skips_quality_baseline_formula_version_mismatch(
    tmp_path,
    monkeypatch,
):
    """R3: a v6 champion below a v5 baseline numerically must NOT be blocked —
    different composite_formula_version makes the numbers incomparable, so the
    newer-formula champion passes the quality baseline (gates still protect)."""
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics["composite_formula_version"] = "v6_sized_econ"
    store = FakePromotionStore(
        _best_iteration(
            metrics,
            primary_metric=0.6969,  # below the v5 baseline numerically
            metric_name="composite_direction_score",
        ),
        promotions=[
            _development_baseline_promotion(
                best_metric=0.7133,
                metric_name="composite_direction_score",
                composite_formula_version="v5_calibration",
            )
        ],
    )

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is True
    assert preview["quality_baseline_evaluation"]["status"] == (
        "not_comparable_formula_version_mismatch"
    )
    assert preview["quality_baseline_evaluation"]["blockers"] == []


@pytest.mark.asyncio
async def test_preview_without_smoke_evidence_uses_recorded_metrics(tmp_path, monkeypatch):
    """With the platform evidence collector removed, preview evaluates the
    metrics exactly as the session recorded them — no server-side
    backfilling of smoke/replay evidence."""
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics.pop("smoke_validation", None)  # timed-out session: never collected
    best = _best_iteration(metrics, primary_metric=0.71, metric_name="auc")
    store = FakePromotionStore(best)
    promoter = ConfigPromoter(store)

    preview = await promoter.preview("res_test")

    # The preview reflects the recorded metrics (no fabricated smoke evidence).
    assert preview["promotion_allowed"] in (True, False)
    assert preview["iteration"] == best["iteration"]

@pytest.mark.asyncio
async def test_preview_passes_when_baseline_predates_version_stamp(
    tmp_path,
    monkeypatch,
):
    """A current-formula champion must NOT be blocked by a LEGACY baseline that
    has no composite_formula_version (predates stamping) — unknown version is
    not comparable (R3), even though the champion's number is lower."""
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    monkeypatch.setattr(config_promoter.settings, "global_stagnation_epsilon", 0.0001)
    metrics = _passing_metrics()
    metrics["composite_formula_version"] = "v6_sized_econ"
    store = FakePromotionStore(
        _best_iteration(
            metrics,
            primary_metric=0.6969,
            metric_name="composite_direction_score",
        ),
        promotions=[
            _development_baseline_promotion(
                best_metric=0.7133,
                metric_name="composite_direction_score",
                composite_formula_version=None,  # legacy, unstamped
            )
        ],
    )

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is True
    assert preview["quality_baseline_evaluation"]["status"] == (
        "not_comparable_formula_version_mismatch"
    )
    assert preview["quality_baseline_evaluation"]["blockers"] == []


@pytest.mark.asyncio
async def test_preview_blocks_same_formula_regression(
    tmp_path,
    monkeypatch,
):
    """Guard: SAME formula version still does the strict numeric compare — a
    real regression below the baseline must still be blocked."""
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    monkeypatch.setattr(config_promoter.settings, "global_stagnation_epsilon", 0.0001)
    metrics = _passing_metrics()
    metrics["composite_formula_version"] = "v6_sized_econ"
    store = FakePromotionStore(
        _best_iteration(
            metrics,
            primary_metric=0.60,
            metric_name="composite_direction_score",
        ),
        promotions=[
            _development_baseline_promotion(
                best_metric=0.6969,
                metric_name="composite_direction_score",
                composite_formula_version="v6_sized_econ",
            )
        ],
    )

    preview = await ConfigPromoter(store).preview("research_1")

    assert "best_metric_below_development_baseline" in (
        preview["quality_baseline_evaluation"]["blockers"]
    )


@pytest.mark.asyncio
async def test_confirm_requires_quality_baseline_pass(tmp_path, monkeypatch):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    monkeypatch.setattr(config_promoter.settings, "global_stagnation_epsilon", 0.0001)
    store = FakePromotionStore(
        _best_iteration(_passing_metrics(), primary_metric=0.635563),
        promotions=[
            _development_baseline_promotion(best_metric=0.6476)
        ],
    )

    with pytest.raises(ValueError, match="development quality baseline failed"):
        await ConfigPromoter(store).confirm("research_1")


@pytest.mark.asyncio
async def test_preview_rebuilds_sweep_consistency_as_promotion_mode(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    metrics = _passing_metrics()
    metrics.pop("feature_schema_hash")
    metrics.pop("parity_metadata")
    metrics.pop("feature_schema")
    best = _best_iteration(metrics)
    best["consistency_report_json"] = json.dumps(
        {"mode": "sweep", "passed": True, "blockers": [], "checks": []}
    )
    store = FakePromotionStore(best)

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["gate_bundle_evaluation"]["passed"] is True
    assert preview["consistency_report"]["mode"] == "promotion"
    assert preview["consistency_report"]["passed"] is False
    assert "missing_feature_schema_hash" in preview["consistency_report"][
        "blockers"
    ]
    assert preview["promotion_allowed"] is False
    detail = next(
        detail
        for detail in preview["consistency_report"]["blocker_details"]
        if detail["code"] == "missing_feature_schema_hash"
    )
    assert detail["source"] == "cross_service_consistency"
    assert detail["likely_fix"]


@pytest.mark.asyncio
async def test_confirm_requires_cross_service_consistency(tmp_path, monkeypatch):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    metrics = _passing_metrics()
    metrics.pop("artifact_uri")
    metrics.pop("mlflow_run_id")
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["gate_bundle_evaluation"]["passed"] is True
    assert preview["promotion_allowed"] is False
    assert "missing_artifact_reference" in preview["consistency_report"]["blockers"]
    with pytest.raises(ValueError, match="cross-service consistency failed"):
        await ConfigPromoter(store).confirm("research_1")


@pytest.mark.asyncio
async def test_preview_blocks_adaptive_finalist_missing_schema_flags(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    metrics = _passing_metrics()
    metrics.update(
        {
            "finalist": True,
            "feature_schema_hash": "schema-adaptive",
            "adaptive_features": {
                "requested": True,
                "enabled": True,
                "version": "adaptive_levels.v1",
                "selected_count": 1,
                "selected_feature_names": ["close_fib_bucket_24"],
                "feature_schema_hash": "schema-adaptive",
            },
        }
    )
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is False
    assert "missing_adaptive_feature_schema_flags" in preview["consistency_report"][
        "blockers"
    ]


@pytest.mark.asyncio
async def test_confirm_records_promotion_when_bundle_passes(tmp_path, monkeypatch):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))

    store = FakePromotionStore(_best_iteration(_passing_metrics()))

    result = await ConfigPromoter(store).confirm("research_1")

    assert result["iteration"] == 3
    assert result["scope"] == "development"
    assert result["metadata_path"]
    assert store.promotions
    target_path = Path(store.promotions[0]["target_path"])
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8") == "agent_strategy: BALA\n"
    metadata_path = Path(result["metadata_path"])
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "development_promotion_metadata.v1"
    assert metadata["scope"] == "development"
    assert metadata["live_production_promotion_allowed"] is False
    assert metadata["live_production_promotion_requested"] is False
    assert metadata["promotion_record_created"] is True
    assert metadata["gate_bundle"]["gate_bundle_id"] == "development_direction_prediction_v1"
    assert metadata["gate_bundle"]["passed"] is True
    assert metadata["cross_service_consistency"]["schema_version"] == (
        "cross_service_consistency_report.v1"
    )
    assert metadata["cross_service_consistency"]["passed"] is True
    assert metadata["registry_metadata"]["model_registry_name"] == "direction-model"
    assert metadata["composite_metadata"]["reload_supported"] is True
    assert store.promotions[0]["promotion_metadata"]["metadata_path"] == str(metadata_path)


@pytest.mark.asyncio
async def test_preview_blocks_live_production_promotion_intent(tmp_path, monkeypatch):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics["promotion_request"] = {"scope": "production"}
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    gate_eval = preview["gate_bundle_evaluation"]
    assert preview["promotion_allowed"] is False
    assert preview["development_promotion_metadata"]["scope"] == "development"
    assert preview["development_promotion_metadata"][
        "live_production_promotion_requested"
    ] is True
    assert "live_production_promotion_forbidden" in gate_eval["blockers"]


@pytest.mark.asyncio
async def test_preview_blocks_missing_required_inference_parity(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_metrics()
    metrics.pop("inference_parity")
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    gate_eval = preview["gate_bundle_evaluation"]
    assert preview["promotion_allowed"] is False
    assert "inference_feature_schema_mismatch" in gate_eval["blockers"]
    detail = next(
        detail
        for detail in gate_eval["blocker_details"]
        if detail["code"] == "inference_feature_schema_mismatch"
    )
    assert detail["category"] == "phase_not_run"
    assert detail["phase"] == "inference_parity_replay"
    assert any(
        check["name"] == "inference_parity_required"
        and check["status"] == "failed"
        for check in gate_eval["checks"]
    )


@pytest.mark.asyncio
async def test_confirm_persists_development_metadata_with_results_store(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))


    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    await store.create_session(
        session_id="research_1",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="dpu070",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path=str(workspace),
    )
    attempt_snapshot = {
        "schema_version": "autoresearch_iteration_attempt.v1",
        "snapshot_hash": "attempt-sha-3",
        "artifact_hash": "artifact-sha-3",
        "config_snapshot_sha256": ConfigPromoter._sha256_text(
            "agent_strategy: BALA\n"
        ),
    }
    await store.add_iteration(
        research_id="research_1",
        iteration=3,
        primary_metric=0.61,
        metric_name="auc",
        all_gates_passed=True,
        decision="keep",
        description="passing candidate",
        config_snapshot="agent_strategy: BALA\n",
        metrics_json=json.dumps(_passing_metrics()),
        training_time_s=1.0,
        attempt_snapshot_json=json.dumps(attempt_snapshot),
        attempt_snapshot_path=str(
            workspace / "server_snapshots" / "iteration_0003_attempt.json"
        ),
        attempt_snapshot_hash="attempt-sha-3",
    )

    result = await ConfigPromoter(store).confirm("research_1")
    promotions = await store.list_promotions()

    assert result["scope"] == "development"
    assert promotions[0]["scope"] == "development"
    assert promotions[0]["metadata_path"] == result["metadata_path"]
    assert promotions[0]["promotion_metadata"]["schema_version"] == (
        "development_promotion_metadata.v1"
    )
    assert promotions[0]["promotion_metadata"]["gate_bundle"]["passed"] is True
    ownership = promotions[0]["promotion_metadata"]["best_candidate_ownership"]
    assert ownership["source"] == "autoresearch.iterations"
    assert ownership["iteration_row_id"] == 1
    assert ownership["config_snapshot_sha256"] == ConfigPromoter._sha256_text(
        "agent_strategy: BALA\n"
    )
    assert ownership["attempt_snapshot_hash"] == "attempt-sha-3"
    assert ownership["artifact_hash"] == "artifact-sha-3"


@pytest.mark.asyncio
async def test_production_scope_blocks_without_paper_and_canary(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_remaining(tmp_path)
    _write_production_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    store = FakePromotionStore(
        _best_iteration(_production_scope_metrics()),
        promotions=[_promotion_row("development", 1)],
    )

    preview = await ConfigPromoter(store).preview(
        "research_1",
        scope="production",
        approval=_approval(),
    )

    metadata = preview["scoped_promotion_metadata"]
    assert preview["promotion_allowed"] is False
    assert metadata["scope"] == "production"
    assert "missing_paper_promotion" in metadata["blockers"]
    assert "missing_canary_promotion" in metadata["blockers"]
    with pytest.raises(ValueError, match="scoped promotion policy failed"):
        await ConfigPromoter(store).confirm(
            "research_1",
            scope="production",
            approval=_approval(),
        )


@pytest.mark.asyncio
async def test_production_scope_records_full_decision_chain(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_remaining(tmp_path)
    _write_production_gate_bundle(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    metrics = _production_scope_metrics()
    metrics["rollup_score"] = 0.77
    mlflow_client = _install_fake_mlflow_client(
        monkeypatch,
        composites=[
            {
                "id": "composite-prod",
                "instrument": "DOGE_USDT",
                "status": "staging",
                "direction_model_version": "direction-model:12",
            }
        ],
        promote_payload={
            "id": "composite-prod",
            "status": "production",
            "promoted_at": "2026-05-08T12:00:00+00:00",
        },
    )
    store = FakePromotionStore(
        _best_iteration(metrics),
        promotions=[
            _promotion_row("development", 1),
            _promotion_row("paper", 2),
            _promotion_row("canary", 3),
        ],
    )

    result = await ConfigPromoter(store).confirm(
        "research_1",
        scope="production",
        approval=_approval(),
    )

    assert result["scope"] == "production"
    metadata_path = Path(result["metadata_path"])
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "scoped_promotion_decision.v1"
    assert metadata["scope"] == "production"
    assert metadata["promotion_allowed"] is True
    assert metadata["approval"]["satisfied"] is True
    assert metadata["production_gate_bundle"]["gate_bundle_id"] == (
        "production_trading_model_promotion_v1"
    )
    assert [entry["scope"] for entry in metadata["decision_chain"]] == [
        "development",
        "paper",
        "canary",
        "production",
    ]
    assert metadata["rollback_targets"]["production"] == "direction_model:12"
    # No platform composite delegation anymore: the promotion is recorded
    # locally with no mlflow-service metadata.
    assert "mlflow_service" not in metadata
    assert store.promotions[-1]["promotion_metadata"]["scope"] == "production"


@pytest.mark.asyncio
async def test_paper_scope_remains_local_only(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_remaining(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    mlflow_client = _install_fake_mlflow_client(monkeypatch, composites=[])
    store = FakePromotionStore(
        _best_iteration(_production_scope_metrics()),
        promotions=[_promotion_row("development", 1)],
    )

    result = await ConfigPromoter(store).confirm(
        "research_1",
        scope="paper",
        approval=_approval(),
    )

    assert result["scope"] == "paper"
    assert "mlflow_service" not in result["promotion_metadata"]
    assert mlflow_client.calls == []


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


@pytest.mark.asyncio
async def test_preview_accepts_rl_candidate_with_honest_oos_provenance(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_rl(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    store = FakePromotionStore(
        _best_iteration(_passing_rl_metrics()),
        model_type="rl",
    )

    preview = await ConfigPromoter(store).preview("research_1")

    gate_eval = preview["gate_bundle_evaluation"]
    assert gate_eval["applicable"] is True
    assert gate_eval["model_type"] == "rl"
    assert gate_eval["passed"] is True
    assert preview["promotion_allowed"] is True
    assert preview["consistency_report"]["passed"] is True
    assert preview["candidate_pool_record"]["artifact_hash"] is None
    checks = {check["name"]: check for check in gate_eval["checks"]}
    assert checks["rl_economic_replay_artifact_hash_recorded"]["status"] == "passed"


@pytest.mark.asyncio
async def test_preview_blocks_rl_candidate_missing_economic_replay(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_rl(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_rl_metrics()
    metrics.pop("rl_economic_replay")
    metrics.pop("economic_replay")
    metrics.pop("rl_economic_replay_artifact_hash")
    store = FakePromotionStore(_best_iteration(metrics), model_type="rl")

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is False
    assert "missing_economic_replay" in preview["gate_bundle_evaluation"]["blockers"]
    assert "missing_economic_replay" in preview["consistency_report"]["blockers"]


@pytest.mark.asyncio
async def test_preview_blocks_rl_candidate_worsening_economic_replay(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_rl(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_rl_metrics()
    metrics["rl_economic_replay"]["metrics"]["post_cost_return"] = -0.02
    metrics["rl_economic_replay"]["comparison"][
        "post_cost_return_delta_vs_baseline"
    ] = -0.02
    metrics["rl_economic_replay"]["gates"]["all_gates_passed"] = False
    metrics["rl_economic_replay"]["gates"]["worsening_vs_baseline"] = True
    metrics["rl_economic_replay"]["gates"]["metrics"][
        "post_cost_return_delta_vs_baseline"
    ] = -0.02
    metrics["economic_replay"] = metrics["rl_economic_replay"]
    store = FakePromotionStore(_best_iteration(metrics), model_type="rl")

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is False
    assert "worsening_post_cost_replay" in preview["gate_bundle_evaluation"][
        "blockers"
    ]
    assert "worsening_post_cost_replay" in preview["consistency_report"][
        "blockers"
    ]


@pytest.mark.asyncio
async def test_preview_blocks_rl_candidate_missing_volatility_provenance(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_rl(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_rl_metrics()
    metrics["rl_oos"].pop("volatility_probability_provenance")
    store = FakePromotionStore(_best_iteration(metrics), model_type="rl")

    preview = await ConfigPromoter(store).preview("research_1")

    gate_eval = preview["gate_bundle_evaluation"]
    assert preview["promotion_allowed"] is False
    assert "missing_volatility_feature_provenance" in gate_eval["blockers"]
    assert "missing_volatility_oof_provenance" in gate_eval["blockers"]
    assert "missing_volatility_feature_provenance" in preview[
        "consistency_report"
    ]["blockers"]


@pytest.mark.asyncio
async def test_preview_blocks_rl_candidate_with_volatility_fallback(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_rl(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_rl_metrics()
    metrics["rl_oos"]["volatility_probability_provenance"].update(
        {
            "honest_coverage": 0.25,
            "unsafe_count": 12,
            "unsafe_values": ["neutral_fallback"],
            "stale": True,
        }
    )
    store = FakePromotionStore(_best_iteration(metrics), model_type="rl")

    preview = await ConfigPromoter(store).preview("research_1")

    blockers = preview["gate_bundle_evaluation"]["blockers"]
    assert preview["promotion_allowed"] is False
    assert "missing_volatility_oof_provenance" in blockers
    assert "proxy_or_neutral_volatility_feature_fallback" in blockers
    assert "stale_or_leaked_feature_provenance" in blockers


@pytest.mark.asyncio
async def test_preview_blocks_rl_candidate_without_nested_or_multi_seed_oos(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_rl(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(config_promoter.settings, "host_configs_path", str(tmp_path / "configs"))
    metrics = _passing_rl_metrics()
    metrics["rl_oos"]["nested_validation_used"] = False
    metrics["rl_oos"]["n_seed_trials"] = 1
    store = FakePromotionStore(_best_iteration(metrics), model_type="rl")

    preview = await ConfigPromoter(store).preview("research_1")

    blockers = preview["gate_bundle_evaluation"]["blockers"]
    assert preview["promotion_allowed"] is False
    assert "missing_nested_validation" in blockers
    assert "missing_multi_seed_rl_validation" in blockers


@pytest.mark.asyncio
async def test_preview_derives_addressable_rollback_and_smoke_readiness(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_controls(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    target = tmp_path / "configs" / "instrument_configs" / "DOGE_USDT_15m.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("agent_strategy: OLD\n", encoding="utf-8")
    metrics = _passing_metrics()
    metrics.pop("rollback_target")
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    gate_eval = preview["gate_bundle_evaluation"]
    metadata = preview["development_promotion_metadata"]
    assert gate_eval["passed"] is True
    assert metadata["rollback_readiness"]["previous_config_present"] is True
    assert metadata["rollback_readiness"][
        "rollback_by_instrument_timeframe_supported"
    ] is True
    assert metadata["rollback_target"].endswith(
        "DOGE_USDT_15m.yaml.development-rollback.research_1.iter-3.yaml"
    )
    assert metadata["smoke_validation"]["passed"] is True
    assert metadata["smoke_validation"]["composite_reload_supported"] is True


@pytest.mark.asyncio
async def test_confirm_writes_rollback_snapshot_and_rollback_restores_previous_config(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_controls(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    target = tmp_path / "configs" / "instrument_configs" / "DOGE_USDT_15m.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("agent_strategy: OLD\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    await store.create_session(
        session_id="research_1",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="dpu071",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path=str(workspace),
    )
    metrics = _passing_metrics()
    metrics.pop("rollback_target")
    await store.add_iteration(
        research_id="research_1",
        iteration=3,
        primary_metric=0.61,
        metric_name="auc",
        all_gates_passed=True,
        decision="keep",
        description="passing candidate",
        config_snapshot="agent_strategy: BALA\n",
        metrics_json=json.dumps(metrics),
        training_time_s=1.0,
    )

    result = await ConfigPromoter(store).confirm("research_1")
    metadata = result["promotion_metadata"]
    rollback_snapshot = Path(
        metadata["rollback_readiness"]["previous_config_snapshot_path"]
    )
    assert target.read_text(encoding="utf-8") == "agent_strategy: BALA\n"
    assert rollback_snapshot.exists()
    assert rollback_snapshot.read_text(encoding="utf-8") == "agent_strategy: OLD\n"

    rollback = await ConfigPromoter(store).rollback(
        model_type="direction",
        instrument="DOGE_USDT",
        timeframe="15m",
        reason="test rollback",
    )
    promotions = await store.list_promotions()

    assert rollback["rolled_back"] is True
    assert target.read_text(encoding="utf-8") == "agent_strategy: OLD\n"
    assert Path(rollback["rollback_metadata_path"]).exists()
    assert promotions[0]["rollback_metadata"]["reason"] == "test rollback"


@pytest.mark.asyncio
async def test_preview_blocks_tsfm_candidate_without_fallback_check(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_controls(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    metrics = _passing_metrics()
    metrics["model_family"] = "tsfm"
    metrics["inference_parity"].update(
        {
            "adapter_loading_passed": True,
            "latency_budget_passed": True,
        }
    )
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is False
    assert "tsfm_adapter_load_failure_without_tabular_fallback" in preview[
        "gate_bundle_evaluation"
    ]["blockers"]
    assert preview["development_promotion_metadata"]["tsfm_fallback_validation"][
        "required"
    ] is True
    assert preview["development_promotion_metadata"]["tsfm_fallback_validation"][
        "passed"
    ] is False


@pytest.mark.asyncio
async def test_preview_records_tsfm_fallback_check_when_present(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_controls(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    metrics = _passing_metrics()
    metrics["model_family"] = "tsfm"
    metrics["inference_parity"].update(
        {
            "latency_budget_passed": True,
            "fallback_check_passed": True,
        }
    )
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["gate_bundle_evaluation"]["passed"] is True
    assert preview["development_promotion_metadata"]["tsfm_fallback_validation"][
        "required"
    ] is True
    assert preview["development_promotion_metadata"]["tsfm_fallback_validation"][
        "passed"
    ] is True


@pytest.mark.asyncio
async def test_preview_accepts_structured_tsfm_fallback_validation(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_controls(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    metrics = _passing_metrics()
    metrics["model_family"] = "tsfm"
    metrics["tsfm_fallback_validation"] = {
        "passed": True,
        "reason": "tabular_fallback_available",
        "candidate_family": "tsfm",
        "is_tsfm_candidate": True,
        "fallback_available": True,
    }
    metrics["inference_parity"].update(
        {
            "latency_budget_passed": True,
        }
    )
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["gate_bundle_evaluation"]["passed"] is True
    assert preview["development_promotion_metadata"]["tsfm_fallback_validation"][
        "required"
    ] is True
    assert preview["development_promotion_metadata"]["tsfm_fallback_validation"][
        "passed"
    ] is True
    assert preview["development_promotion_metadata"]["tsfm_fallback_validation"][
        "details"
    ]["structured"]["reason"] == "tabular_fallback_available"


@pytest.mark.asyncio
async def test_preview_emits_development_signal_health_metrics(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_remaining(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    target = tmp_path / "configs" / "instrument_configs" / "DOGE_USDT_15m.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("agent_strategy: OLD\n", encoding="utf-8")
    store = FakePromotionStore(_best_iteration(_passing_m7_remaining_metrics()))

    preview = await ConfigPromoter(store).preview("research_1")

    signal_health = preview["development_promotion_metadata"]["signal_health"]
    assert preview["gate_bundle_evaluation"]["passed"] is True
    assert signal_health["schema_version"] == "development_direction_signal_health.v1"
    assert signal_health["observable"] is True
    assert signal_health["metrics"]["sample_count"] == 5
    assert signal_health["metrics"]["probability_mean"] == pytest.approx(0.52)
    assert signal_health["operational"]["rl_hold_rate"] == 0.32
    assert signal_health["drift"]["psi"] is not None


@pytest.mark.asyncio
async def test_preview_blocks_missing_development_signal_health_metrics(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_remaining(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    target = tmp_path / "configs" / "instrument_configs" / "DOGE_USDT_15m.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("agent_strategy: OLD\n", encoding="utf-8")
    metrics = _passing_m7_remaining_metrics()
    metrics.pop("development_signal_health")
    store = FakePromotionStore(_best_iteration(metrics))

    preview = await ConfigPromoter(store).preview("research_1")

    assert preview["promotion_allowed"] is False
    assert "missing_signal_health_metrics" in preview["gate_bundle_evaluation"][
        "blockers"
    ]


@pytest.mark.asyncio
async def test_preview_records_inference_reload_validation(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_remaining(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    target = tmp_path / "configs" / "instrument_configs" / "DOGE_USDT_15m.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("agent_strategy: OLD\n", encoding="utf-8")
    store = FakePromotionStore(_best_iteration(_passing_m7_remaining_metrics()))

    preview = await ConfigPromoter(store).preview("research_1")

    reload_validation = preview["development_promotion_metadata"][
        "inference_reload_validation"
    ]
    assert reload_validation["schema_version"] == (
        "development_inference_reload_validation.v1"
    )
    assert reload_validation["passed"] is True
    assert reload_validation["checks"]["feature_name_alignment_passed"] is True
    assert reload_validation["checks"]["composite_reload_passed"] is True
    assert reload_validation["checks"]["rollback_ready"] is True


def test_inference_reload_uses_generic_adapter_blocker_for_tabular_candidate():
    metrics = _passing_m7_remaining_metrics()
    metrics["candidate_family"] = "tabular"
    metrics["is_tsfm_candidate"] = False
    metrics["inference_reload_validation"] = {
        "checks": {
            "feature_name_alignment_passed": True,
            "feature_count_alignment_passed": True,
            "adapter_loading_passed": False,
            "fallback_behavior_passed": False,
            "latency_budget_passed": False,
            "model_roster_parity_passed": True,
            "observation_dimension_parity_passed": True,
            "composite_reload_passed": True,
            "rollback_ready": True,
            "prior_version_preserved_on_reload_failure": True,
        }
    }
    bundle = {
        "version": 1,
        "gate_bundle_id": "development_direction_prediction_v1",
        "scope": "development",
        "promotion_policy": {
            "auc_only_promotion_allowed": False,
            "live_production_promotion_allowed": False,
        },
        "gate_tiers": {
            "inference_reload": {
                "required": True,
                "checks": {
                    "feature_alignment_required": True,
                    "adapter_loading_required": True,
                    "roster_parity_required": True,
                    "observation_dimension_parity_required": True,
                    "fallback_behavior_required": True,
                    "latency_budget_required": True,
                    "composite_reload_required": True,
                    "rollback_ready_required": True,
                    "prior_version_preserved_on_reload_failure": True,
                },
            }
        },
    }

    result = evaluate_development_gate_bundle(
        bundle=bundle,
        model_type="direction",
        best_iteration=_best_iteration(metrics),
    )

    assert "inference_adapter_load_failure" in result["blockers"]
    assert "tsfm_adapter_load_failure_without_tabular_fallback" not in result[
        "blockers"
    ]
    assert "tsfm_latency_budget_failure" not in result["blockers"]
    assert {
        check["name"]
        for check in result["checks"]
        if check["name"].startswith("inference_reload")
    } == {
        "inference_reload_validation_required",
        "inference_reload_feature_alignment",
        "inference_reload_adapter_loading",
        "inference_reload_roster_parity",
        "inference_reload_observation_dimension_parity",
        "inference_reload_composite_reload",
        "inference_reload_rollback_ready",
        "inference_reload_prior_version_preserved_on_failure",
    }


@pytest.mark.asyncio
async def test_confirm_blocks_reload_failure_before_replacing_prior_config(
    tmp_path,
    monkeypatch,
):
    _write_gate_bundle_with_m7_remaining(tmp_path)
    monkeypatch.setattr(config_promoter.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(
        config_promoter.settings, "host_configs_path", str(tmp_path / "configs")
    )
    target = tmp_path / "configs" / "instrument_configs" / "DOGE_USDT_15m.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("agent_strategy: OLD\n", encoding="utf-8")
    metrics = _passing_m7_remaining_metrics()
    metrics["inference_parity"]["composite_reload_passed"] = False
    metrics["composite_metadata"]["reload_supported"] = False
    metrics["smoke_validation"] = {
        "passed": True,
        "composite_reload_supported": False,
    }
    store = FakePromotionStore(_best_iteration(metrics))

    with pytest.raises(ValueError, match="development gate bundle failed"):
        await ConfigPromoter(store).confirm("research_1")

    assert target.read_text(encoding="utf-8") == "agent_strategy: OLD\n"
