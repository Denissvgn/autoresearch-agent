from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.api import results


class FakeStore:
    def __init__(self) -> None:
        self.pipelines: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.iterations: dict[str, list[dict]] = {}
        self.hpo_studies: dict[str, list[dict]] = {}
        self.planned_trials: dict[str, list[dict]] = {}
        self.promotions: list[dict] = []
        self.audit_events: list[dict] = []

    async def get_pipeline(self, pipeline_id: str):
        return self.pipelines.get(pipeline_id)

    async def get_session(self, session_id: str):
        return self.sessions.get(session_id)

    async def get_iterations(self, research_id: str):
        return self.iterations.get(research_id, [])

    async def get_iteration(self, research_id: str, iteration: int):
        return next(
            (
                row for row in self.iterations.get(research_id, [])
                if row.get("iteration") == iteration
            ),
            None,
        )

    async def get_best_iteration(self, research_id: str):
        rows = self.iterations.get(research_id, [])
        return rows[0] if rows else None

    async def get_hpo_studies(self, research_id: str):
        return self.hpo_studies.get(research_id, [])

    async def get_planned_trials(self, research_id: str):
        return self.planned_trials.get(research_id, [])

    async def list_promotions(self):
        return self.promotions

    async def list_audit_events(
        self,
        *,
        limit: int = 100,
        action: str | None = None,
        research_id: str | None = None,
        pipeline_id: str | None = None,
    ):
        rows = self.audit_events
        if action:
            rows = [row for row in rows if row.get("action") == action]
        if research_id:
            rows = [row for row in rows if row.get("research_id") == research_id]
        if pipeline_id:
            rows = [row for row in rows if row.get("pipeline_id") == pipeline_id]
        return rows[:limit]


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_pipeline_agent_log_uses_phase_sessions_and_download(tmp_path: Path):
    store = FakeStore()
    results.init(store)

    direction_ws = tmp_path / "direction"
    rl_ws = tmp_path / "rl"
    _write_jsonl(
        direction_ws / "agent_log.jsonl",
        [
            {
                "ts": "2026-04-06T10:00:00+00:00",
                "turn": 0,
                "type": "system",
                "content": "direction phase started",
                "meta": {},
            }
        ],
    )
    _write_jsonl(
        rl_ws / "agent_log.jsonl",
        [
            {
                "ts": "2026-04-06T10:05:00+00:00",
                "turn": 0,
                "type": "system",
                "content": "rl phase started",
                "meta": {},
            }
        ],
    )

    store.pipelines["pipe_demo"] = {
        "id": "pipe_demo",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "status": "running",
        "current_phase": "rl",
        "direction_session_id": "res_dir",
        "volatility_session_id": None,
        "rl_session_id": "res_rl",
    }
    store.sessions["res_dir"] = {
        "id": "res_dir",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": "direction",
        "workspace_path": str(direction_ws),
    }
    store.sessions["res_rl"] = {
        "id": "res_rl",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": "rl",
        "workspace_path": str(rl_ws),
    }
    store.iterations["res_rl"] = [
        {
            "id": 1,
            "research_id": "res_rl",
            "iteration": 1,
            "primary_metric": 1.23,
            "metric_name": "sharpe",
            "all_gates_passed": 1,
            "decision": "keep",
            "description": "good run",
            "config_snapshot": None,
            "metrics_json": json.dumps({"mean_oos_sharpe": 1.23}),
            "training_time_s": 10.0,
            "created_at": "2026-04-06T10:06:00+00:00",
            "mlflow_run_id": None,
        }
    ]

    payload = await results.get_agent_log("pipe_demo", format="json")

    assert payload["research_id"] == "pipe_demo"
    assert payload["resolved_research_id"] == "res_rl"
    assert [entry["meta"]["phase"] for entry in payload["entries"]] == [
        "direction",
        "rl",
    ]
    assert payload["total_lines"] == 2

    iterations = await results.get_iterations("pipe_demo")
    assert len(iterations) == 1
    assert iterations[0]["research_id"] == "res_rl"

    response = await results.download_agent_log("pipe_demo")
    body = response.body.decode("utf-8")
    assert '"phase": "direction"' in body
    assert '"phase": "rl"' in body
    assert "DOGE_USDT_rl_agent_log.jsonl" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_pipeline_agent_log_is_empty_before_first_phase():
    store = FakeStore()
    results.init(store)
    store.pipelines["pipe_empty"] = {
        "id": "pipe_empty",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "status": "running",
        "current_phase": None,
        "direction_session_id": None,
        "volatility_session_id": None,
        "rl_session_id": None,
    }

    payload = await results.get_agent_log("pipe_empty", format="json")

    assert payload["entries"] == []
    assert payload["total_lines"] == 0
    assert payload["resolved_research_id"] is None

    iterations = await results.get_iterations("pipe_empty")
    assert iterations == []


