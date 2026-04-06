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
