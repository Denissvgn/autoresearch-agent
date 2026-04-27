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
        self.promotions: list[dict] = []

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

    async def list_promotions(self):
        return self.promotions


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
    assert state["top_candidates"][0]["artifact_hash"] == "artifact-sha"
    assert state["failed_pruned_configs"][0]["status"] == "pruned"
    assert state["rollback_target"] == "direction_model:0"
    assert state["paper_status"]["status"] == "not_required"