@pytest.mark.asyncio
async def test_pipeline_results_expose_promotion_blockers():
    store = FakeStore()
    results.init(store)
    store.pipelines["pipe_blocked"] = {
        "id": "pipe_blocked",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "status": "promotion_blocked",
        "current_phase": "rl",
        "direction_session_id": None,
        "volatility_session_id": None,
        "rl_session_id": None,
        "promotion_blocked_phase": "rl",
        "promotion_blockers_json": json.dumps(["missing_rl_oos_gates"]),
        "promotion_preview_json": json.dumps(
            {
                "schema_version": "pipeline_promotion_blocked.v1",
                "phase": "rl",
                "blockers": ["missing_rl_oos_gates"],
            }
        ),
    }

    payload = await results.get_results("pipe_blocked")

    assert payload["session"]["promotion_blockers"] == ["missing_rl_oos_gates"]
    assert payload["session"]["promotion_preview"]["phase"] == "rl"


@pytest.mark.asyncio
async def test_hpo_studies_decode_structured_plan_fields():
    store = FakeStore()
    results.init(store)
    store.sessions["res_hpo"] = {
        "id": "res_hpo",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": "direction",
        "workspace_path": "/tmp/res_hpo",
    }
    store.hpo_studies["res_hpo"] = [
        {
            "id": 1,
            "research_id": "res_hpo",
            "iteration": 0,
            "study_id": "hpo_res_hpo_direction",
            "n_trials": 4,
            "max_trials": 4,
            "completed_trials": 0,
            "top_trials_json": json.dumps([{"trial": 1, "value": 0.62}]),
            "search_space_json": json.dumps({"prediction_horizon": [3, 6]}),
            "budget_json": json.dumps({"max_iterations": 4}),
            "timeout_s": 900,
            "quick_mode": 1,
            "status": "planned",
        }
    ]

    payload = await results.get_hpo_studies("res_hpo")

    study = payload["hpo_studies"][0]
    assert study["study_id"] == "hpo_res_hpo_direction"
    assert study["search_space"]["prediction_horizon"] == [3, 6]
    assert study["budget"]["max_iterations"] == 4
    assert study["top_trials"][0]["value"] == 0.62


@pytest.mark.asyncio
async def test_research_state_endpoint_reconstructs_session_without_workspace():
    store = FakeStore()
    results.init(store)
    store.sessions["res_state"] = {
        "id": "res_state",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": "direction",
        "status": "running",
        "workspace_path": "/tmp/res_state",
        "max_budget_usd": 2.0,
        "total_api_cost_usd": 0.25,
        "max_iterations": 3,
    }
    store.iterations["res_state"] = [
        {
            "id": 1,
            "research_id": "res_state",
            "iteration": 1,
            "primary_metric": 0.64,
            "metric_name": "auc",
            "all_gates_passed": 1,
            "decision": "keep",
            "metrics_json": json.dumps(
                {
                    "mlflow_run_id": "run-1",
                    "artifact_hash": "artifact-sha",
                    "calibration_full_validation": {"selected": {}},
                    "economic_replay": {"gates": {"all_gates_passed": True}},
                    "inference_parity": {
                        "feature_name_alignment_passed": True,
                        "feature_count_alignment_passed": True,
                        "model_roster_parity_passed": True,
                    },
                    "rollback_target": "direction_model:1",
                    "smoke_validation": {"passed": True},
                }
            ),
            "attempt_snapshot_json": json.dumps(
                {
                    "artifact_hash": "artifact-sha",
                    "config_snapshot_sha256": "config-sha",
                }
            ),
            "attempt_snapshot_hash": "attempt-sha",
        },
        {
            "id": 2,
            "research_id": "res_state",
            "iteration": 2,
            "primary_metric": None,
            "metric_name": None,
            "all_gates_passed": 0,
            "decision": "discard",
            "metrics_json": json.dumps({"status": "pruned"}),
        },
    ]
    store.hpo_studies["res_state"] = [
        {
            "id": 10,
            "research_id": "res_state",
            "iteration": 0,
            "study_id": "hpo_res_state_direction",
            "top_trials_json": "[]",
            "search_space_json": "{}",
            "budget_json": "{}",
        }
    ]
    store.planned_trials["res_state"] = [
        {
            "id": 30,
            "research_id": "res_state",
            "study_id": "hpo_res_state_direction",
            "trial_id": "trial_001_dz200_scoped_isotonic",
            "trial_index": 1,
            "search_phase": "hpo_screening",
            "config_patch_json": json.dumps({"direction_pct_threshold": 0.020}),
            "config_hash": "trial-sha",
            "expected_command": (
                ".venv/bin/python scripts/autotuner/direction/prepare.py "
                "--config runs/autotuner/DOGE_USDT_15m/direction/"
                "planned_trials/trial_001_dz200_scoped_isotonic/train.yaml --quick"
            ),
            "status": "planned",
        }
    ]
    store.promotions = [
        {
            "id": 20,
            "research_id": "res_state",
            "promoted_at": "2026-04-27T10:00:00+00:00",
            "promotion_metadata": {
                "rollback_target": "direction_model:0",
                "smoke_validation": {
                    "passed": True,
                    "paper_validation": {"status": "not_required"},
                },
            },
        }
    ]

    state = await results.get_research_state("res_state")

    assert state["schema_version"] == "autoresearch_state.v1"
    assert state["current_phase"] == "adaptive_feature_sweeps"
    assert state["budget_usage"]["iterations_used"] == 2
    assert state["hpo_study_ids"] == ["hpo_res_state_direction"]
    assert state["planned_trials"][0]["config_hash"] == "trial-sha"
    assert state["search_plan"]["planned_trial_count"] == 1
    assert state["top_candidates"][0]["artifact_hash"] == "artifact-sha"
    assert state["failed_pruned_configs"][0]["status"] == "pruned"
    assert state["rollback_target"] == "direction_model:0"
    assert state["paper_status"]["status"] == "not_required"


@pytest.mark.asyncio
async def test_research_state_exposes_production_operations_summary():
    store = FakeStore()
    results.init(store)
    store.sessions["res_ops"] = {
        "id": "res_ops",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": "rl",
        "status": "completed",
        "workspace_path": "/tmp/res_ops",
        "max_budget_usd": 2.0,
        "total_api_cost_usd": 0.25,
        "max_iterations": 3,
    }
    metrics = {
        "mlflow_run_id": "run-rl-ops",
        "artifact_hash": "policy-sha",
        "supervised_feature_readiness": {
            "direction": {"passed": True, "auc": 0.66},
            "volatility": {"passed": True, "auc": 0.63},
        },
        "inference_reload_validation": {"passed": True},
        "rollback_target": "rl_policy:1",
        "rl_economic_replay": {
            "schema_version": "rl_economic_replay.v1",
            "rl_profit_score": 0.235,
            "metrics": {
                "post_cost_return": 0.14,
                "max_drawdown": 0.03,
                "sharpe": 1.24,
            },
            "artifact_path": "/tmp/replay.json",
            "artifact_hash": "replay-sha",
        },
        "rl_oos": {
            "feature_bundle_hash": "feature-bundle-sha",
            "nested_validation_used": True,
            "multi_seed": True,
            "n_seed_trials": 3,
            "direction_feature_provenance": {
                "status": "passed",
                "honest_coverage": 1.0,
                "hash": "direction-prov-sha",
            },
            "volatility_feature_provenance": {
                "status": "passed",
                "honest_coverage": 1.0,
                "hash": "volatility-prov-sha",
            },
        },
    }
    store.iterations["res_ops"] = [
        {
            "id": 1,
            "research_id": "res_ops",
            "iteration": 1,
            "primary_metric": 0.235,
            "metric_name": "rl_profit_score",
            "all_gates_passed": 1,
            "decision": "keep",
            "metrics_json": json.dumps(metrics),
            "attempt_snapshot_json": json.dumps({"artifact_hash": "policy-sha"}),
            "attempt_snapshot_hash": "attempt-sha",
            "mlflow_run_id": "run-rl-ops",
        }
    ]
    store.promotions = [
        {
            "id": 10,
            "research_id": "res_ops",
            "model_type": "rl",
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "iteration": 1,
            "scope": "development",
            "target_path": "/tmp/rl.yaml",
            "metadata_path": "/tmp/rl.development.json",
            "promoted_at": "2026-04-30T10:00:00+00:00",
            "promotion_metadata": {
                "schema_version": "development_promotion_metadata.v1",
                "scope": "development",
                "promotion_allowed": True,
                "rollback_target": "rl_policy:0",
            },
        }
    ]
    store.audit_events = [
        {
            "event_id": "aud_1",
            "timestamp": "2026-04-30T10:01:00+00:00",
            "actor_id": "operator",
            "action": "promotion.preview",
            "research_id": "res_ops",
            "pipeline_id": None,
            "request_metadata": {"scope": "production"},
            "outcome": "failure",
            "error_message": "missing_canary_promotion",
        }
    ]

    state = await results.get_research_state("res_ops")

    ops = state["production_operations"]
    assert ops["schema_version"] == "autoresearch_production_operations.v1"
    assert ops["rl_profit"]["status"] == "passed"
    assert ops["rl_profit"]["artifact_hash"] == "replay-sha"
    assert ops["feature_readiness"]["status"] == "passed"
    assert ops["oos_provenance"]["status"] == "passed"
    assert ops["rollback"]["target"] == "rl_policy:0"
    scopes = {item["scope"]: item for item in ops["promotion"]["scopes"]}
    assert scopes["development"]["status"] == "promoted"
    assert scopes["production"]["status"] == "blocked"
    assert "missing_paper_promotion" in scopes["production"]["blockers"]
    assert ops["audit_events"][0]["scope"] == "production"
